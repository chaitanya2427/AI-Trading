"""
Unit tests for Upstox Feed V3 Protobuf parsing and WebSocket streaming client.
"""

import pytest
from backend.app.adapters.proto import MarketDataFeed_pb2
from backend.app.adapters.upstox_ws import UpstoxWebSocketClient


def test_protobuf_binary_serialization_and_parsing():
    # 1. Build a synthetic Protobuf FeedResponse
    response_msg = MarketDataFeed_pb2.FeedResponse()
    response_msg.type = MarketDataFeed_pb2.FeedResponse.Type.live_feed

    # Add LTPC feed for RELIANCE
    feed_reliance = response_msg.feeds["NSE_EQ|INE002A01018"]
    feed_reliance.ltpc.ltp = 2525.50
    feed_reliance.ltpc.ltt = 1793798400000
    feed_reliance.ltpc.ltq = 15
    feed_reliance.ltpc.cp = 2510.00

    # Add FullFeed for NIFTY
    feed_nifty = response_msg.feeds["NSE_INDEX|Nifty 50"]
    feed_nifty.fullFeed.ltpc.ltp = 24150.00
    feed_nifty.fullFeed.ltpc.cp = 24100.00
    feed_nifty.fullFeed.atp = 24125.00
    feed_nifty.fullFeed.vtot = 1500000
    feed_nifty.fullFeed.oi = 3500000.0

    # Add bid/ask depth quote
    quote = feed_nifty.fullFeed.marketLevel.bidAskQuote.add()
    quote.bp = 24149.50
    quote.bq = 500
    quote.bno = 3
    quote.ap = 24150.50
    quote.aq = 400
    quote.ano = 2

    # Serialize to bytes
    binary_data = response_msg.SerializeToString()
    assert isinstance(binary_data, bytes)
    assert len(binary_data) > 0

    # 2. Parse using UpstoxWebSocketClient
    client = UpstoxWebSocketClient()
    ticks = client.parse_protobuf_message(binary_data)

    assert len(ticks) == 2
    by_key = {t["instrument_key"]: t for t in ticks}

    # Verify RELIANCE LTPC
    rel_tick = by_key["NSE_EQ|INE002A01018"]
    assert rel_tick["ltp"] == 2525.50
    assert rel_tick["close"] == 2510.00
    assert rel_tick["source"] == "UPSTOX_WS_FEED_V3"

    # Verify NIFTY FullFeed
    nifty_tick = by_key["NSE_INDEX|Nifty 50"]
    assert nifty_tick["ltp"] == 24150.00
    assert nifty_tick["volume"] == 1500000
    assert len(nifty_tick["bids"]) == 1
    assert nifty_tick["bids"][0]["price"] == 24149.50
    assert len(nifty_tick["asks"]) == 1
    assert nifty_tick["asks"][0]["price"] == 24150.50


def test_ws_client_subscription_and_callbacks():
    client = UpstoxWebSocketClient()
    received_ticks = []

    client.add_callback(lambda t: received_ticks.append(t))
    client.subscribe(["NSE_EQ|INE002A01018"])
    assert "NSE_EQ|INE002A01018" in client.subscribed_keys

    # Retrieve latest tick (triggers synthetic fallback when disconnected)
    tick = client.get_latest_tick("NSE_EQ|INE002A01018")
    assert tick is not None
    assert tick["instrument_key"] == "NSE_EQ|INE002A01018"
    assert "ltp" in tick

