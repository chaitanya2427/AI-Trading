"""
Strategy 1: VWAP Trend Continuation
Enters on intraday pullback to Volume Weighted Average Price with volume confirmation.
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import atr, calculate_all_indicators


class VWAPContinuationStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="VWAP_CONTINUATION", version="1.0", min_candles_required=20)

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
        vwap_val = float(last["vwap"])
        atr_val = max(float(last["atr"]), instrument.tick_size * 5)
        avg_vol = df["volume"].iloc[-20:].mean()

        # Bullish Pullback: Price above VWAP, prev touched near VWAP, current candle closed green
        if prev["low"] <= vwap_val * 1.002 and last["close"] > last["open"] and last["close"] > vwap_val:
            if last["volume"] > avg_vol * 0.8:
                stop_loss = round(min(prev["low"], vwap_val - 1.2 * atr_val), 2)
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
                    confidence=0.75,
                    supporting_evidence=[
                        f"Price tested VWAP ({vwap_val:.2f}) and confirmed bullish reversal",
                        f"Candle closed green above VWAP with healthy volume ({last['volume']:.0f} vs avg {avg_vol:.0f})",
                    ],
                )

        # Bearish Pullback: Price below VWAP, prev touched near VWAP, current candle closed red
        if prev["high"] >= vwap_val * 0.998 and last["close"] < last["open"] and last["close"] < vwap_val:
            if last["volume"] > avg_vol * 0.8:
                stop_loss = round(max(prev["high"], vwap_val + 1.2 * atr_val), 2)
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
                    confidence=0.75,
                    supporting_evidence=[
                        f"Price tested VWAP ({vwap_val:.2f}) from below and rejected",
                        f"Candle closed red below VWAP with volume confirmation ({last['volume']:.0f})",
                    ],
                )

        return None

