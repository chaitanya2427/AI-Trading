"""
Unit tests for the Multi-Agent Specialist Advisory Framework and Orchestrator.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from agents.base import BaseAgent
from agents.market_microstructure import MarketMicrostructureAgent
from agents.options_intelligence import OptionsIntelligenceAgent
from agents.orchestrator import AgentOrchestrator
from agents.price_action import PriceActionAgent
from agents.quantitative_researcher import QuantitativeResearcherAgent
from agents.strategy_validator import StrategyValidatorAgent
from agents.technical_analyst import TechnicalAnalystAgent
from backend.app.models.domain import AgentAssessment, DirectionEnum, ExchangeEnum, Instrument, SegmentEnum
from tests.test_indicators import generate_sample_candles

IST = ZoneInfo("Asia/Kolkata")
TEST_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)


class SlowMockAgent(BaseAgent):
    """Simulates an agent that hangs and violates timeout."""
    def __init__(self):
        super().__init__(name="SlowAgent", timeout_seconds=0.1)

    async def _evaluate(self, candles, instrument, context):
        await asyncio.sleep(0.5)
        return AgentAssessment(
            agent_name=self.name,
            stance="BULLISH",
            confidence=0.9,
            evidence=["Should not be reached"],
            timestamp=datetime.now(IST),
        )


@pytest.mark.asyncio
async def test_agent_timeout_isolation():
    agent = SlowMockAgent()
    df = generate_sample_candles(n=10)
    # Must fail safely with NO_SIGNAL and not hang the process
    assessment = await agent.assess(df, TEST_INST)
    assert assessment.stance == "NO_SIGNAL"
    assert assessment.confidence == 0.0
    assert "timeout" in assessment.evidence[0].lower()


@pytest.mark.asyncio
async def test_technical_analyst_agent():
    agent = TechnicalAnalystAgent()
    df = generate_sample_candles(n=40, trend=1.0)
    assessment = await agent.assess(df, TEST_INST)

    assert assessment.agent_name == "TechnicalAnalyst"
    assert assessment.stance in ("BULLISH", "BEARISH", "NEUTRAL")
    assert 0.0 <= assessment.confidence <= 1.0
    assert len(assessment.evidence) > 0


@pytest.mark.asyncio
async def test_price_action_agent():
    agent = PriceActionAgent()
    df = generate_sample_candles(n=25, trend=0.5)
    assessment = await agent.assess(df, TEST_INST)

    assert assessment.agent_name == "PriceActionAnalyst"
    assert assessment.stance in ("BULLISH", "BEARISH", "NEUTRAL")
    assert len(assessment.evidence) > 0


@pytest.mark.asyncio
async def test_quant_researcher_agent():
    agent = QuantitativeResearcherAgent()
    df = generate_sample_candles(n=35)
    assessment = await agent.assess(df, TEST_INST)

    assert assessment.agent_name == "QuantResearcher"
    assert "Z-score" in assessment.evidence[0]


@pytest.mark.asyncio
async def test_options_intelligence_agent():
    agent = OptionsIntelligenceAgent()
    df = generate_sample_candles(n=10)
    # High PCR -> Bullish
    assessment = await agent.assess(df, TEST_INST, context={"pcr": 1.45})
    assert assessment.stance == "BULLISH"
    assert assessment.confidence == 0.70


@pytest.mark.asyncio
async def test_microstructure_agent():
    agent = MarketMicrostructureAgent()
    df = generate_sample_candles(n=10)
    book = {
        "bids": [{"price": 100.0, "quantity": 1000}],
        "asks": [{"price": 100.1, "quantity": 200}],
        "spread": 0.1,
    }
    assessment = await agent.assess(df, TEST_INST, context={"order_book": book})
    assert assessment.stance == "BULLISH"
    assert assessment.confidence > 0.50


@pytest.mark.asyncio
async def test_strategy_validator_contradiction_detection():
    validator = StrategyValidatorAgent()
    df = generate_sample_candles(n=10)

    # Injected bearish specialist opinions
    bearish_assessments = [
        AgentAssessment(agent_name="TA", stance="BEARISH", confidence=0.8, evidence=[], timestamp=datetime.now(IST)),
        AgentAssessment(agent_name="PA", stance="BEARISH", confidence=0.8, evidence=[], timestamp=datetime.now(IST)),
    ]

    # Propose LONG -> Must detect contradiction
    assessment = await validator.assess(
        df,
        TEST_INST,
        context={"assessments": bearish_assessments, "proposed_direction": DirectionEnum.LONG},
    )

    assert "CONTRADICTION DETECTED" in assessment.evidence[1]
    assert assessment.stance == "BEARISH"


@pytest.mark.asyncio
async def test_agent_orchestrator():
    orchestrator = AgentOrchestrator()
    df = generate_sample_candles(n=40)
    results = await orchestrator.run_all(df, TEST_INST, proposed_direction=DirectionEnum.LONG)

    # 5 domain specialists + 1 StrategyValidator = 6 total assessments
    assert len(results) == 6
    names = {a.agent_name for a in results}
    assert "TechnicalAnalyst" in names
    assert "PriceActionAnalyst" in names
    assert "QuantResearcher" in names
    assert "OptionsIntelligence" in names
    assert "MicrostructureAnalyst" in names
    assert "StrategyValidator" in names

