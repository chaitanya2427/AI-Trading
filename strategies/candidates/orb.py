"""
Strategy 4: Opening Range Breakout (ORB)
Enters on breakout of the initial trading session range (first 15m/30m) with volume confirmation.
"""

from datetime import time
from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal


class OpeningRangeBreakoutStrategy(BaseStrategy):
    def __init__(self, orb_candles_count: int = 3):  # First 3 candles = 15m on a 5m timeframe
        super().__init__(name="ORB", version="1.0", min_candles_required=orb_candles_count + 1)
        self.orb_candles_count = orb_candles_count

    def evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> Optional[StrategySignal]:
        if not self.has_sufficient_data(candles):
            return None

        # Calculate opening range from the initial N candles
        orb_subset = candles.iloc[: self.orb_candles_count]
        orb_high = orb_subset["high"].max()
        orb_low = orb_subset["low"].min()
        orb_range = orb_high - orb_low

        if orb_range <= instrument.tick_size * 2:
            return None

        last = candles.iloc[-1]
        prev = candles.iloc[-2]
        current_price = float(last["close"])
        avg_vol = candles["volume"].iloc[: self.orb_candles_count].mean()

        # Bullish Breakout: Previous candle below/at ORB High, current candle closes cleanly above ORB High
        if prev["close"] <= orb_high and current_price > orb_high and last["volume"] > avg_vol * 1.1:
            stop_loss = round(orb_low + 0.5 * orb_range, 2)  # Halfway back into opening range
            risk_dist = current_price - stop_loss
            if risk_dist <= 0:
                return None
            target = round(current_price + 1.5 * risk_dist, 2)

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.LONG,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.74,
                supporting_evidence=[
                    f"Price broke out above 15m Opening Range High ({orb_high:.2f})",
                    f"Volume confirmation: {last['volume']:.0f} vs ORB avg {avg_vol:.0f}",
                ],
            )

        # Bearish Breakout: Previous candle above/at ORB Low, current candle closes cleanly below ORB Low
        if prev["close"] >= orb_low and current_price < orb_low and last["volume"] > avg_vol * 1.1:
            stop_loss = round(orb_high - 0.5 * orb_range, 2)
            risk_dist = stop_loss - current_price
            if risk_dist <= 0:
                return None
            target = round(current_price - 1.5 * risk_dist, 2)

            return StrategySignal(
                strategy_name=self.name,
                strategy_version=self.version,
                direction=DirectionEnum.SHORT,
                timeframe=timeframe,
                entry_price=current_price,
                stop_loss=stop_loss,
                target=target,
                confidence=0.74,
                supporting_evidence=[
                    f"Price broke out below 15m Opening Range Low ({orb_low:.2f})",
                    f"Volume confirmation: {last['volume']:.0f} vs ORB avg {avg_vol:.0f}",
                ],
            )

        return None

