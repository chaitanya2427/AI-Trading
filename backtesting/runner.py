"""
Backtest Runner & Multi-Day Historical Scenario Generator
Assembles multi-day trading sessions for reproducible quantitative backtests.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

from backend.app.adapters.instruments import instrument_master
from backend.app.adapters.synthetic_feed import synthetic_feed
from backend.app.core.clock import clock
from backend.app.models.domain import Instrument
from backtesting.engine import BacktestEngine
from strategies.base import BaseStrategy
from strategies.registry import strategy_registry


class BacktestRunner:
    """Orchestrates historical scenario generation and backtest executions."""

    @staticmethod
    def generate_multi_day_dataset(
        symbol: str = "RELIANCE",
        days: int = 5,
        base_price: float = 2500.0,
        timeframe_minutes: int = 5,
    ) -> pd.DataFrame:
        """
        Generates consecutive intraday trading days (excluding weekends).
        """
        all_dfs: List[pd.DataFrame] = []
        current_date = clock.today() - timedelta(days=days * 2)
        generated_days = 0

        while generated_days < days:
            if not clock.is_weekend(datetime.combine(current_date, datetime.min.time(), tzinfo=clock.now().tzinfo)):
                day_df = synthetic_feed.generate_candles(
                    symbol=symbol,
                    trading_date=current_date,
                    base_price=base_price,
                    timeframe_minutes=timeframe_minutes,
                )
                all_dfs.append(day_df)
                generated_days += 1
                base_price = float(day_df["close"].iloc[-1])

            current_date += timedelta(days=1)

        return pd.concat(all_dfs, ignore_index=True)

    @classmethod
    def run_strategy_backtest(
        cls,
        strategy_name: str,
        instrument_key: str,
        days: int = 5,
        timeframe_minutes: int = 5,
    ) -> Dict:
        """Runs a complete backtest for a strategy over historical multi-day scenario."""
        strategy = strategy_registry.get_strategy(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy {strategy_name} not registered.")

        instrument = instrument_master.get_by_key(instrument_key)
        if not instrument:
            raise ValueError(f"Instrument {instrument_key} not found.")

        candles_df = cls.generate_multi_day_dataset(
            symbol=instrument.symbol,
            days=days,
            timeframe_minutes=timeframe_minutes,
        )

        engine = BacktestEngine(
            strategy=strategy,
            instrument=instrument,
            timeframe=f"{timeframe_minutes}m",
        )

        result = engine.run(candles_df, data_source_label=f"SYNTHETIC_SCENARIO_{days}D")
        result["instrument"] = instrument.symbol
        result["strategy"] = strategy.name
        result["days_simulated"] = days
        return result


backtest_runner = BacktestRunner()
