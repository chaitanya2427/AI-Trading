"""
Risk Management & Pre-Trade Enforcement API Endpoints
Provides risk status, pre-trade proposal gate evaluation, kill-switch, and audited overrides.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.db.models import DailyRiskAuditModel, SystemAuditLogModel
from backend.app.db.session import get_db_session
from backend.app.models.domain import DecisionEnum, TradeProposal
from risk.engine import risk_engine

router = APIRouter(prefix="/risk", tags=["Central Risk Engine"])


class KillSwitchActionRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Mandatory reason for kill switch action")


class ManualOverrideRequest(BaseModel):
    operator_id: str = Field(default="HUMAN_OPERATOR", min_length=3)
    rationale: str = Field(..., min_length=15, description="Mandatory detailed written rationale")


@router.get("/status")
async def get_risk_status(db: AsyncSession = Depends(get_db_session)):
    """Returns comprehensive risk budget, limits, and halt status."""
    if risk_engine.state is None:
        await risk_engine.initialize_session(db)

    state = risk_engine.state
    net_pnl = state.net_pnl
    loss_limit = settings.DAILY_LOSS_LIMIT_INR
    headroom = round(loss_limit + net_pnl, 2)

    return {
        "status": state.status.value,
        "kill_switch_active": risk_engine.kill_switch_active,
        "halt_reason": state.halt_reason,
        "halt_timestamp": state.halt_timestamp.isoformat() if state.halt_timestamp else None,
        "capital_metrics": {
            "starting_capital_inr": state.starting_capital,
            "available_capital_inr": state.available_capital,
            "daily_loss_limit_inr": loss_limit,
            "realized_pnl_inr": state.realized_pnl,
            "unrealized_pnl_inr": state.unrealized_pnl,
            "total_charges_inr": state.total_charges,
            "net_pnl_inr": net_pnl,
            "loss_limit_headroom_inr": headroom,
            "loss_budget_utilized_pct": round(min(100.0, max(0.0, (-net_pnl / loss_limit) * 100.0)), 2),
        },
        "limits": {
            "max_risk_per_trade_inr": settings.MAX_RISK_PER_TRADE_INR,
            "max_open_positions": settings.MAX_OPEN_POSITIONS,
            "max_daily_trades": settings.MAX_DAILY_TRADES,
            "current_open_positions": state.open_positions_count,
            "today_trades_count": state.today_trades_count,
        },
        "session": {
            "time_ist": clock.now().isoformat(),
            "session_phase": clock.get_session_phase().value,
            "is_intraday_entry_allowed": clock.is_intraday_entry_allowed(),
        },
    }


@router.post("/evaluate")
async def evaluate_trade_proposal(
    proposal: TradeProposal,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Primary pre-trade risk boundary: runs proposal through all 12 deterministic gates.
    """
    decision, reason = await risk_engine.evaluate_proposal(proposal, db)
    return {
        "proposal_id": str(proposal.proposal_id),
        "decision": decision.value,
        "approved": decision == DecisionEnum.APPROVED,
        "reason": reason,
        "timestamp": clock.now().isoformat(),
    }


@router.post("/kill-switch")
async def trigger_kill_switch(
    payload: KillSwitchActionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Triggers emergency kill switch immediately."""
    await risk_engine.trigger_kill_switch(payload.reason, db)
    return {"status": "SUCCESS", "message": "Emergency kill switch activated.", "reason": payload.reason}


@router.post("/kill-switch/reset")
async def reset_kill_switch(
    payload: KillSwitchActionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Resets emergency kill switch after verified clearance."""
    await risk_engine.reset_kill_switch(payload.reason, db)
    return {"status": "SUCCESS", "message": "Emergency kill switch reset.", "reason": payload.reason}


@router.post("/override")
async def request_manual_override(
    payload: ManualOverrideRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Applies a strictly audited same-session manual override."""
    try:
        await risk_engine.apply_audited_override(
            operator_id=payload.operator_id,
            rationale=payload.rationale,
            db=db,
        )
        return {
            "status": "OVERRIDE_APPLIED",
            "message": "Manual override applied for 1 trade opportunity with fresh risk evaluation.",
            "operator_id": payload.operator_id,
            "rationale": payload.rationale,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/audit-logs")
async def get_risk_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieves immutable system audit records."""
    stmt = select(SystemAuditLogModel).order_by(desc(SystemAuditLogModel.id))
    if event_type:
        stmt = stmt.where(SystemAuditLogModel.event_type == event_type)
    stmt = stmt.limit(limit)

    res = await db.execute(stmt)
    records = res.scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "event_type": r.event_type,
            "actor": r.actor,
            "severity": r.severity,
            "message": r.message,
            "details": r.details,
        }
        for r in records
    ]

