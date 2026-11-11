"""
Quantitative Researcher Specialist Agent
Computes statistical metrics (z-scores of returns, volatility percentiles, momentum autocorrelation).
"""

from typing import Dict
import numpy as np
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument


class QuantitativeResearcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="QuantResearcher", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        if len(candles) < 30:
            return AgentAssessment(
                agent_name=self.name,
                stance="NEUTRAL",
                confidence=0.0,
                evidence=["Insufficient sample size for statistical distribution metrics"],
                timestamp=now,
            )

        returns = candles["close"].pct_change().dropna()
        recent_ret = returns.iloc[-1]
        mean_ret = returns.mean()
        std_ret = max(1e-6, returns.std())
        z_score = (recent_ret - mean_ret) / std_ret

        # Volatility percentile
        rolling_std = returns.rolling(10).std()
        current_vol = rolling_std.iloc[-1]
        vol_pct = (rolling_std < current_vol).mean() * 100.0

        evidence = [
            f"1-bar return Z-score: {z_score:.2f}",
            f"Current volatility is in the {vol_pct:.0f}th percentile of the session",
        ]

        if z_score > 1.5:
            stance = "BULLISH"
            confidence = min(0.85, 0.50 + abs(z_score) * 0.1)
            evidence.append("Statistically significant positive momentum thrust")
        elif z_score < -1.5:
            stance = "BEARISH"
            confidence = min(0.85, 0.50 + abs(z_score) * 0.1)
            evidence.append("Statistically significant negative momentum thrust")
        else:
            stance = "NEUTRAL"
            confidence = 0.50
            evidence.append("Returns within normal Gaussian distribution envelope (|z| <= 1.5)")

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=round(confidence, 2),
            evidence=evidence,
            timestamp=now,
        )

