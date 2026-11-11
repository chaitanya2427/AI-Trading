"""
Unit and Integration Tests for Central Risk Engine (12 Pre-Trade Gates, Halt, Persistence, Overrides).
"""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.db.init_db import init_db
from backend.app.db.models import Base
from backend.app.main import app
from backend.app.models.domain import (
    DecisionEnum,
    DirectionEnum,
    EntryDetails,
    ExchangeEnum,
    ExecutionModeEnum,
    Instrument,
    MarketDataProvenance,
    OrderTypeEnum,
    RiskStatusEnum,
    SegmentEnum,
    StrategyInfo,
    TradeProposal,
)
from risk.engine import CentralRiskEngine

IST = ZoneInfo("Asia/Kolkata")
TEST_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)


@pytest.fixture
async def isolated_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def make_proposal(
    direction=DirectionEnum.LONG,
    entry_price=2500.0,
    stop_loss=2480.0,
    target=2540.0,
    qty=5,
    risk_inr=100.0,
    age_seconds=1.0,
):
    now = clock.now()
    quote_time = now - timedelta(seconds=age_seconds)
    prov = MarketDataProvenance(as_of=quote_time, source="MARKET_FEED", is_stale=False)

    return TradeProposal(
        schema_version="1.0",
        proposal_id=uuid4(),
        created_at=now,
        instrument=TEST_INST,
        direction=direction,
        strategy=StrategyInfo(name="TEST_STRAT", version="1.0"),
        timeframe="5m",
        market_data=prov,
        entry=EntryDetails(order_type=OrderTypeEnum.LIMIT, reference_price=entry_price, limit_price=entry_price),
        stop_loss=stop_loss,
        target=target,
        quantity=qty,
        estimated_risk_inr=risk_inr,
        estimated_reward_inr=round(abs(target - entry_price) * qty, 2),
        estimated_costs_inr=20.0,
        execution_mode=ExecutionModeEnum.PAPER,
    )


@pytest.mark.asyncio
async def test_gate_1_deduplication(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    proposal = make_proposal()
    decision1, _ = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision1 == DecisionEnum.APPROVED

    # Submit exact same proposal again -> Duplicate check
    decision2, reason2 = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision2 == DecisionEnum.REJECTED
    assert "duplicate" in reason2.lower()


@pytest.mark.asyncio
async def test_gate_2_kill_switch_active(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    await engine.trigger_kill_switch("Operator Emergency Stop", isolated_db)
    proposal = make_proposal()
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)

    assert decision == DecisionEnum.REJECTED
    assert "kill switch" in reason.lower()


@pytest.mark.asyncio
async def test_gate_3_hard_250_loss_halt(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    # Inject losses of ₹255.00
    await engine.update_pnl_and_exposure(realized_pnl=-240.0, unrealized_pnl=-5.0, charges=10.0, open_positions_count=0, db=isolated_db)
    assert engine.state.status == RiskStatusEnum.HALTED

    proposal = make_proposal()
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "halted" in reason.lower()


@pytest.mark.asyncio
async def test_gate_4_market_clock_session(isolated_db):
    engine = CentralRiskEngine()
    # 15:05 IST (Past 15:00 intraday entry cutoff)
    clock.set_simulated_time(datetime(2026, 11, 4, 15, 5, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    proposal = make_proposal()
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "outside permitted intraday entry window" in reason.lower()


@pytest.mark.asyncio
async def test_gate_5_quote_freshness(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    # Quote is 8.0 seconds old (threshold is 5.0s)
    proposal = make_proposal(age_seconds=8.0)
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "stale" in reason.lower()


@pytest.mark.asyncio
async def test_gate_7_risk_reward_ratio(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    # Stop distance = 20, Target distance = 10 -> R:R = 0.5 (below 1:1.5 requirement)
    proposal = make_proposal(entry_price=2500.0, stop_loss=2480.0, target=2510.0, qty=5, risk_inr=100.0)
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "risk/reward" in reason.lower()


@pytest.mark.asyncio
async def test_gate_8_single_trade_risk_cap(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    # Risk = ₹300.00 (Exceeds ₹250 cap)
    proposal = make_proposal(entry_price=2500.0, stop_loss=2470.0, target=2560.0, qty=10, risk_inr=300.0)
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "ceiling" in reason.lower()


@pytest.mark.asyncio
async def test_gate_10_max_open_positions(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)

    # Max positions is 2; set open positions to 2
    await engine.update_pnl_and_exposure(0.0, 0.0, 0.0, open_positions_count=2, db=isolated_db)
    proposal = make_proposal()
    decision, reason = await engine.evaluate_proposal(proposal, isolated_db)
    assert decision == DecisionEnum.REJECTED
    assert "maximum simultaneous positions" in reason.lower()


@pytest.mark.asyncio
async def test_restart_persistence_tamper_resistance(isolated_db):
    # Session 1 halts due to loss
    engine_1 = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine_1.initialize_session(isolated_db)
    await engine_1.update_pnl_and_exposure(-260.0, 0.0, 0.0, 0, isolated_db)
    assert engine_1.state.status == RiskStatusEnum.HALTED

    # Simulate crash / reboot: instantiate brand-new engine_2
    engine_2 = CentralRiskEngine()
    recovered = await engine_2.initialize_session(isolated_db)
    assert recovered.status == RiskStatusEnum.HALTED
    assert recovered.net_pnl == -260.0


@pytest.mark.asyncio
async def test_audited_manual_override_flow(isolated_db):
    engine = CentralRiskEngine()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))
    await engine.initialize_session(isolated_db)
    await engine.update_pnl_and_exposure(-255.0, 0.0, 0.0, 0, isolated_db)
    assert engine.state.status == RiskStatusEnum.HALTED

    # Override without adequate rationale -> Rejected
    with pytest.raises(ValueError):
        await engine.apply_audited_override("OPERATOR_1", "short reason", isolated_db)

    # Override with proper rationale -> Succeeds
    ok = await engine.apply_audited_override(
        "OPERATOR_CHAITANYA",
        "Confirmed market dislocation cleared; authorizing 1 controlled scalp with tight stop.",
        isolated_db,
    )
    assert ok is True
    assert engine.state.status == RiskStatusEnum.ACTIVE


@pytest.mark.asyncio
async def test_risk_api_endpoints():
    await init_db()
    clock.set_simulated_time(datetime(2026, 11, 4, 10, 30, tzinfo=IST))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check /api/v1/risk/status
        resp = await client.get("/api/v1/risk/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "capital_metrics" in data
        assert data["capital_metrics"]["daily_loss_limit_inr"] == 250.0

        # Check /api/v1/risk/audit-logs
        log_resp = await client.get("/api/v1/risk/audit-logs")
        assert log_resp.status_code == 200
        logs = log_resp.json()
        assert isinstance(logs, list)
