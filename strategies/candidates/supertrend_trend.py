"""
Strategy 5: Supertrend Volatility Following
Enters on directional flip of the ATR-based Supertrend indicator.
"""

from typing import Optional
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument
from strategies.base import BaseStrategy, StrategySignal
from strategies.indicators import calculate_all_indicators


class SupertrendStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="SUPERTREND", version="1.0", min_candles_required=20)

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
        st_val = float(last["supertrend"])
        st_dir_last = int(last["supertrend_dir"])
        st_dir_prev = int(prev["supertrend_dir"])
        atr_val = max(float(last["atr"]), instrument.tick_size * 5)

        # Bullish flip (-1 to +1)
        if st_dir_prev == -1 and st_dir_last == 1:
            stop_loss = round(st_val, 2)
            risk_dist = current_price - stop_loss
            if risk_dist <= 0:
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
                confidence=0.76,
                supporting_evidence=[
                    f"Supertrend flipped bullish (+1) at {current_price:.2f}",
                    f"Trailing band level established at {st_val:.2f}",
                ],
            )

        # Bearish flip (+1 to -1)
        if st_dir_prev == 1 and st_dir_last == -1:
            stop_loss = round(st_val, 2)
            risk_dist = stop_loss - current_price
            if risk_dist <= 0:
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
                confidence=0.76,
                supporting_evidence=[
                    f"Supertrend flipped bearish (-1) at {current_price:.2f}",
                    f"Trailing band level established at {st_val:.2f}",
                ],
            )

        return None

