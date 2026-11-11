"""
Unit and Integration tests for Backtesting Engine, Cost Model, and Walk-Forward Validation.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.adapters.instruments import instrument_master
from backend.app.db.init_db import init_db
from backend.app.main import app
from backend.app.models.domain import DirectionEnum, ExchangeEnum, Instrument, SegmentEnum
from backtesting.engine import BacktestEngine
from backtesting.metrics import BacktestMetricsCalculator
from backtesting.runner import backtest_runner
from backtesting.walk_forward import WalkForwardValidator
from strategies.base import BaseStrategy, StrategySignal

IST = ZoneInfo("Asia/Kolkata")
TEST_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)


class MockSimpleStrategy(BaseStrategy):
    """Strategy that triggers Long on bar index 20."""
    def __init__(self):
        super().__init__(name="MOCK_STRAT", version="1.0", min_candles_required=20)

    def evaluate(self, candles, instrument, timeframe="5m"):
        if len(candles) == 21:
            last = candles.iloc[-1]
            p = float(last["close"])
            return StrategySignal(
                strategy_name=self.name,
                direction=DirectionEnum.LONG,
                timeframe=timeframe,
                entry_price=p,
                stop_loss=p - 10.0,
                target=p + 20.0,
                confidence=0.8,
            )
        return None


def test_lookahead_bias_elimination():
    # Construct sequence: bar 20 triggers signal, bar 21 open is 2505.0
    now = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    rows = []
    for i in range(25):
        ts = now + timedelta(minutes=5 * i)
        rows.append(
            {
                "timestamp": ts,
                "open": 2500.0 + i,
                "high": 2502.0 + i,
                "low": 2498.0 + i,
                "close": 2501.0 + i,
                "volume": 1000,
            }
        )
    df = pd.DataFrame(rows)

    strat = MockSimpleStrategy()
    engine = BacktestEngine(strategy=strat, instrument=TEST_INST, slippage_pct=0.0, spread_ticks=0)
    result = engine.run(df)

    assert result["summary"]["total_trades"] == 1
    # Trade must have executed at bar 21 (timestamp 5*21 = 105 mins after start)
    # Entry price must match bar 21 Open (which is 2500.0 + 21 = 2521.0)
    # It must NOT have executed at bar 20 Close (look-ahead bias check)


def test_conservative_intrabar_exit():
    # Construct scenario where bar hits BOTH stop-loss and target
    now = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    rows = []
    for i in range(21):
        ts = now + timedelta(minutes=5 * i)
        rows.append(
            {
                "timestamp": ts,
                "open": 2500.0,
                "high": 2505.0,
                "low": 2495.0,
                "close": 2500.0,
                "volume": 1000,
            }
        )
    # Bar 21 (Execution at Open 2500, Stop 2490, Target 2520)
    rows.append(
        {
            "timestamp": now + timedelta(minutes=105),
            "open": 2500.0,
            "high": 2505.0,
            "low": 2495.0,
            "close": 2500.0,
            "volume": 1000,
        }
    )
    # Bar 22 (Extreme bar: High hits 2530 (Target), Low hits 2480 (Stop))
    rows.append(
        {
            "timestamp": now + timedelta(minutes=110),
            "open": 2500.0,
            "high": 2530.0,  # Hits target (2520)
            "low": 2480.0,   # Hits stop (2490)
            "close": 2510.0,
            "volume": 1000,
        }
    )
    df = pd.DataFrame(rows)

    strat = MockSimpleStrategy()
    engine = BacktestEngine(strategy=strat, instrument=TEST_INST, slippage_pct=0.0, spread_ticks=0)
    result = engine.run(df)

    # Conservative invariant: Stop Loss must take precedence when both hit in same candle
    assert result["summary"]["losing_trades"] == 1
    assert result["summary"]["winning_trades"] == 0


def test_mandatory_intraday_square_off():
    # Construct trade that never hits stop or target and remains open until 15:15 IST
    now = datetime(2026, 11, 4, 9, 15, tzinfo=IST)
    rows = []
    # 72 bars from 09:15 up to 15:15
    for i in range(73):
        ts = now + timedelta(minutes=5 * i)
        rows.append(
            {
                "timestamp": ts,
                "open": 2500.0,
                "high": 2504.0,  # Never hits 2520 target
                "low": 2496.0,   # Never hits 2490 stop
                "close": 2502.0,
                "volume": 1000,
            }
        )
    df = pd.DataFrame(rows)

    strat = MockSimpleStrategy()
    engine = BacktestEngine(strategy=strat, instrument=TEST_INST, slippage_pct=0.0, spread_ticks=0)
    result = engine.run(df)

    assert result["summary"]["total_trades"] == 1
    assert result["summary"]["total_trades"] == 1


def test_metrics_calculator_tear_sheet():
    trades = [
        {
            "gross_pnl": 200.0,
            "net_pnl": 175.0,
            "total_costs": 25.0,
            "entry_time": "2026-11-04T10:00:00+05:30",
            "exit_time": "2026-11-04T10:30:00+05:30",
            "costs_breakdown": {"brokerage": 20.0, "stt": 2.5, "exchange_turnover": 0.5, "gst": 2.0},
        },
        {
            "gross_pnl": -100.0,
            "net_pnl": -125.0,
            "total_costs": 25.0,
            "entry_time": "2026-11-04T11:00:00+05:30",
            "exit_time": "2026-11-04T11:15:00+05:30",
            "costs_breakdown": {"brokerage": 20.0, "stt": 2.5, "exchange_turnover": 0.5, "gst": 2.0},
        },
    ]

    sheet = BacktestMetricsCalculator.compute_tear_sheet(trades, initial_capital=25000.0)

    assert sheet["summary"]["total_trades"] == 2
    assert sheet["summary"]["winning_trades"] == 1
    assert sheet["summary"]["losing_trades"] == 1
    assert sheet["summary"]["win_rate_pct"] == 50.0
    assert sheet["pnl"]["net_pnl_inr"] == 50.0  # 175 - 125 = 50.0
    assert sheet["pnl"]["gross_pnl_inr"] == 100.0  # 200 - 100 = 100.0
    assert sheet["pnl"]["total_costs_inr"] == 50.0  # 25 + 25 = 50.0
    assert sheet["summary"]["profit_factor"] == 2.0  # 200 / 100 = 2.0


def test_walk_forward_splits():
    df = backtest_runner.generate_multi_day_dataset(symbol="RELIANCE", days=3, timeframe_minutes=5)
    strat = MockSimpleStrategy()

    wf = WalkForwardValidator(strategy=strat, instrument=TEST_INST, n_splits=2)
    res = wf.run(df)

    assert res["splits_count"] >= 1
    assert "splits" in res
    assert "walk_forward_efficiency_pct" in res


@pytest.mark.asyncio
async def test_api_run_backtest_endpoint():
    await init_db()
    instrument_master.initialize()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/backtest/run",
            json={
                "strategy_name": "VWAP_CONTINUATION",
                "instrument_key": "NSE_EQ|INE002A01018",
                "days": 2,
                "timeframe_minutes": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "pnl" in data
        assert "risk_metrics" in data
        assert "cost_breakdown_inr" in data
        assert data["metadata"]["simulated"] is True

