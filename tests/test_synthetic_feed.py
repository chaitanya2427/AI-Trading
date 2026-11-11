"""
Unit tests for Synthetic Market Data Feed.
"""

from datetime import date
import pytest
from backend.app.adapters.synthetic_feed import SyntheticMarketFeed


def test_synthetic_candles_intraday_shape():
    feed = SyntheticMarketFeed(seed=123)
    # Generate 5-minute candles for 1 session (09:15 to 15:30 -> 375 minutes -> 75 candles)
    df = feed.generate_candles(
        symbol="RELIANCE",
        trading_date=date(2026, 11, 4),
        base_price=2500.0,
        timeframe_minutes=5,
    )
    assert len(df) == 75
    assert set(df.columns) == {"timestamp", "open", "high", "low", "close", "volume"}


def test_synthetic_candles_satisfy_invariants():
    feed = SyntheticMarketFeed(seed=456)
    df = feed.generate_candles(timeframe_minutes=1)
    assert len(df) > 0

    # Test all price invariants across entire series
    assert (df["low"] > 0).all()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert (df["volume"] > 0).all()


def test_synthetic_order_book_depth():
    feed = SyntheticMarketFeed(seed=789)
    book = feed.generate_order_book(mid_price=2500.0, tick_size=0.05, depth=5)

    assert book["source"] == "SYNTHETIC_FIXTURE"
    assert len(book["bids"]) == 5
    assert len(book["asks"]) == 5
    assert book["spread"] > 0.0
    # Best ask must be strictly greater than best bid
    assert book["asks"][0]["price"] > book["bids"][0]["price"]


def test_synthetic_quote_provenance():
    feed = SyntheticMarketFeed(seed=999)
    quote = feed.generate_quote(symbol="TCS", current_price=3800.0)

    assert quote["symbol"] == "TCS"
    assert quote["ltp"] == 3800.0
    assert quote["provenance"]["source"] == "SYNTHETIC_FIXTURE"
    assert quote["provenance"]["is_stale"] is False

