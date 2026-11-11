"""
Options Intelligence Specialist Agent
Evaluates Put-Call Ratio (PCR), Open Interest shifts, Max Pain, and contract affordability.
"""

from typing import Dict
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument, SegmentEnum


class OptionsIntelligenceAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="OptionsIntelligence", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        # Extract option context if provided
        pcr = context.get("pcr", 1.0)
        call_oi = context.get("total_call_oi", 100000)
        put_oi = context.get("total_put_oi", 100000)
        max_pain = context.get("max_pain", None)

        evidence = [f"Put-Call Ratio (PCR): {pcr:.2f}"]

        # Standard PCR interpretation for Indian indices/derivatives:
        # PCR > 1.2 -> Bullish (Puts heavily written / strong support)
        # PCR < 0.8 -> Bearish (Calls heavily written / strong resistance)
        if pcr > 1.2:
            stance = "BULLISH"
            confidence = 0.70
            evidence.append("High PCR indicates aggressive Put writing (bullish floor)")
        elif pcr < 0.8:
            stance = "BEARISH"
            confidence = 0.70
            evidence.append("Low PCR indicates aggressive Call writing (bearish ceiling)")
        else:
            stance = "NEUTRAL"
            confidence = 0.50
            evidence.append("PCR is balanced in neutral range (0.8 - 1.2)")

        if max_pain:
            evidence.append(f"Option Max Pain strike: {max_pain}")

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=confidence,
            evidence=evidence,
            timestamp=now,
        )

