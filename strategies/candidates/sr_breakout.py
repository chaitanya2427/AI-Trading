"""
Strategy 6: Support / Resistance Breakout
Detects swing highs and lows and trades confirmed breakouts beyond consolidation levels.
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import atr


class SRBreakoutStrategy(BaseStrategy):
    def __init__(self, lookback_period: int = 20):
        super().__init__(name="SR_BREAKOUT", version="1.0", min_candles_required=lookback_period + 2)
        self.lookback_period = lookback_period

    def evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> Optional[StrategySignal]:
        if not self.has_sufficient_data(candles):
            return None

        # Look back over recent swing window excluding latest bar
        window = candles.iloc[-self.lookback_period - 1 : -1]
        resistance = float(window["high"].max())
        support = float(window["low"].min())

        last = candles.iloc[-1]
        prev = candles.iloc[-2]
        current_price = float(last["close"])
        atr_val = float(atr(candles).iloc[-1])
        avg_vol = window["volume"].mean()

        # Bullish Breakout above Resistance
        if prev["close"] <= resistance and current_price > resistance and last["volume"] > avg_vol * 1.2:
            stop_loss = round(resistance - 1.2 * atr_val, 2)
            risk_dist = current_price - stop_loss
            if risk_dist <= 0:
                return None
            target = round(current_price + 2.0 * risk_dist, 2)

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.LONG,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.73,
                supporting_evidence=[
                    f"Price closed above {self.lookback_period}-period resistance ({resistance:.2f})",
                    f"Volume expanded to {last['volume']:.0f} (1.2x average)",
                ],
            )

        # Bearish Breakdown below Support
        if prev["close"] >= support and current_price < support and last["volume"] > avg_vol * 1.2:
            stop_loss = round(support + 1.2 * atr_val, 2)
            risk_dist = stop_loss - current_price
            if risk_dist <= 0:
                return None
            target = round(current_price - 2.0 * risk_dist, 2)

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.SHORT,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.73,
                supporting_evidence=[
                    f"Price closed below {self.lookback_period}-period support ({support:.2f})",
                    f"Volume expanded to {last['volume']:.0f} (1.2x average)",
                ],
            )

        return None

