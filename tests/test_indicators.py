"""
Unit tests for Technical Indicators Engine.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest

from strategies.indicators import (
    atr,
    bollinger_bands,
    calculate_all_indicators,
    ema,
    macd,
    rsi,
    sma,
    supertrend,
    vwap,
)

IST = ZoneInfo("Asia/Kolkata")


def generate_sample_candles(n=50, start_price=100.0, trend=0.5):
    now = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    timestamps = [now + timedelta(minutes=5 * i) for i in range(n)]

    closes = [start_price + trend * i + (i % 3) * 0.2 for i in range(n)]
    opens = [c - 0.2 for c in closes]
    highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
    volumes = [1000 + (i % 5) * 200 for i in range(n)]

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_sma_and_ema():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    s_ma = sma(s, window=3)
    assert pd.isna(s_ma.iloc[0])
    assert s_ma.iloc[2] == 20.0
    assert s_ma.iloc[4] == 40.0

    e_ma = ema(s, span=3)
    assert not pd.isna(e_ma.iloc[2])
    assert e_ma.iloc[-1] > s_ma.iloc[-1]  # EMA reacts faster to recent upward moves


def test_rsi_bounds():
    df = generate_sample_candles(n=40, trend=1.0)
    rsi_vals = rsi(df["close"], period=14)

    assert len(rsi_vals) == 40
    # RSI must strictly lie in [0, 100]
    assert (rsi_vals >= 0.0).all()
    assert (rsi_vals <= 100.0).all()
    # In an uptrend, RSI should be elevated (> 50)
    assert rsi_vals.iloc[-1] > 50.0


def test_atr_positive():
    df = generate_sample_candles(n=30)
    atr_vals = atr(df, period=14)

    assert len(atr_vals) == 30
    assert (atr_vals.dropna() > 0.0).all()


def test_vwap_session_reset():
    # Session 1: Day 1
    day1_start = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    day2_start = datetime(2026, 11, 5, 9, 15, tzinfo=IST)

    ts1 = [day1_start + timedelta(minutes=5 * i) for i in range(5)]
    ts2 = [day2_start + timedelta(minutes=5 * i) for i in range(5)]

    df = pd.DataFrame(
        {
            "timestamp": ts1 + ts2,
            "open": [100.0] * 5 + [200.0] * 5,
            "high": [102.0] * 5 + [202.0] * 5,
            "low": [98.0] * 5 + [198.0] * 5,
            "close": [100.0] * 5 + [200.0] * 5,
            "volume": [1000] * 10,
        }
    )

    vwap_vals = vwap(df)
    # On day 1, typical price is 100, vwap is 100
    assert vwap_vals.iloc[4] == 100.0
    # On day 2, session resets, vwap starts fresh around 200
    assert vwap_vals.iloc[5] == 200.0


def test_bollinger_bands():
    df = generate_sample_candles(n=30)
    upper, mid, lower = bollinger_bands(df["close"], period=20, num_std=2.0)

    valid_idx = ~upper.isna()
    assert (upper[valid_idx] >= mid[valid_idx]).all()
    assert (mid[valid_idx] >= lower[valid_idx]).all()


def test_supertrend_direction():
    df = generate_sample_candles(n=40, trend=1.5)
    st_val, st_dir = supertrend(df, period=10, multiplier=3.0)

    assert len(st_val) == 40
    # In a strong uptrend, direction should be +1 (Bullish)
    assert st_dir.iloc[-1] == 1


def test_calculate_all_indicators():
    df = generate_sample_candles(n=60)
    enriched = calculate_all_indicators(df)

    expected_cols = {
        "rsi", "vwap", "atr", "ema_9", "ema_21", "ema_50",
        "bb_upper", "bb_mid", "bb_lower", "macd_line", "macd_signal", "macd_hist",
        "supertrend", "supertrend_dir"
    }
    assert expected_cols.issubset(set(enriched.columns))

