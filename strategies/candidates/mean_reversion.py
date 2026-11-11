"""
Strategy 8: Mean Reversion (Bollinger Bands + RSI Extreme)
Trades statistical overextended extremes piercing Bollinger Bands with reversal confirmation.
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import calculate_all_indicators


class MeanReversionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MEAN_REVERSION", version="1.0", min_candles_required=25)

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
        bb_upper = float(last["bb_upper"])
        bb_mid = float(last["bb_mid"])
        bb_lower = float(last["bb_lower"])
        rsi_val = float(last["rsi"])

        # Bullish Reversal: Prev pierced lower band with low RSI, current candle closed green back above lower band
        if prev["low"] < bb_lower and prev["rsi"] < 35.0 and last["close"] > last["open"] and current_price > bb_lower:
            stop_loss = round(prev["low"] - instrument.tick_size * 2, 2)
            target = round(bb_mid, 2)
            risk_dist = current_price - stop_loss
            reward_dist = target - current_price

            if risk_dist <= 0 or reward_dist < risk_dist * 1.2:
                return None

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.LONG,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.71,
                supporting_evidence=[
                    f"Price rebounded from lower Bollinger Band ({bb_lower:.2f})",
                    f"RSI extreme ({prev['rsi']:.1f}) confirmed mean-reversion setup",
                ],
            )

        # Bearish Reversal: Prev pierced upper band with high RSI, current candle closed red back below upper band
        if prev["high"] > bb_upper and prev["rsi"] > 65.0 and last["close"] < last["open"] and current_price < bb_upper:
            stop_loss = round(prev["high"] + instrument.tick_size * 2, 2)
            target = round(bb_mid, 2)
            risk_dist = stop_loss - current_price
            reward_dist = current_price - target

            if risk_dist <= 0 or reward_dist < risk_dist * 1.2:
                return None

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.SHORT,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.71,
                supporting_evidence=[
                    f"Price rejected from upper Bollinger Band ({bb_upper:.2f})",
                    f"RSI extreme ({prev['rsi']:.1f}) confirmed mean-reversion setup",
                ],
            )

        return None

