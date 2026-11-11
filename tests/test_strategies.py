"""
Unit tests for the 8 Candidate Trading Strategies and Strategy Registry.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from backend.app.models.domain import DirectionEnum, ExchangeEnum, Instrument, SegmentEnum
from strategies.candidates.ema_crossover import EMACrossoverStrategy
from strategies.candidates.mean_reversion import MeanReversionStrategy
from strategies.candidates.orb import OpeningRangeBreakoutStrategy
from strategies.candidates.rsi_momentum import RSIMomentumStrategy
from strategies.candidates.sr_breakout import SRBreakoutStrategy
from strategies.candidates.supertrend_trend import SupertrendStrategy
from strategies.candidates.volume_breakout import VolumeBreakoutStrategy
from strategies.candidates.vwap_continuation import VWAPContinuationStrategy
from strategies.registry import strategy_registry
from tests.test_indicators import generate_sample_candles

IST = ZoneInfo("Asia/Kolkata")

TEST_INSTRUMENT = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)


def test_strategy_registry_discovery():
    strats = strategy_registry.list_strategies()
    assert len(strats) == 8
    names = {s["name"] for s in strats}
    assert "VWAP_CONTINUATION" in names
    assert "EMA_CROSSOVER" in names
    assert "RSI_MOMENTUM" in names
    assert "ORB" in names
    assert "SUPERTREND" in names
    assert "SR_BREAKOUT" in names
    assert "VOLUME_BREAKOUT" in names
    assert "MEAN_REVERSION" in names


def test_insufficient_candles_returns_none():
    short_df = generate_sample_candles(n=5)
    strat = VWAPContinuationStrategy()
    assert strat.evaluate(short_df, TEST_INSTRUMENT) is None


def test_orb_strategy_bullish_breakout():
    strat = OpeningRangeBreakoutStrategy(orb_candles_count=3)
    # Candles 0-2 define opening range: High=105, Low=95
    # Candle 3 breaks out cleanly to 110 with volume surge
    now = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    df = pd.DataFrame(
        [
            {"timestamp": now, "open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0, "volume": 1000},
            {"timestamp": now + timedelta(minutes=5), "open": 101.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 1000},
            {"timestamp": now + timedelta(minutes=10), "open": 103.0, "high": 104.0, "low": 95.0, "close": 100.0, "volume": 1000},
            {"timestamp": now + timedelta(minutes=15), "open": 100.0, "high": 110.0, "low": 100.0, "close": 109.0, "volume": 3000},
        ]
    )

    sig = strat.evaluate(df, TEST_INSTRUMENT)
    assert sig is not None
    assert sig.direction == DirectionEnum.LONG
    assert sig.entry_price == 109.0
    assert sig.stop_loss < 109.0
    assert sig.target > 109.0


def test_volume_breakout_strategy():
    strat = VolumeBreakoutStrategy()
    df = generate_sample_candles(n=25, trend=0.1)
    # Inject wide expansion candle with 5x volume
    last_idx = len(df) - 1
    df.loc[last_idx, "open"] = 100.0
    df.loc[last_idx, "high"] = 110.0
    df.loc[last_idx, "low"] = 99.0
    df.loc[last_idx, "close"] = 109.5
    df.loc[last_idx, "volume"] = 25000  # Massive RVOL

    sig = strat.evaluate(df, TEST_INSTRUMENT)
    assert sig is not None
    assert sig.direction == DirectionEnum.LONG
    assert sig.entry_price == 109.5
    assert sig.stop_loss == 99.0


def test_evaluate_all_registry():
    df = generate_sample_candles(n=60)
    signals = strategy_registry.evaluate_all(df, TEST_INSTRUMENT)
    assert isinstance(signals, list)

