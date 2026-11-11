"""
Agent Orchestrator
Coordinates concurrent execution of specialist agents and synthesizes consensus through StrategyValidator.
"""

import asyncio
import logging
from typing import Dict, List, Optional
import pandas as pd

from agents.market_microstructure import MarketMicrostructureAgent
from agents.options_intelligence import OptionsIntelligenceAgent
from agents.price_action import PriceActionAgent
from agents.quantitative_researcher import QuantitativeResearcherAgent
from agents.strategy_validator import StrategyValidatorAgent
from agents.technical_analyst import TechnicalAnalystAgent
from backend.app.models.domain import AgentAssessment, DirectionEnum, Instrument

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Manages concurrent specialist agent execution with fail-safe boundaries."""

    def __init__(self):
        self.ta_agent = TechnicalAnalystAgent()
        self.pa_agent = PriceActionAgent()
        self.quant_agent = QuantitativeResearcherAgent()
        self.options_agent = OptionsIntelligenceAgent()
        self.micro_agent = MarketMicrostructureAgent()
        self.validator_agent = StrategyValidatorAgent()

    async def run_all(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Optional[Dict] = None,
        proposed_direction: Optional[DirectionEnum] = None,
    ) -> List[AgentAssessment]:
        """
        Runs all domain specialist agents concurrently, followed by the StrategyValidator.
        An exception in any single agent does not affect the others.
        """
        ctx = context or {}

        # Run domain specialists concurrently
        specialist_tasks = [
            self.ta_agent.assess(candles, instrument, ctx),
            self.pa_agent.assess(candles, instrument, ctx),
            self.quant_agent.assess(candles, instrument, ctx),
            self.options_agent.assess(candles, instrument, ctx),
            self.micro_agent.assess(candles, instrument, ctx),
        ]

        specialist_results = await asyncio.gather(*specialist_tasks, return_exceptions=False)
        assessments: List[AgentAssessment] = list(specialist_results)

        # Run StrategyValidator with synthesis context
        validator_ctx = {
            **ctx,
            "assessments": assessments,
            "proposed_direction": proposed_direction,
        }
        val_assessment = await self.validator_agent.assess(candles, instrument, validator_ctx)
        assessments.append(val_assessment)

        return assessments


agent_orchestrator = AgentOrchestrator()

