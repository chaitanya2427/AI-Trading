"""
Integration tests for Trade Proposal Generation, Risk Evaluation, and Strategy APIs.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.adapters.instruments import instrument_master
from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.db.init_db import init_db
from backend.app.main import app
from backend.app.models.domain import DecisionEnum, DirectionEnum, ExchangeEnum, Instrument, SegmentEnum
from risk.engine import risk_engine
from strategies.base import StrategySignal
from strategies.proposal_generator import proposal_generator

IST = ZoneInfo("Asia/Kolkata")
TEST_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)


@pytest.fixture(autouse=True)
async def setup_environment():
    await init_db()
    instrument_master.initialize()


def test_proposal_generator_creates_valid_schema():
    now = datetime(2026, 11, 4, 10, 0, tzinfo=IST)
    clock.set_simulated_time(now)
    prov = validator.check_quote_freshness(now)

    signal = StrategySignal(
        strategy_name="VWAP_CONTINUATION",
        strategy_version="1.0",
        direction=DirectionEnum.LONG,
        timeframe="5m",
        entry_price=2500.0,
        stop_loss=2480.0,  # Stop dist = 20. Max risk = 250 -> 12 shares
        target=2540.0,
        confidence=0.75,
        supporting_evidence=["Bullish VWAP test"],
    )

    proposal = proposal_generator.create_proposal(
        signal=signal,
        instrument=TEST_INST,
        provenance=prov,
        available_capital=25000.0,
    )

    assert proposal is not None
    assert proposal.schema_version == "1.0"
    assert proposal.direction == DirectionEnum.LONG
    assert proposal.quantity == 10  # 10 shares * 2500 = 25000 max capital
    assert proposal.estimated_risk_inr == 200.0  # 10 * 20 = 200 (< 250 limit)
    assert proposal.estimated_costs_inr > 0.0


@pytest.mark.asyncio
async def test_api_list_strategies():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8


@pytest.mark.asyncio
async def test_api_evaluate_strategy_endpoint():
    # Set simulated time to regular market hours Wednesday 10:30 IST
    now = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(now)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/evaluate",
            json={"instrument_key": "NSE_EQ|INE002A01018", "timeframe": "5m"},
        )
        assert resp.status_code == 200
        proposals = resp.json()
        assert isinstance(proposals, list)
        for p in proposals:
            assert p["schema_version"] == "1.0"
            assert "estimated_risk_inr" in p
            assert p["estimated_risk_inr"] <= 250.0  # Must not exceed ₹250 limit!


@pytest.mark.asyncio
async def test_api_agent_assessment_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies/agents/assess?instrument_key=NSE_EQ|INE002A01018")
        assert resp.status_code == 200
        assessments = resp.json()
        assert len(assessments) == 6
        assert any(a["agent_name"] == "StrategyValidator" for a in assessments)

