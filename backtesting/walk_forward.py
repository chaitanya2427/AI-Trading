"""
Walk-Forward Chronological Validation
Executes out-of-sample partitions without look-ahead bias or data leakage.
"""

from typing import Dict, List
import pandas as pd

from backend.app.models.domain import Instrument
from backtesting.engine import BacktestEngine
from strategies.base import BaseStrategy


class WalkForwardValidator:
    """Performs chronological rolling walk-forward validation."""

    def __init__(
        self,
        strategy: BaseStrategy,
        instrument: Instrument,
        train_ratio: float = 0.70,
        n_splits: int = 3,
    ):
        self.strategy = strategy
        self.instrument = instrument
        self.train_ratio = train_ratio
        self.n_splits = n_splits

    def run(self, candles_df: pd.DataFrame) -> Dict:
        """
        Splits data into chronological anchored or rolling windows and evaluates
        In-Sample (Train) vs Out-of-Sample (Test) performance.
        """
        n_bars = len(candles_df)
        if n_bars < 100:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": f"Requires at least 100 candles for walk-forward splits (provided {n_bars})",
            }

        split_results: List[Dict] = []
        window_size = n_bars // self.n_splits

        for split_idx in range(self.n_splits):
            start_idx = split_idx * (window_size // 2)
            end_idx = min(n_bars, start_idx + window_size)
            window_df = candles_df.iloc[start_idx:end_idx].reset_index(drop=True)

            if len(window_df) < 50:
                continue

            train_cutoff = int(len(window_df) * self.train_ratio)
            train_df = window_df.iloc[:train_cutoff].reset_index(drop=True)
            test_df = window_df.iloc[train_cutoff:].reset_index(drop=True)

            # In-Sample Backtest
            engine_train = BacktestEngine(self.strategy, self.instrument)
            train_result = engine_train.run(train_df, data_source_label="IN_SAMPLE_TRAIN")

            # Out-of-Sample Backtest
            engine_test = BacktestEngine(self.strategy, self.instrument)
            test_result = engine_test.run(test_df, data_source_label="OUT_OF_SAMPLE_TEST")

            split_results.append(
                {
                    "split_index": split_idx + 1,
                    "train_bars": len(train_df),
                    "test_bars": len(test_df),
                    "train_net_pnl": train_result["pnl"]["net_pnl_inr"],
                    "test_net_pnl": test_result["pnl"]["net_pnl_inr"],
                    "train_win_rate": train_result["summary"]["win_rate_pct"],
                    "test_win_rate": test_result["summary"]["win_rate_pct"],
                    "train_profit_factor": train_result["summary"]["profit_factor"],
                    "test_profit_factor": test_result["summary"]["profit_factor"],
                    "in_sample_tear_sheet": train_result,
                    "out_of_sample_tear_sheet": test_result,
                }
            )

        # Aggregate degradation summary
        avg_train_pnl = sum(r["train_net_pnl"] for r in split_results) / max(1, len(split_results))
        avg_test_pnl = sum(r["test_net_pnl"] for r in split_results) / max(1, len(split_results))

        pnl_efficiency = round((avg_test_pnl / avg_train_pnl) * 100.0, 1) if avg_train_pnl != 0 else 0.0

        return {
            "strategy": self.strategy.name,
            "instrument": self.instrument.symbol,
            "splits_count": len(split_results),
            "walk_forward_efficiency_pct": pnl_efficiency,
            "splits": split_results,
        }

