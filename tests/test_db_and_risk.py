"""
Unit tests for SQLite persistence, Central Risk Engine, ₹250 loss halt, and restart recovery.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.clock import clock
from backend.app.db.models import Base
from backend.app.models.domain import DecisionEnum, DirectionEnum, RiskStatusEnum
from risk.engine import CentralRiskEngine
from tests.test_proposals import create_valid_proposal

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
async def test_db():
    # Use in-memory SQLite for rapid, isolated testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_risk_session_initialization(test_db):
    engine = CentralRiskEngine()
    state = await engine.initialize_session(test_db)
    assert state.status == RiskStatusEnum.ACTIVE
    assert state.net_pnl == 0.0
    assert state.starting_capital == 25000.0


@pytest.mark.asyncio
async def test_risk_evaluation_approves_valid_proposal_during_market_hours(test_db):
    engine = CentralRiskEngine()
    await engine.initialize_session(test_db)

    # Set clock to regular trading hours: Wednesday 10:30 IST
    now = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(now)

    proposal = create_valid_proposal(DirectionEnum.LONG)
    proposal.market_data.as_of = now  # Fresh data (< 5s)

    decision, reason = await engine.evaluate_proposal(proposal, test_db)
    assert decision == DecisionEnum.APPROVED
    assert reason is None


@pytest.mark.asyncio
async def test_risk_evaluation_rejects_stale_data(test_db):
    engine = CentralRiskEngine()
    await engine.initialize_session(test_db)

    now = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(now)

    proposal = create_valid_proposal(DirectionEnum.LONG)
    # Market data is 15 seconds old (threshold is 5s)
    proposal.market_data.as_of = datetime(2026, 11, 4, 10, 29, 45, tzinfo=IST)

    decision, reason = await engine.evaluate_proposal(proposal, test_db)
    assert decision == DecisionEnum.REJECTED
    assert "stale" in reason.lower()


@pytest.mark.asyncio
async def test_daily_loss_limit_250_inr_hard_halt(test_db):
    engine = CentralRiskEngine()
    await engine.initialize_session(test_db)

    now = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(now)

    # Inject losses of ₹260.00 (Breaches ₹250 limit)
    state = await engine.update_pnl(realized_pnl=-240.0, unrealized_pnl=-10.0, charges=10.0, db=test_db)

    assert state.net_pnl == -260.0
    assert state.status == RiskStatusEnum.HALTED
    assert "Daily loss limit" in state.halt_reason

    # Verify that all subsequent proposals are rejected
    proposal = create_valid_proposal(DirectionEnum.LONG)
    proposal.market_data.as_of = now
    decision, reason = await engine.evaluate_proposal(proposal, test_db)

    assert decision == DecisionEnum.REJECTED
    assert "HALTED" in reason


@pytest.mark.asyncio
async def test_halt_persists_across_system_restarts(test_db):
    # 1. First engine instance experiences a loss breach and halts
    engine_1 = CentralRiskEngine()
    await engine_1.initialize_session(test_db)
    await engine_1.update_pnl(realized_pnl=-260.0, unrealized_pnl=0.0, charges=0.0, db=test_db)
    assert engine_1.state.status == RiskStatusEnum.HALTED

    # 2. Simulate application restart: instantiate brand new engine_2 connecting to same database
    engine_2 = CentralRiskEngine()
    recovered_state = await engine_2.initialize_session(test_db)

    # Invariant: Halt state must be preserved from DB
    assert recovered_state.status == RiskStatusEnum.HALTED
    assert recovered_state.net_pnl == -260.0


@pytest.mark.asyncio
async def test_emergency_kill_switch(test_db):
    engine = CentralRiskEngine()
    await engine.initialize_session(test_db)

    now = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(now)

    # Activate kill switch
    await engine.trigger_kill_switch("Manual emergency stop by operator", test_db)
    assert engine.kill_switch_active is True

    # Proposals must be rejected
    proposal = create_valid_proposal(DirectionEnum.LONG)
    proposal.market_data.as_of = now
    decision, reason = await engine.evaluate_proposal(proposal, test_db)

    assert decision == DecisionEnum.REJECTED
    assert "Kill Switch" in reason

    # Reset kill switch
    await engine.reset_kill_switch("All systems verified clear", test_db)
    assert engine.kill_switch_active is False

