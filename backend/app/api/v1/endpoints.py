"""
API v1 Endpoints
Provides system status, risk monitoring, audit logs, and kill-switch controls.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.advisor_api import router as advisor_router
from backend.app.api.v1.backtest_api import router as backtest_router
from backend.app.api.v1.execution_api import router as execution_router
from backend.app.api.v1.market_data import router as market_data_router
from backend.app.api.v1.risk_api import router as risk_router
from backend.app.api.v1.strategies_api import router as strategies_router
from backend.app.api.v1.stream_api import router as stream_router
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.db.models import DailyRiskAuditModel, SystemAuditLogModel
from backend.app.db.session import get_db_session
from backend.app.models.domain import RiskStatusEnum
from risk.engine import risk_engine

router = APIRouter(prefix="/api/v1")
router.include_router(market_data_router)
router.include_router(strategies_router)
router.include_router(backtest_router)
router.include_router(risk_router)
router.include_router(execution_router)
router.include_router(stream_router)
router.include_router(advisor_router)


class KillSwitchRequest(BaseModel):
    reason: str


class AuditLogResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    actor: str
    severity: str
    message: str
    details: Optional[dict] = None


@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db_session)):
    """Provides complete system and operational status."""
    now_ist = clock.now()
    phase = clock.get_session_phase(now_ist)
    
    # Ensure risk engine session is active
    if risk_engine.state is None:
        await risk_engine.initialize_session(db)

    return {
        "environment": settings.ENVIRONMENT,
        "execution_mode": settings.EXECUTION_MODE,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "current_time_ist": now_ist.isoformat(),
        "session_phase": phase.value,
        "is_trading_day": clock.is_trading_day(now_ist),
        "is_market_open": clock.is_market_open(now_ist),
        "is_intraday_entry_allowed": clock.is_intraday_entry_allowed(now_ist),
        "risk_status": risk_engine.state.status.value if risk_engine.state else "UNKNOWN",
        "kill_switch_active": risk_engine.kill_switch_active,
        "capital_summary": {
            "starting_capital_inr": settings.STARTING_CAPITAL_INR,
            "daily_loss_limit_inr": settings.DAILY_LOSS_LIMIT_INR,
            "realized_pnl_inr": risk_engine.state.realized_pnl if risk_engine.state else 0.0,
            "unrealized_pnl_inr": risk_engine.state.unrealized_pnl if risk_engine.state else 0.0,
            "total_charges_inr": risk_engine.state.total_charges if risk_engine.state else 0.0,
            "net_pnl_inr": risk_engine.state.net_pnl if risk_engine.state else 0.0,
            "loss_limit_headroom_inr": (
                settings.DAILY_LOSS_LIMIT_INR + (risk_engine.state.net_pnl if risk_engine.state else 0.0)
            ),
        },
    }


@router.get("/risk/state")
async def get_risk_state(db: AsyncSession = Depends(get_db_session)):
    """Returns the detailed risk engine state."""
    if risk_engine.state is None:
        await risk_engine.initialize_session(db)
    return risk_engine.state


@router.post("/risk/kill-switch")
async def activate_kill_switch(payload: KillSwitchRequest, db: AsyncSession = Depends(get_db_session)):
    """Triggers the emergency kill-switch immediately."""
    await risk_engine.trigger_kill_switch(payload.reason, db)
    return {"status": "SUCCESS", "message": "Kill switch activated.", "reason": payload.reason}


@router.post("/risk/kill-switch/reset")
async def reset_kill_switch(payload: KillSwitchRequest, db: AsyncSession = Depends(get_db_session)):
    """Resets the emergency kill-switch with an audit reason."""
    if not payload.reason or len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A comprehensive reason is required to reset the kill switch.")
    await risk_engine.reset_kill_switch(payload.reason, db)
    return {"status": "SUCCESS", "message": "Kill switch reset.", "reason": payload.reason}


@router.get("/audit/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
):
    """Fetches recent immutable system audit events."""
    stmt = select(SystemAuditLogModel).order_by(desc(SystemAuditLogModel.id)).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        AuditLogResponse(
            id=r.id,
            timestamp=r.timestamp.isoformat(),
            event_type=r.event_type,
            actor=r.actor,
            severity=r.severity,
            message=r.message,
            details=r.details,
        )
        for r in records
    ]

