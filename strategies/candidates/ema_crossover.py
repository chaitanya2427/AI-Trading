"""
Strategy 2: EMA Multi-Timeframe Trend Following (9 / 21 / 50)
Enters on fast EMA (9) cross above/below medium EMA (21) in the direction of the trend (50 EMA).
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import calculate_all_indicators


class EMACrossoverStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="EMA_CROSSOVER", version="1.0", min_candles_required=55)

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
        ema_9_last = float(last["ema_9"])
        ema_21_last = float(last["ema_21"])
        ema_50_last = float(last["ema_50"])

        ema_9_prev = float(prev["ema_9"])
        ema_21_prev = float(prev["ema_21"])
        atr_val = max(float(last["atr"]), instrument.tick_size * 5)

        # Bullish Crossover: 9 EMA crosses above 21 EMA while price > 50 EMA
        if ema_9_prev <= ema_21_prev and ema_9_last > ema_21_last and current_price > ema_50_last:
            stop_loss = round(min(ema_21_last - 0.5 * atr_val, current_price - 1.5 * atr_val), 2)
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
                confidence=0.72,
                supporting_evidence=[
                    f"9 EMA ({ema_9_last:.2f}) crossed above 21 EMA ({ema_21_last:.2f})",
                    f"Trend alignment: Price ({current_price:.2f}) above 50 EMA ({ema_50_last:.2f})",
                ],
            )

        # Bearish Crossover: 9 EMA crosses below 21 EMA while price < 50 EMA
        if ema_9_prev >= ema_21_prev and ema_9_last < ema_21_last and current_price < ema_50_last:
            stop_loss = round(max(ema_21_last + 0.5 * atr_val, current_price + 1.5 * atr_val), 2)
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
                confidence=0.72,
                supporting_evidence=[
                    f"9 EMA ({ema_9_last:.2f}) crossed below 21 EMA ({ema_21_last:.2f})",
                    f"Trend alignment: Price ({current_price:.2f}) below 50 EMA ({ema_50_last:.2f})",
                ],
            )

        return None

