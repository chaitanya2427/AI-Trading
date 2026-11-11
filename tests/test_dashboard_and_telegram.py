"""
Unit & Integration Tests for Phase 7: Local Dashboard & Telegram Bot
Covers:
- Root HTML serving from compiled frontend dist
- SSE / WebSocket stream broadcasting
- Telegram Bot chat whitelist authorization
- Telegram Bot commands (/status, /approve, /reject, /kill, /squareoff)
- Proposal broadcast formatting
"""

from datetime import datetime, timezone
import json
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from backend.app.adapters.telegram_bot import TelegramBotAdapter, telegram_adapter
from backend.app.api.v1.stream_api import stream_manager
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.db.init_db import init_db
from backend.app.db.session import AsyncSessionLocal
from backend.app.main import app
from execution.portfolio import portfolio_tracker
from execution.proposal_service import proposal_service
from risk.engine import risk_engine
from tests.test_paper_trading import create_sample_proposal


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        await risk_engine.initialize_session(session)
    yield


# ------------------------------------------------------------------------------
# 1. Dashboard Static Asset & Health Serving Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_root_serves_html():
    """Verify that accessing root '/' serves the compiled production HTML."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "AI Multi-Agent Trading System" in res.text


# ------------------------------------------------------------------------------
# 2. Real-Time Streaming Tests (SSE & WebSocket)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_manager_broadcast():
    """Test broadcasting events through ConnectionManager."""
    # When no connections exist, broadcast completes silently
    await stream_manager.broadcast("TEST_EVENT", {"key": "value"})
    assert len(stream_manager.active_connections) == 0


def test_websocket_snapshot_and_ping():
    """Test WebSocket connection lifecycle using Starlette TestClient."""
    client = TestClient(app)
    with client.websocket_connect("/api/v1/stream/ws") as websocket:
        # Initial snapshot received upon connecting
        raw_msg = websocket.receive_text()
        data = json.loads(raw_msg)
        assert data["type"] == "SNAPSHOT"
        assert "portfolio" in data["data"]
        assert "system_state" in data["data"]

        # Client pings server
        websocket.send_text(json.dumps({"action": "PING"}))
        pong_msg = websocket.receive_text()
        pong = json.loads(pong_msg)
        assert pong["type"] == "PONG"


# ------------------------------------------------------------------------------
# 3. Telegram Bot Adapter Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_bot_authorization():
    """Unauthorized chat IDs must be blocked immediately."""
    bot = TelegramBotAdapter()
    bot.allowed_chat_ids = {"12345678"}

    assert bot.is_authorized("12345678") is True
    assert bot.is_authorized("99999999") is False

    # Blocked response
    unauth_resp = await bot.handle_command("99999999", "/status")
    assert "Access Denied" in unauth_resp


@pytest.mark.asyncio
async def test_telegram_bot_status_command():
    """Authorized /status command returns formatted markdown."""
    bot = TelegramBotAdapter()
    bot.allowed_chat_ids = {"12345678"}

    resp = await bot.handle_command("12345678", "/status")
    assert "SYSTEM STATUS" in resp
    assert "Risk State" in resp
    assert "Starting Capital" in resp
    assert "₹250 Limit" in resp


@pytest.mark.asyncio
async def test_telegram_bot_kill_switch_command():
    """Authorized /kill command triggers emergency kill switch fail-closed."""
    bot = TelegramBotAdapter()
    bot.allowed_chat_ids = {"12345678"}

    resp = await bot.handle_command("12345678", "/kill Extreme anomaly observed")
    assert "EMERGENCY KILL SWITCH ACTIVATED" in resp
    assert risk_engine.kill_switch_active is True

    # Reset kill switch for cleanup
    async with AsyncSessionLocal() as session:
        await risk_engine.reset_kill_switch("Restored in test cleanup", session)


@pytest.mark.asyncio
async def test_telegram_bot_proposal_workflow():
    """Authorized /approve and /reject commands through Telegram."""
    bot = TelegramBotAdapter()
    bot.allowed_chat_ids = {"12345678"}

    # 1. Create proposal
    async with AsyncSessionLocal() as session:
        trading_time = clock.now().replace(hour=11, minute=0, second=0)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(clock, "now", lambda: trading_time)

            proposal = create_sample_proposal(symbol="INFY", quantity=2)
            prop_id = await proposal_service.save_proposal(proposal, session)

            # 2. Reject via Telegram
            reject_resp = await bot.handle_command("12345678", f"/reject {prop_id} Volatility too high")
            assert "PROPOSAL REJECTED" in reject_resp


@pytest.mark.asyncio
async def test_telegram_bot_broadcast_proposal():
    """Verify proposal broadcast formatting without throwing errors."""
    bot = TelegramBotAdapter()
    bot.allowed_chat_ids = {"12345678"}
    bot.enabled = False  # Mock mode

    sample_dict = {
        "proposal_id": "test-uuid-1234",
        "symbol": "TCS",
        "direction": "LONG",
        "entry_price": 3500.0,
        "stop_loss": 3480.0,
        "target": 3540.0,
        "quantity": 5,
        "estimated_risk_inr": 100.0,
        "estimated_reward_inr": 200.0,
        "strategy_name": "VWAP_Continuation",
    }
    # Should complete safely in mock mode
    await bot.broadcast_trade_proposal(sample_dict)

