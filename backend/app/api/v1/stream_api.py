"""
Real-Time Event Streaming API (WebSockets & Server-Sent Events)
Streams market data ticks, risk headroom, P&L, trade proposals, and position updates
to the local web dashboard with zero cloud dependencies.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from execution.portfolio import portfolio_tracker
from execution.paper_broker import paper_broker
from risk.engine import risk_engine

logger = get_logger("backend.stream_api")

router = APIRouter(prefix="/stream", tags=["Real-Time Stream"])


class ConnectionManager:
    """Manages active WebSocket connections for dashboard live streaming."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("New dashboard WebSocket connected. Total active: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("Dashboard WebSocket disconnected. Remaining active: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcasts a JSON-encoded event to all connected clients."""
        if not self.active_connections:
            return

        message = {
            "type": event_type,
            "timestamp": clock.now().isoformat(),
            "execution_mode": "PAPER",
            "provenance": "SIMULATED",
            "data": data,
        }
        payload = json.dumps(message)

        dead_connections: List[WebSocket] = []
        async with self._lock:
            for ws in list(self.active_connections):
                try:
                    await ws.send_text(payload)
                except Exception as e:
                    logger.warning("Error sending message to WebSocket: %s", e)
                    dead_connections.append(ws)

            for ws in dead_connections:
                self.active_connections.discard(ws)


stream_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint streaming live session ticks, risk metrics, and order updates.
    """
    await stream_manager.connect(websocket)
    try:
        # Send initial snapshot upon connection
        summary = portfolio_tracker.get_portfolio_summary()
        initial_snapshot = {
            "system_state": risk_engine.state.status.value if risk_engine.state else "UNKNOWN",
            "kill_switch_active": risk_engine.kill_switch_active,
            "portfolio": summary,
            "open_positions": [p.to_dict() for p in portfolio_tracker.get_open_positions()],
            "recent_orders": [o.to_dict() for o in paper_broker.list_orders(limit=10)],
        }
        await websocket.send_text(
            json.dumps({
                "type": "SNAPSHOT",
                "timestamp": clock.now().isoformat(),
                "data": initial_snapshot,
            })
        )

        # Heartbeat loop listening for client pings
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": clock.now().isoformat()}))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await stream_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket unhandled exception: %s", e)
        await stream_manager.disconnect(websocket)


@router.get("/sse")
async def sse_dashboard_endpoint():
    """
    Server-Sent Events (SSE) alternative for dashboard clients.
    Emits continuous state updates every 1.0 second.
    """
    async def event_generator():
        while True:
            summary = portfolio_tracker.get_portfolio_summary()
            payload = {
                "type": "METRICS_HEARTBEAT",
                "timestamp": clock.now().isoformat(),
                "system_state": risk_engine.state.status.value if risk_engine.state else "UNKNOWN",
                "kill_switch_active": risk_engine.kill_switch_active,
                "net_pnl": summary["net_pnl_inr"],
                "realized_pnl": summary["realized_pnl_inr"],
                "unrealized_pnl": summary["unrealized_pnl_inr"],
                "total_charges": summary["total_charges_inr"],
                "headroom": summary["loss_limit_headroom_inr"],
                "open_positions_count": summary["open_positions_count"],
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

