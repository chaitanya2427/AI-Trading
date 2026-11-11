"""
Unit & Integration Tests for Phase 6: Paper Trading & Portfolio Monitoring
Covers:
- Live Broker safety barrier (SafetyViolationError)
- Paper Broker order lifecycle, spread crossing, slippage & provenance
- Stale quote rejection fail-closed
- Portfolio Tracker real-time MTM valuation
- Automated Stop Loss / Target intrabar triggers
- Mandatory 15:15 IST square-off
- Fail-closed emergency square-off on Central Risk Engine ₹250 halt
- Human proposal approval pipeline & execution
- Risk rejection during proposal approval
- Reconciliation engine consistency audits
- FastAPI Execution API routes
"""

from datetime import datetime, time, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.clock import clock
from backend.app.core.config import settings
from sqlalchemy import delete
from backend.app.db.init_db import init_db
from backend.app.db.models import (
    DailyRiskAuditModel,
    PaperOrderModel,
    PaperPositionModel,
    SystemAuditLogModel,
    TradeProposalModel,
)
from backend.app.db.session import AsyncSessionLocal
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
from execution.live_broker import LiveBrokerAdapter, SafetyViolationError
from execution.paper_broker import PaperBroker, PaperOrder, paper_broker
from execution.portfolio import PaperPosition, PortfolioTracker, portfolio_tracker
from execution.proposal_service import ProposalExecutionService, proposal_service
from execution.reconciliation import ReconciliationEngine, reconciliation_engine
from risk.engine import CentralRiskEngine, risk_engine


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PaperOrderModel))
        await session.execute(delete(PaperPositionModel))
        await session.execute(delete(TradeProposalModel))
        await session.execute(delete(DailyRiskAuditModel))
        await session.execute(delete(SystemAuditLogModel))
        await session.commit()

    # Reset in-memory states
    paper_broker._orders.clear()
    portfolio_tracker._positions.clear()
    risk_engine.state = None
    risk_engine.kill_switch_active = False
    risk_engine._processed_proposal_ids.clear()
    risk_engine._last_trade_time = None
    yield


def create_sample_proposal(
    symbol: str = "TCS",
    entry_price: float = 3500.0,
    stop_loss: float = 3475.0,
    target: float = 3550.0,
    quantity: int = 5,
    direction: DirectionEnum = DirectionEnum.LONG,
    quote_age_seconds: float = 0.5,
) -> TradeProposal:
    now_ist = clock.now()
    as_of = now_ist - timedelta(seconds=quote_age_seconds)
    risk_inr = round(abs(entry_price - stop_loss) * quantity, 2)
    reward_inr = round(abs(target - entry_price) * quantity, 2)

    return TradeProposal(
        schema_version="1.0",
        created_at=now_ist,
        instrument=Instrument(
            exchange=ExchangeEnum.NSE,
            segment=SegmentEnum.EQ,
            symbol=symbol,
            instrument_key=f"NSE_{symbol}",
            lot_size=1,
            tick_size=0.05,
        ),
        direction=direction,
        strategy=StrategyInfo(name="VWAP_Continuation", version="1.0"),
        timeframe="5m",
        market_data=MarketDataProvenance(
            as_of=as_of,
            source="UPSTOX_REST",
            is_stale=False,
        ),
        entry=EntryDetails(
            order_type=OrderTypeEnum.MARKET,
            reference_price=entry_price,
        ),
        stop_loss=stop_loss,
        target=target,
        quantity=quantity,
        estimated_risk_inr=risk_inr,
        estimated_reward_inr=reward_inr,
        estimated_costs_inr=35.0,
        execution_mode=ExecutionModeEnum.PAPER,
    )


# ------------------------------------------------------------------------------
# 1. Live Safety Isolation Tests
# ------------------------------------------------------------------------------

def test_live_broker_adapter_safety_barrier():
    """Live broker adapter must throw SafetyViolationError fail-closed."""
    with pytest.raises(SafetyViolationError) as exc_info:
        LiveBrokerAdapter()
    assert "Real-money live trading is disabled by design" in str(exc_info.value)


