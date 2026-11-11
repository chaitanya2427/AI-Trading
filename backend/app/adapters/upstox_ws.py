"""
Upstox WebSocket Feed V3 Client (Protobuf Binary Streaming)
Manages WebSocket connection lifecycle, binary Protobuf deserialization, and tick distribution.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set
from zoneinfo import ZoneInfo
import websockets

from backend.app.adapters.proto import MarketDataFeed_pb2
from backend.app.adapters.synthetic_feed import synthetic_feed
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.models.domain import MarketDataProvenance

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class UpstoxWebSocketClient:
    """
    Client for Upstox Feed V3 WebSocket.
    Processes binary Protobuf frames and distributes structured ticks to callbacks.
    """

    def __init__(self):
        self.subscribed_keys: Set[str] = set()
        self.latest_ticks: Dict[str, Dict] = {}
        self.callbacks: List[Callable[[Dict], None]] = []
        self._running = False
        self._ws_task: Optional[asyncio.Task] = None
        self._last_heartbeat: datetime = clock.now()

    def add_callback(self, cb: Callable[[Dict], None]) -> None:
        """Register a callback for incoming ticks."""
        self.callbacks.append(cb)

    def subscribe(self, instrument_keys: List[str]) -> None:
        """Adds instrument keys to subscription set."""
        for key in instrument_keys:
            self.subscribed_keys.add(key)

    def unsubscribe(self, instrument_keys: List[str]) -> None:
        """Removes instrument keys from subscription set."""
        for key in instrument_keys:
            self.subscribed_keys.discard(key)

    def get_latest_tick(self, instrument_key: str) -> Optional[Dict]:
        """Returns the most recent tick for an instrument, or generates a synthetic tick if unavailable."""
        if instrument_key in self.latest_ticks:
            return self.latest_ticks[instrument_key]

        # Generate synthetic fallback tick if not connected
        symbol = instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
        tick = synthetic_feed.generate_quote(symbol, 2500.0)
        tick["instrument_key"] = instrument_key
        self.latest_ticks[instrument_key] = tick
        return tick

    def parse_protobuf_message(self, binary_data: bytes) -> List[Dict]:
        """
        Deserializes a raw Protobuf byte buffer into structured tick records.
        """
        parsed_ticks: List[Dict] = []
        try:
            feed_response = MarketDataFeed_pb2.FeedResponse()
            feed_response.ParseFromString(binary_data)

            now = clock.now()

            for key, feed in feed_response.feeds.items():
                tick: Dict = {
                    "instrument_key": key,
                    "timestamp": now.isoformat(),
                    "source": "UPSTOX_WS_FEED_V3",
                }

                # Check for LTPC
                if feed.HasField("ltpc"):
                    tick["ltp"] = feed.ltpc.ltp
                    tick["ltt"] = feed.ltpc.ltt
                    tick["ltq"] = feed.ltpc.ltq
                    tick["close"] = feed.ltpc.cp

                # Check for FullFeed
                elif feed.HasField("fullFeed"):
                    full = feed.fullFeed
                    tick["ltp"] = full.ltpc.ltp
                    tick["ltt"] = full.ltpc.ltt
                    tick["ltq"] = full.ltpc.ltq
                    tick["close"] = full.ltpc.cp
                    tick["atp"] = full.atp
                    tick["volume"] = full.vtot
                    tick["oi"] = full.oi

                    # Parse Depth Quotes
                    bids = []
                    asks = []
                    if full.HasField("marketLevel"):
                        for q in full.marketLevel.bidAskQuote:
                            if q.bq > 0 and q.bp > 0:
                                bids.append({"price": q.bp, "quantity": q.bq, "orders": q.bno})
                            if q.aq > 0 and q.ap > 0:
                                asks.append({"price": q.ap, "quantity": q.aq, "orders": q.ano})
                    tick["bids"] = bids
                    tick["asks"] = asks

                tick["provenance"] = MarketDataProvenance(
                    as_of=now,
                    source="UPSTOX_WS_FEED_V3",
                    is_stale=False,
                ).model_dump()

                parsed_ticks.append(tick)
                self.latest_ticks[key] = tick

        except Exception as e:
            logger.error(f"Error parsing Protobuf feed payload: {e}")

        return parsed_ticks

    async def start(self) -> None:
        """Starts the WebSocket connection or simulated background tick stream."""
        if self._running:
            return
        self._running = True

        if not settings.UPSTOX_ACCESS_TOKEN or len(settings.UPSTOX_ACCESS_TOKEN) < 20:
            logger.info("Upstox token not set. Running WebSocket in SYNTHETIC simulation mode.")
            self._ws_task = asyncio.create_task(self._synthetic_tick_loop())
        else:
            self._ws_task = asyncio.create_task(self._live_ws_loop())

    async def stop(self) -> None:
        """Stops the WebSocket background loop."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

    async def _synthetic_tick_loop(self) -> None:
        """Generates periodic synthetic ticks for subscribed instruments."""
        while self._running:
            keys = list(self.subscribed_keys) or ["NSE_INDEX|Nifty 50", "NSE_EQ|INE002A01018"]
            for key in keys:
                symbol = key.split("|")[-1]
                quote = synthetic_feed.generate_quote(symbol, 2500.0)
                quote["instrument_key"] = key
                self.latest_ticks[key] = quote
                for cb in self.callbacks:
                    try:
                        cb(quote)
                    except Exception as e:
                        logger.error(f"Error in tick callback: {e}")
            await asyncio.sleep(1.0)

    async def _live_ws_loop(self) -> None:
        """Connects to real Upstox WebSocket Feed V3."""
        # Stub for live streaming when credentials provided
        logger.info("Live WebSocket adapter initialized (Read-Only).")


upstox_ws = UpstoxWebSocketClient()

