"""
Unit tests for Market Data Sanitizer and Price Invariant Validator.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from backend.app.adapters.validator import MarketDataValidator
from backend.app.core.clock import clock

IST = ZoneInfo("Asia/Kolkata")


def test_validator_candle_invariants_valid():
    valid, err = MarketDataValidator.validate_candle_invariants(
        open_=100.0, high=105.0, low=98.0, close=102.0, volume=5000.0
    )
    assert valid is True
    assert err is None


def test_validator_candle_invariants_invalid_high():
    # High is less than max(Open, Close)
    valid, err = MarketDataValidator.validate_candle_invariants(
        open_=100.0, high=99.0, low=95.0, close=98.0, volume=100.0
    )
    assert valid is False
    assert "High" in err


def test_validator_candle_invariants_invalid_low():
    # Low is greater than min(Open, Close)
    valid, err = MarketDataValidator.validate_candle_invariants(
        open_=100.0, high=105.0, low=101.0, close=103.0, volume=100.0
    )
    assert valid is False
    assert "Low" in err


def test_validator_candle_invariants_negative_volume():
    valid, err = MarketDataValidator.validate_candle_invariants(
        open_=100.0, high=105.0, low=98.0, close=102.0, volume=-5.0
    )
    assert valid is False
    assert "Volume" in err


def test_validator_sanitize_dataframe():
    now = datetime(2026, 11, 4, 10, 0, tzinfo=IST)
    raw_df = pd.DataFrame(
        [
            # Valid candle 1
            {"timestamp": now, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 100},
            # Corrupted candle (High < Open) -> must be filtered
            {"timestamp": now + timedelta(minutes=5), "open": 102.0, "high": 100.0, "low": 95.0, "close": 98.0, "volume": 100},
            # Duplicate candle 1 -> must be deduplicated
            {"timestamp": now, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 100},
            # Valid candle 2
            {"timestamp": now + timedelta(minutes=10), "open": 102.0, "high": 108.0, "low": 101.0, "close": 107.0, "volume": 150},
        ]
    )

    cleaned = MarketDataValidator.sanitize_dataframe(raw_df)
    assert len(cleaned) == 2
    assert list(cleaned["close"]) == [102.0, 107.0]


def test_validator_gap_detection():
    now = datetime(2026, 11, 4, 10, 0, tzinfo=IST)
    # Series with a 15-minute gap between 10:05 and 10:20
    df = pd.DataFrame(
        [
            {"timestamp": now, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 100},
            {"timestamp": now + timedelta(minutes=5), "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0, "volume": 100},
            {"timestamp": now + timedelta(minutes=20), "open": 103.0, "high": 106.0, "low": 102.0, "close": 105.0, "volume": 100},
        ]
    )
    gaps = MarketDataValidator.detect_gaps(df, timeframe_minutes=5)
    assert len(gaps) == 1
    assert gaps[0][0] == now + timedelta(minutes=5)
    assert gaps[0][1] == now + timedelta(minutes=20)


def test_validator_quote_freshness():
    now = datetime(2026, 11, 4, 10, 30, 0, tzinfo=IST)
    clock.set_simulated_time(now)

    # Fresh quote: 2 seconds old
    fresh_ts = now - timedelta(seconds=2)
    prov1 = MarketDataValidator.check_quote_freshness(fresh_ts, max_age_seconds=5.0)
    assert prov1.is_stale is False
    assert prov1.latency_ms == 2000.0

    # Stale quote: 7 seconds old
    stale_ts = now - timedelta(seconds=7)
    prov2 = MarketDataValidator.check_quote_freshness(stale_ts, max_age_seconds=5.0)
    assert prov2.is_stale is True
    assert prov2.latency_ms == 7000.0