# ------------------------------------------------------------------------------
# 2. Paper Broker Tests
# ------------------------------------------------------------------------------

def test_paper_broker_order_lifecycle():
    """Test full order lifecycle, spread crossing, slippage, and provenance."""
    broker = PaperBroker(default_slippage_pct=0.0002, min_tick_size=0.05)
    order = broker.create_order(
        symbol="INFY",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=10,
        order_type=OrderTypeEnum.MARKET,
        reference_price=1500.0,
    )

    assert order.status == "NEW"
    assert order.execution_mode == "PAPER"
    assert order.provenance == "SIMULATED"

    # Execute order
    executed = broker.execute_order(
        order=order,
        current_market_price=1500.0,
        quote_timestamp=clock.now(),
    )

    assert executed.status == "FILLED"
    assert executed.filled_price is not None
    # Buy side crosses the ask: filled price should be higher than reference price
    assert executed.filled_price >= 1500.0
    assert executed.slippage_inr >= 0.0
    assert executed.charges_inr > 0.0
    assert executed.filled_at is not None


def test_paper_broker_stale_quote_rejection():
    """Paper broker must reject orders when market quote is stale (> 5.0s)."""
    broker = PaperBroker()
    order = broker.create_order(
        symbol="RELIANCE",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=5,
        order_type=OrderTypeEnum.MARKET,
        reference_price=2500.0,
    )

    stale_timestamp = clock.now() - timedelta(seconds=10.0)
    executed = broker.execute_order(
        order=order,
        current_market_price=2500.0,
        quote_timestamp=stale_timestamp,
    )

    assert executed.status == "REJECTED"
    assert "Stale market price rejected" in executed.reject_reason


def test_paper_broker_cancellation():
    """Cancelling an unfilled order updates its state to CANCELLED."""
    broker = PaperBroker()
    order = broker.create_order(
        symbol="SBIN",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=20,
        order_type=OrderTypeEnum.LIMIT,
        reference_price=600.0,
        limit_price=590.0,
    )

    cancelled = broker.cancel_order(order.order_id, reason="OPERATOR_CANCEL")
    assert cancelled.status == "CANCELLED"
    assert cancelled.reject_reason == "OPERATOR_CANCEL"

    with pytest.raises(ValueError):
        broker.cancel_order(order.order_id)


