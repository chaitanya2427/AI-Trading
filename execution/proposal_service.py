"""
Trade Proposal Human Approval & Execution Lifecycle Service
Enforces human review gate before risk engine validation and paper broker dispatch.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.core.logging import get_logger
from backend.app.db.models import PaperOrderModel, PaperPositionModel, TradeProposalModel
from backend.app.models.domain import (
    DecisionEnum,
    DirectionEnum,
    EntryDetails,
    ExchangeEnum,
    ExecutionModeEnum,
    Instrument,
    MarketDataProvenance,
    OrderTypeEnum,
    SegmentEnum,
    StrategyInfo,
    TradeProposal,
)
from execution.paper_broker import paper_broker
from execution.portfolio import portfolio_tracker
from risk.engine import risk_engine

logger = get_logger("execution.proposal_service")


class ProposalExecutionService:
    """Manages the full lifecycle from Trade Proposal to Approval, Risk Check, and Paper Execution."""

    async def save_proposal(self, proposal: TradeProposal, db: AsyncSession) -> str:
        """Persists a newly generated Trade Proposal in PENDING state."""
        prop_id = str(proposal.proposal_id)
        entry_price = proposal.entry.limit_price or proposal.entry.reference_price

        model = TradeProposalModel(
            proposal_id=prop_id,
            created_at=proposal.created_at,
            symbol=proposal.instrument.symbol,
            exchange=proposal.instrument.exchange.value,
            segment=proposal.instrument.segment.value,
            direction=proposal.direction.value,
            strategy_name=proposal.strategy.name,
            timeframe=proposal.timeframe,
            entry_price=entry_price,
            stop_loss=proposal.stop_loss,
            target=proposal.target,
            quantity=proposal.quantity,
            estimated_risk_inr=proposal.estimated_risk_inr,
            estimated_reward_inr=proposal.estimated_reward_inr,
            estimated_costs_inr=proposal.estimated_costs_inr,
            risk_decision="PENDING",
            human_decision="PENDING",
            execution_mode=ExecutionModeEnum.PAPER.value,
            raw_payload=proposal.model_dump(mode="json"),
        )
        db.add(model)
        await db.commit()
        logger.info("Persisted Trade Proposal %s for %s (%s)", prop_id, proposal.instrument.symbol, proposal.direction.value)
        return prop_id

    async def list_proposals(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        db: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves list of proposals with human/risk decisions."""
        if db is None:
            return []

        stmt = select(TradeProposalModel).order_by(desc(TradeProposalModel.created_at)).limit(limit)
        if status:
            stmt = stmt.where(TradeProposalModel.human_decision == status)

        res = await db.execute(stmt)
        records = res.scalars().all()
        return [
            {
                "proposal_id": r.proposal_id,
                "created_at": r.created_at.isoformat(),
                "symbol": r.symbol,
                "exchange": r.exchange,
                "segment": r.segment,
                "direction": r.direction,
                "strategy_name": r.strategy_name,
                "entry_price": r.entry_price,
                "stop_loss": r.stop_loss,
                "target": r.target,
                "quantity": r.quantity,
                "estimated_risk_inr": r.estimated_risk_inr,
                "estimated_reward_inr": r.estimated_reward_inr,
                "estimated_costs_inr": r.estimated_costs_inr,
                "risk_decision": r.risk_decision,
                "risk_reason": r.risk_reason,
                "human_decision": r.human_decision,
                "human_reason": r.human_reason,
                "execution_mode": r.execution_mode,
            }
            for r in records
        ]

    async def approve_and_execute(
        self,
        proposal_id: str,
        operator: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Operator reviews and approves a Trade Proposal.
        Workflow:
        1. Human Approval logged.
        2. Central Risk Engine evaluates proposal against 12 pre-trade gates.
        3. If Risk Engine rejects -> state is recorded and execution stopped.
        4. If Risk Engine accepts -> Paper Broker executes order -> Portfolio records position.
        """
        stmt = select(TradeProposalModel).where(TradeProposalModel.proposal_id == proposal_id)
        res = await db.execute(stmt)
        model = res.scalar_one_or_none()

        if not model:
            raise ValueError(f"Proposal {proposal_id} not found.")

        if model.human_decision != "PENDING":
            raise ValueError(f"Proposal {proposal_id} already has decision: {model.human_decision}")

        # Record Human Approval
        model.human_decision = "APPROVED"
        model.human_reason = f"Approved by operator {operator}"
        await db.commit()

        # Reconstruct Domain TradeProposal
        raw = model.raw_payload
        proposal = TradeProposal(
            schema_version="1.0",
            proposal_id=UUID(model.proposal_id),
            created_at=datetime.fromisoformat(raw["created_at"]) if isinstance(raw["created_at"], str) else raw["created_at"],
            instrument=Instrument(**raw["instrument"]),
            direction=DirectionEnum(raw["direction"]),
            strategy=StrategyInfo(**raw["strategy"]),
            timeframe=raw["timeframe"],
            market_data=MarketDataProvenance(**raw["market_data"]),
            entry=EntryDetails(**raw["entry"]),
            stop_loss=float(raw["stop_loss"]),
            target=float(raw["target"]),
            quantity=int(raw["quantity"]),
            estimated_risk_inr=float(raw["estimated_risk_inr"]),
            estimated_reward_inr=float(raw["estimated_reward_inr"]),
            estimated_costs_inr=float(raw["estimated_costs_inr"]),
            execution_mode=ExecutionModeEnum.PAPER,
        )

        # Non-Bypassable Central Risk Engine Evaluation
        decision, reason = await risk_engine.evaluate_order_proposal(proposal, db)
        model.risk_decision = decision.value
        model.risk_reason = reason
        await db.commit()

        if decision != DecisionEnum.APPROVED:
            logger.warning(
                "Proposal %s REJECTED by Central Risk Engine: %s",
                proposal_id,
                reason,
            )
            return {
                "status": "RISK_REJECTED",
                "proposal_id": proposal_id,
                "human_decision": "APPROVED",
                "risk_decision": "REJECTED",
                "risk_reason": reason,
            }

        # Submit to Paper Broker for Execution
        order = paper_broker.create_order(
            symbol=proposal.instrument.symbol,
            exchange=proposal.instrument.exchange,
            direction=proposal.direction,
            quantity=proposal.quantity,
            order_type=proposal.entry.order_type,
            reference_price=proposal.entry.reference_price,
            limit_price=proposal.entry.limit_price,
            proposal_id=proposal_id,
        )

        # Execute immediately against authentic market reference price
        paper_broker.execute_order(
            order=order,
            current_market_price=proposal.entry.reference_price,
            quote_timestamp=proposal.market_data.as_of,
            instrument=proposal.instrument,
        )

        # Persist Paper Order
        order_model = PaperOrderModel(
            order_id=order.order_id,
            proposal_id=proposal_id,
            created_at=order.created_at,
            symbol=order.symbol,
            exchange=order.exchange.value if isinstance(order.exchange, ExchangeEnum) else str(order.exchange),
            direction=order.direction.value if isinstance(order.direction, DirectionEnum) else str(order.direction),
            order_type=order.order_type.value if isinstance(order.order_type, OrderTypeEnum) else str(order.order_type),
            quantity=order.quantity,
            reference_price=order.reference_price,
            filled_price=order.filled_price,
            slippage_inr=order.slippage_inr,
            charges_inr=order.charges_inr,
            status=order.status,
            reject_reason=order.reject_reason,
        )
        db.add(order_model)
        await db.commit()

        if order.status != "FILLED":
            return {
                "status": "EXECUTION_REJECTED",
                "proposal_id": proposal_id,
                "order_id": order.order_id,
                "reason": order.reject_reason,
            }

        # Open Position in Portfolio Tracker
        pos = portfolio_tracker.open_position_from_fill(
            order=order,
            stop_loss=proposal.stop_loss,
            target=proposal.target,
            instrument=proposal.instrument,
            db=db,
        )

        # Persist Initial Position in DB
        pos_model = PaperPositionModel(
            position_id=pos.position_id,
            symbol=pos.symbol,
            exchange=pos.exchange.value if isinstance(pos.exchange, ExchangeEnum) else str(pos.exchange),
            direction=pos.direction.value if isinstance(pos.direction, DirectionEnum) else str(pos.direction),
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            stop_loss=pos.stop_loss,
            target=pos.target,
            current_price=pos.current_price,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            total_charges=pos.total_charges,
            status="OPEN",
        )
        db.add(pos_model)
        await db.commit()

        # Update Risk Engine Exposure
        await portfolio_tracker.sync_to_risk_engine(db)

        return {
            "status": "EXECUTED",
            "proposal_id": proposal_id,
            "order_id": order.order_id,
            "position_id": pos.position_id,
            "filled_price": order.filled_price,
            "quantity": order.quantity,
            "slippage_inr": order.slippage_inr,
            "charges_inr": order.charges_inr,
            "execution_mode": "PAPER",
        }

    async def reject_proposal(
        self,
        proposal_id: str,
        operator: str,
        reason: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Operator rejects a Trade Proposal."""
        stmt = select(TradeProposalModel).where(TradeProposalModel.proposal_id == proposal_id)
        res = await db.execute(stmt)
        model = res.scalar_one_or_none()

        if not model:
            raise ValueError(f"Proposal {proposal_id} not found.")

        if model.human_decision != "PENDING":
            raise ValueError(f"Proposal {proposal_id} already has decision: {model.human_decision}")

        model.human_decision = "REJECTED"
        model.human_reason = f"Rejected by operator {operator}: {reason}"
        await db.commit()

        logger.info("Proposal %s rejected by %s: %s", proposal_id, operator, reason)
        return {
            "status": "REJECTED",
            "proposal_id": proposal_id,
            "human_decision": "REJECTED",
            "human_reason": model.human_reason,
        }


proposal_service = ProposalExecutionService()
