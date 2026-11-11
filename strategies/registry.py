"""
Strategy Registry & Factory
Discovers and manages active deterministic trading strategies.
"""

from typing import Dict, List, Optional
import pandas as pd

from backend.app.models.domain import Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.candidates.ema_crossover import EMACrossoverStrategy
from strategies.candidates.mean_reversion import MeanReversionStrategy
from strategies.candidates.orb import OpeningRangeBreakoutStrategy
from strategies.candidates.rsi_momentum import RSIMomentumStrategy
from strategies.candidates.sr_breakout import SRBreakoutStrategy
from strategies.candidates.supertrend_trend import SupertrendStrategy
from strategies.candidates.volume_breakout import VolumeBreakoutStrategy
from strategies.candidates.vwap_continuation import VWAPContinuationStrategy


class StrategyRegistry:
    """Registry maintaining active strategy singletons."""

    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        default_candidates = [
            VWAPContinuationStrategy(),
            EMACrossoverStrategy(),
            RSIMomentumStrategy(),
            OpeningRangeBreakoutStrategy(),
            SupertrendStrategy(),
            SRBreakoutStrategy(),
            VolumeBreakoutStrategy(),
            MeanReversionStrategy(),
        ]
        for s in default_candidates:
            self._strategies[s.name] = s

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Fetch strategy by name."""
        return self._strategies.get(name)

    def list_strategies(self) -> List[Dict[str, str]]:
        """List all registered strategy metadata."""
        return [{"name": s.name, "version": s.version} for s in self._strategies.values()]

    def evaluate_all(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> List[StrategySignal]:
        """Runs all registered strategies on candles and returns any triggered signals."""
        signals: List[StrategySignal] = []
        for strategy in self._strategies.values():
            try:
                sig = strategy.evaluate(candles, instrument, timeframe=timeframe)
                if sig is not None:
                    signals.append(sig)
            except Exception as e:
                # Individual strategy exceptions must never crash the platform
                pass
        return signals


strategy_registry = StrategyRegistry()