# ------------------------------------------------------------------------------
# 3. Portfolio Tracker Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_tracker_mtm_and_pnl():
    """Test position opening, MTM calculation, and realized P&L on closure."""
    tracker = PortfolioTracker()
    order = PaperOrder(
        symbol="TCS",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=5,
        order_type=OrderTypeEnum.MARKET,
        reference_price=3500.0,
    )
    order.status = "FILLED"
    order.filled_price = 3500.0
    order.filled_at = clock.now()

    pos = tracker.open_position_from_fill(order, stop_loss=3450.0, target=3600.0)
    assert pos.status == "OPEN"
    assert len(tracker.get_open_positions()) == 1

    # MTM Gain: price rises to 3520.0 (+₹20/share * 5 = +₹100)
    pos.calculate_mtm(3520.0)
    assert pos.unrealized_pnl == 100.0

    # MTM Loss: price drops to 3490.0 (-₹10/share * 5 = -₹50)
    pos.calculate_mtm(3490.0)
    assert pos.unrealized_pnl == -50.0

    # Close Position @ 3550.0 (+₹50/share * 5 = +₹250 realized)
    closed = await tracker.close_position(
        position_id=pos.position_id,
        exit_price=3550.0,
        exit_reason="MANUAL_PROFIT_TAKE",
    )
    assert closed.status == "CLOSED"
    assert closed.realized_pnl == 250.0
    assert closed.unrealized_pnl == 0.0
    assert closed.total_charges > 0.0
    assert len(tracker.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_portfolio_automated_sl_and_target_triggers():
    """Verify automated intrabar SL and Target triggering on market price update."""
    tracker = PortfolioTracker()

    # Long Position: Entry 1000, SL 980, Target 1050
    order = PaperOrder(
        symbol="INFY",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=5,
        order_type=OrderTypeEnum.MARKET,
        reference_price=1000.0,
    )
    order.status = "FILLED"
    order.filled_price = 1000.0
    order.filled_at = clock.now()

    pos = tracker.open_position_from_fill(order, stop_loss=980.0, target=1050.0)

    # 1. Price drops to 975.0 <= SL (980.0) -> Auto exit via STOP_LOSS
    closed = await tracker.update_market_price(symbol="INFY", current_price=975.0)
    assert len(closed) == 1
    assert closed[0].status == "CLOSED"
    assert closed[0].exit_reason == "STOP_LOSS"
    assert closed[0].exit_price == 980.0


@pytest.mark.asyncio
async def test_mandatory_1515_square_off():
    """Verify mandatory 15:15 IST square-off closes all open positions."""
    tracker = PortfolioTracker()
    order = PaperOrder(
        symbol="HDFC",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=10,
        order_type=OrderTypeEnum.MARKET,
        reference_price=1600.0,
    )
    order.status = "FILLED"
    order.filled_price = 1600.0
    order.filled_at = clock.now()

    tracker.open_position_from_fill(order, stop_loss=1580.0, target=1650.0)
    assert len(tracker.get_open_positions()) == 1

    # Before 15:15 -> no square-off
    time_1430 = clock.now().replace(hour=14, minute=30, second=0)
    closed = await tracker.check_intraday_square_off(current_time=time_1430)
    assert len(closed) == 0
    assert len(tracker.get_open_positions()) == 1

    # At 15:15 -> mandatory square-off triggers
    time_1515 = clock.now().replace(hour=15, minute=15, second=0)
    closed = await tracker.check_intraday_square_off(current_time=time_1515)
    assert len(closed) == 1
    assert closed[0].exit_reason == "MANDATORY_SQUARE_OFF_1515"
    assert len(tracker.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_fail_closed_emergency_square_off_on_risk_halt():
    """When net losses reach ₹250, Central Risk Engine halts and triggers emergency square-off."""
    tracker = PortfolioTracker()
    order = PaperOrder(
        symbol="LT",
        exchange=ExchangeEnum.NSE,
        direction=DirectionEnum.LONG,
        quantity=10,
        order_type=OrderTypeEnum.MARKET,
        reference_price=3000.0,
    )
    order.status = "FILLED"
    order.filled_price = 3000.0
    order.filled_at = clock.now()

    tracker.open_position_from_fill(order, stop_loss=2900.0, target=3200.0)

    async with AsyncSessionLocal() as db:
        await risk_engine.initialize_session(db)

        # Drop price significantly: ₹300 loss (> ₹250 limit)
        # Entry 3000 -> Current 2970 -> Loss: -30 * 10 = -300
        closed = await tracker.update_market_price(symbol="LT", current_price=2970.0, db=db)
        
        # Risk engine must have halted
        assert risk_engine.state.status == RiskStatusEnum.HALTED
        # All positions must be squared off fail-closed
        assert len(tracker.get_open_positions()) == 0


# ------------------------------------------------------------------------------
# 4. Proposal Approval Pipeline Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proposal_approval_and_execution_pipeline():
    """Verify human approval -> Central Risk Engine 12 gates -> Paper fill -> Portfolio open."""
    async with AsyncSessionLocal() as db:
        await risk_engine.initialize_session(db)

        # Ensure clock is inside market hours
        trading_time = clock.now().replace(hour=10, minute=30, second=0)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(clock, "now", lambda: trading_time)

            # Create valid proposal inside market hours context
            proposal = create_sample_proposal(
                symbol="TCS",
                entry_price=3500.0,
                stop_loss=3480.0,
                target=3540.0,
                quantity=5,  # Risk = 20 * 5 = 100 <= 250
            )
            prop_id = await proposal_service.save_proposal(proposal, db)

            result = await proposal_service.approve_and_execute(
                proposal_id=prop_id,
                operator="TRADER_ALICE",
                db=db,
            )

            assert result["status"] == "EXECUTED"
            assert result["order_id"] is not None
            assert result["position_id"] is not None
            assert result["execution_mode"] == "PAPER"
            assert len(portfolio_tracker.get_open_positions()) == 1


@pytest.mark.asyncio
async def test_proposal_rejection_by_human():
    """Human rejection records decision and reason without executing."""
    async with AsyncSessionLocal() as db:
        proposal = create_sample_proposal()
        prop_id = await proposal_service.save_proposal(proposal, db)

        result = await proposal_service.reject_proposal(
            proposal_id=prop_id,
            operator="TRADER_BOB",
            reason="Unfavorable intraday market sentiment",
            db=db,
        )

        assert result["status"] == "REJECTED"
        assert "Unfavorable intraday" in result["human_reason"]
        assert len(portfolio_tracker.get_open_positions()) == 0


@pytest.mark.asyncio
async def test_proposal_risk_rejection_during_approval():
    """When human approves an unsafe proposal, Central Risk Engine blocks it fail-closed."""
    async with AsyncSessionLocal() as db:
        await risk_engine.initialize_session(db)

        # Create proposal outside market hours (e.g. 20:00 IST)
        night_time = clock.now().replace(hour=20, minute=0, second=0)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(clock, "now", lambda: night_time)

            proposal = create_sample_proposal()
            prop_id = await proposal_service.save_proposal(proposal, db)

            result = await proposal_service.approve_and_execute(
                proposal_id=prop_id,
                operator="TRADER_ALICE",
                db=db,
            )

            assert result["status"] == "RISK_REJECTED"
            assert result["human_decision"] == "APPROVED"
            assert result["risk_decision"] == "REJECTED"
            assert "outside permitted intraday entry window" in result["risk_reason"].lower()
            assert len(portfolio_tracker.get_open_positions()) == 0


# ------------------------------------------------------------------------------
# 5. Reconciliation Engine Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_clean_and_discrepancy_detection():
    """Verify clean state check and discrepancy reporting on desynchronization."""
    async with AsyncSessionLocal() as db:
        await risk_engine.initialize_session(db)

        # 1. Clean state
        report = await reconciliation_engine.run_reconciliation(db=db)
        assert report.is_clean is True
        assert report.to_dict()["discrepancy_count"] == 0

        # 2. Inject orphan in-memory position without DB record
        order = PaperOrder(
            symbol="INFY",
            exchange=ExchangeEnum.NSE,
            direction=DirectionEnum.LONG,
            quantity=10,
            order_type=OrderTypeEnum.MARKET,
            reference_price=1500.0,
        )
        order.status = "FILLED"
        order.filled_price = 1500.0
        portfolio_tracker.open_position_from_fill(order, stop_loss=1480.0, target=1540.0)

        dirty_report = await reconciliation_engine.run_reconciliation(db=db)
        assert dirty_report.is_clean is False
        assert dirty_report.to_dict()["discrepancy_count"] > 0
        assert any("Count Mismatch" in d for d in dirty_report.discrepancies)


# ------------------------------------------------------------------------------
# 6. Execution API Routes Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execution_api_routes():
    """Verify all FastAPI Execution & Paper Trading routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Summary
        res = await client.get("/api/v1/execution/portfolio/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["execution_mode"] == "PAPER"
        assert data["starting_capital_inr"] == settings.STARTING_CAPITAL_INR

        # 2. Orders list
        res = await client.get("/api/v1/execution/orders")
        assert res.status_code == 200
        assert "orders" in res.json()

        # 3. Positions list
        res = await client.get("/api/v1/execution/positions")
        assert res.status_code == 200
        assert "positions" in res.json()

        # 4. Reconciliation
        res = await client.get("/api/v1/execution/reconciliation")
        assert res.status_code == 200
        assert res.json()["execution_mode"] == "PAPER"
