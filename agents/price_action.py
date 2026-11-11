"""
Price Action Specialist Agent
Evaluates swing structure (Higher-Highs / Lower-Lows) and candlestick patterns.
"""

from typing import Dict
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument


class PriceActionAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PriceActionAnalyst", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        if len(candles) < 10:
            return AgentAssessment(
                agent_name=self.name,
                stance="NEUTRAL",
                confidence=0.0,
                evidence=["Insufficient bars for price action evaluation"],
                timestamp=now,
            )

        last = candles.iloc[-1]
        prev = candles.iloc[-2]
        evidence = []

        # Candle body and wick calculations
        body = abs(last["close"] - last["open"])
        candle_range = max(0.01, last["high"] - last["low"])
        upper_wick = last["high"] - max(last["close"], last["open"])
        lower_wick = min(last["close"], last["open"]) - last["low"]

        # 1. Candlestick Anatomy
        is_hammer = lower_wick >= 2.0 * body and upper_wick <= 0.2 * body and last["close"] > last["open"]
        is_shooting_star = upper_wick >= 2.0 * body and lower_wick <= 0.2 * body and last["close"] < last["open"]
        is_bullish_engulfing = (
            prev["close"] < prev["open"]
            and last["close"] > last["open"]
            and last["close"] >= prev["open"]
            and last["open"] <= prev["close"]
        )

        # 2. Swing Structure over last 10 bars
        highs = candles["high"].iloc[-10:]
        lows = candles["low"].iloc[-10:]
        higher_highs = highs.iloc[-1] > highs.iloc[-5] and highs.iloc[-5] > highs.iloc[-10]
        higher_lows = lows.iloc[-1] > lows.iloc[-5] and lows.iloc[-5] > lows.iloc[-10]
        lower_highs = highs.iloc[-1] < highs.iloc[-5] and highs.iloc[-5] < highs.iloc[-10]
        lower_lows = lows.iloc[-1] < lows.iloc[-5] and lows.iloc[-5] < lows.iloc[-10]

        if higher_highs and higher_lows:
            evidence.append("Bullish swing structure: Higher Highs and Higher Lows confirmed")
            stance = "BULLISH"
            confidence = 0.75
        elif lower_highs and lower_lows:
            evidence.append("Bearish swing structure: Lower Highs and Lower Lows confirmed")
            stance = "BEARISH"
            confidence = 0.75
        elif is_hammer or is_bullish_engulfing:
            evidence.append("Bullish reversal candlestick pattern detected")
            stance = "BULLISH"
            confidence = 0.68
        elif is_shooting_star:
            evidence.append("Bearish shooting star rejection detected")
            stance = "BEARISH"
            confidence = 0.68
        else:
            evidence.append("Consolidation or indecisive price action")
            stance = "NEUTRAL"
            confidence = 0.50

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=confidence,
            evidence=evidence,
            timestamp=now,
        )

