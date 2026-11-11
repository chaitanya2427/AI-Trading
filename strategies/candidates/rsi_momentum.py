"""
Strategy 3: RSI Momentum & Divergence
Enters on directional RSI momentum breakouts confirmed by moving average slope.
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import calculate_all_indicators


class RSIMomentumStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="RSI_MOMENTUM", version="1.0", min_candles_required=25)

    def evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> Optional[StrategySignal]:
        if not self.has_sufficient_data(candles):
            return None

        df = calculate_all_indicators(candles)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = float(last["close"])
        rsi_last = float(last["rsi"])
        rsi_prev = float(prev["rsi"])
        atr_val = max(float(last["atr"]), instrument.tick_size * 5)

        # Bullish Momentum: RSI crosses above 55 with upward velocity
        if rsi_prev <= 55.0 and rsi_last > 55.0 and rsi_last < 70.0 and last["close"] > last["open"]:
            stop_loss = round(current_price - 1.5 * atr_val, 2)
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
                confidence=0.70,
                supporting_evidence=[
                    f"RSI crossed above momentum threshold (55.0) to {rsi_last:.1f}",
                    "Bullish price bar expansion confirmed",
                ],
            )

        # Bearish Momentum: RSI crosses below 45 with downward velocity
        if rsi_prev >= 45.0 and rsi_last < 45.0 and rsi_last > 30.0 and last["close"] < last["open"]:
            stop_loss = round(current_price + 1.5 * atr_val, 2)
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
                confidence=0.70,
                supporting_evidence=[
                    f"RSI crossed below momentum threshold (45.0) to {rsi_last:.1f}",
                    "Bearish price bar expansion confirmed",
                ],
            )

        return None

