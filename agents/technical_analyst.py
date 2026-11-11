"""
Technical Analyst Specialist Agent
Evaluates multi-timeframe indicators (RSI, VWAP, Supertrend, Moving Averages) to provide advisory assessment.
"""

from typing import Dict
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument
from strategies.indicators import calculate_all_indicators


class TechnicalAnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="TechnicalAnalyst", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        if len(candles) < 20:
            return AgentAssessment(
                agent_name=self.name,
                stance="NEUTRAL",
                confidence=0.0,
                evidence=["Insufficient candle history for technical analysis"],
                timestamp=now,
            )

        df = calculate_all_indicators(candles)
        last = df.iloc[-1]

        price = float(last["close"])
        vwap_val = float(last["vwap"])
        rsi_val = float(last["rsi"])
        st_dir = int(last["supertrend_dir"])
        ema_9 = float(last["ema_9"])
        ema_21 = float(last["ema_21"])

        bullish_points = 0
        bearish_points = 0
        evidence = []

        # VWAP stance
        if price > vwap_val:
            bullish_points += 1
            evidence.append(f"Price ({price:.2f}) > VWAP ({vwap_val:.2f})")
        else:
            bearish_points += 1
            evidence.append(f"Price ({price:.2f}) < VWAP ({vwap_val:.2f})")

        # Supertrend stance
        if st_dir == 1:
            bullish_points += 1
            evidence.append("Supertrend is bullish (+1)")
        else:
            bearish_points += 1
            evidence.append("Supertrend is bearish (-1)")

        # EMA alignment
        if ema_9 > ema_21:
            bullish_points += 1
            evidence.append("9 EMA > 21 EMA")
        else:
            bearish_points += 1
            evidence.append("9 EMA < 21 EMA")

        # RSI momentum
        if rsi_val > 55.0:
            bullish_points += 1
            evidence.append(f"RSI ({rsi_val:.1f}) in bullish territory")
        elif rsi_val < 45.0:
            bearish_points += 1
            evidence.append(f"RSI ({rsi_val:.1f}) in bearish territory")
        else:
            evidence.append(f"RSI ({rsi_val:.1f}) is neutral")

        total = bullish_points + bearish_points
        if bullish_points >= 3:
            stance = "BULLISH"
            confidence = round(bullish_points / total, 2)
        elif bearish_points >= 3:
            stance = "BEARISH"
            confidence = round(bearish_points / total, 2)
        else:
            stance = "NEUTRAL"
            confidence = 0.50

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=confidence,
            evidence=evidence,
            timestamp=now,
        )

