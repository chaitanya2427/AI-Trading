"""
Strategy Validator & Cross-Agent Consensus Engine
Synthesizes independent specialist agent assessments, detects contradictions, and computes composite confidence.
"""

from typing import Dict, List, Tuple
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, DirectionEnum, Instrument


class StrategyValidatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="StrategyValidator", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        assessments: List[AgentAssessment] = context.get("assessments", [])
        proposed_direction: Optional[DirectionEnum] = context.get("proposed_direction")

        if not assessments:
            return AgentAssessment(
                agent_name=self.name,
                stance="NEUTRAL",
                confidence=0.50,
                evidence=["No specialist assessments provided for synthesis"],
                timestamp=now,
            )

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        conf_sum = 0.0
        evidence: List[str] = []

        for a in assessments:
            if a.stance == "BULLISH":
                bullish_count += 1
                conf_sum += a.confidence
            elif a.stance == "BEARISH":
                bearish_count += 1
                conf_sum += a.confidence
            else:
                neutral_count += 1
                conf_sum += a.confidence

        total = len(assessments)
        avg_conf = conf_sum / max(1, total)

        evidence.append(
            f"Agent Consensus Breakdown: {bullish_count} Bullish, {bearish_count} Bearish, {neutral_count} Neutral"
        )

        # Detect direct contradictions
        if proposed_direction == DirectionEnum.LONG and bearish_count >= 2:
            evidence.append("CONTRADICTION DETECTED: Proposed LONG conflicts with multiple bearish specialist agents")
            return AgentAssessment(
                agent_name=self.name,
                stance="BEARISH",
                confidence=0.80,
                evidence=evidence,
                timestamp=now,
            )
        elif proposed_direction == DirectionEnum.SHORT and bullish_count >= 2:
            evidence.append("CONTRADICTION DETECTED: Proposed SHORT conflicts with multiple bullish specialist agents")
            return AgentAssessment(
                agent_name=self.name,
                stance="BULLISH",
                confidence=0.80,
                evidence=evidence,
                timestamp=now,
            )

        # Consensus determination
        if bullish_count > bearish_count and bullish_count >= 2:
            stance = "BULLISH"
            final_conf = min(0.90, round(avg_conf + 0.1, 2))
            evidence.append("Multi-agent consensus confirms bullish market alignment")
        elif bearish_count > bullish_count and bearish_count >= 2:
            stance = "BEARISH"
            final_conf = min(0.90, round(avg_conf + 0.1, 2))
            evidence.append("Multi-agent consensus confirms bearish market alignment")
        else:
            stance = "NEUTRAL"
            final_conf = 0.50
            evidence.append("Mixed signals across specialist agents; consensus is neutral")

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=final_conf,
            evidence=evidence,
            timestamp=now,
        )

