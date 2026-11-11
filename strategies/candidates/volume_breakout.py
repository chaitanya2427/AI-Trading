"""
Strategy 7: Volume-Confirmed Breakout
Trades wide-range bar thrusts accompanied by relative volume (RVOL > 2.0).
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import atr


class VolumeBreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="VOLUME_BREAKOUT", version="1.0", min_candles_required=25)

    def evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> Optional[StrategySignal]:
        if not self.has_sufficient_data(candles):
            return None

        last = candles.iloc[-1]
        current_price = float(last["close"])
        open_price = float(last["open"])
        high_price = float(last["high"])
        low_price = float(last["low"])

        avg_vol = candles["volume"].iloc[-21:-1].mean()
        rvol = last["volume"] / max(1.0, avg_vol)

        atr_val = float(atr(candles).iloc[-1])
        candle_range = high_price - low_price

        # Must have RVOL > 2.0 and wide expansion bar
        if rvol < 2.0 or candle_range < 1.2 * atr_val:
            return None

        # Bullish Volume Thrust
        if current_price > open_price and (current_price - low_price) / candle_range > 0.7:
            stop_loss = round(low_price, 2)
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
                confidence=0.77,
                supporting_evidence=[
                    f"RVOL surge of {rvol:.2f}x average volume",
                    f"Bullish bar expansion ({candle_range:.2f}) closed near top quartile",
                ],
            )

        # Bearish Volume Thrust
        if current_price < open_price and (high_price - current_price) / candle_range > 0.7:
            stop_loss = round(high_price, 2)
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
                confidence=0.77,
                supporting_evidence=[
                    f"RVOL surge of {rvol:.2f}x average volume",
                    f"Bearish bar expansion ({candle_range:.2f}) closed near bottom quartile",
                ],
            )

        return None

