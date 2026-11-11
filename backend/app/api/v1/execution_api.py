"""
Execution & Paper Trading API Endpoints
Provides routes for Proposal Approval, Paper Orders, Portfolio Tracking, MTM Updates,
Square-Off Controls, and Reconciliation Audits.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.db.session import get_db_session
from execution.paper_broker import paper_broker
from execution.portfolio import portfolio_tracker
from execution.proposal_service import proposal_service
from execution.reconciliation import reconciliation_engine

router = APIRouter(prefix="/execution", tags=["Execution & Paper Trading"])


class ProposalApprovalRequest(BaseModel):
    operator: str = Field(default="OPERATOR_1", description="Identifier of the operator reviewing the proposal")


class ProposalRejectionRequest(BaseModel):
    operator: str = Field(default="OPERATOR_1")
    reason: str = Field(..., min_length=3, description="Audit justification for rejection")


class MarketPriceUpdateRequest(BaseModel):
    symbol: str
    price: float = Field(gt=0.0)


class SquareOffRequest(BaseModel):
    exit_price: Optional[float] = Field(default=None, gt=0.0)
    reason: str = Field(default="MANUAL_SQUARE_OFF")


@router.get("/proposals")
async def list_proposals(
    status: Optional[str] = Query(None, description="Filter by decision: PENDING, APPROVED, REJECTED"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """Lists trade proposals requiring human approval or past historical decisions."""
    proposals = await proposal_service.list_proposals(status=status, limit=limit, db=db)
    return {"count": len(proposals), "proposals": proposals}


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    payload: ProposalApprovalRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Operator approves a trade proposal.
    Triggers Central Risk Engine validation and executes via Paper Broker if approved.
    """
    try:
        result = await proposal_service.approve_and_execute(
            proposal_id=proposal_id,
            operator=payload.operator,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval pipeline error: {str(e)}")


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    payload: ProposalRejectionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Operator rejects a trade proposal with documented reason."""
    try:
        result = await proposal_service.reject_proposal(
            proposal_id=proposal_id,
            operator=payload.operator,
            reason=payload.reason,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders")
async def list_orders(
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="NEW, SUBMITTED, FILLED, REJECTED, CANCELLED"),
    limit: int = Query(100, ge=1, le=500),
):
    """Retrieves paper orders executed or pending in the simulated broker."""
    orders = paper_broker.list_orders(symbol=symbol, status=status, limit=limit)
    return {
        "execution_mode": "PAPER",
        "count": len(orders),
        "orders": [o.to_dict() for o in orders],
    }


@router.get("/positions")
async def list_positions(
    status: Optional[str] = Query("OPEN", description="OPEN, CLOSED, or ALL"),
):
    """Lists current open or closed positions in the paper portfolio."""
    if status == "OPEN":
        positions = portfolio_tracker.get_open_positions()
    elif status == "CLOSED":
        positions = portfolio_tracker.get_closed_positions()
    else:
        positions = portfolio_tracker.get_open_positions() + portfolio_tracker.get_closed_positions()

    return {
        "execution_mode": "PAPER",
        "count": len(positions),
        "positions": [p.to_dict() for p in positions],
    }


@router.get("/portfolio/summary")
async def get_portfolio_summary():
    """Returns high-level portfolio valuation, MTM, and ₹250 loss limit headroom."""
    return portfolio_tracker.get_portfolio_summary()


@router.post("/market-update")
async def update_market_price(
    payload: MarketPriceUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Feeds authentic market price into portfolio to update MTM and evaluate SL/Target triggers.
    """
    closed = await portfolio_tracker.update_market_price(
        symbol=payload.symbol,
        current_price=payload.price,
        timestamp=clock.now(),
        db=db,
    )
    return {
        "symbol": payload.symbol,
        "price": payload.price,
        "positions_closed_on_trigger": len(closed),
        "closed_details": [p.to_dict() for p in closed],
    }


@router.post("/positions/{position_id}/square-off")
async def square_off_position(
    position_id: str,
    payload: SquareOffRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Manually squares off an active open position."""
    pos = portfolio_tracker.get_position(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
    if pos.status == "CLOSED":
        raise HTTPException(status_code=400, detail=f"Position {position_id} is already closed.")

    exit_price = payload.exit_price or pos.current_price
    closed_pos = await portfolio_tracker.close_position(
        position_id=position_id,
        exit_price=exit_price,
        exit_reason=payload.reason,
        exit_time=clock.now(),
        db=db,
    )
    return {
        "status": "CLOSED",
        "position": closed_pos.to_dict(),
    }


@router.post("/square-off-all")
async def square_off_all_positions(
    db: AsyncSession = Depends(get_db_session),
):
    """Emergency manual square-off of all currently open positions."""
    closed = await portfolio_tracker.square_off_all(
        reason="MANUAL_SQUARE_OFF_ALL",
        db=db,
    )
    return {
        "status": "ALL_CLOSED",
        "count_squared_off": len(closed),
        "closed_positions": [p.to_dict() for p in closed],
    }


@router.get("/reconciliation")
async def run_reconciliation(
    db: AsyncSession = Depends(get_db_session),
):
    """Runs complete reconciliation audit across memory, DB, and risk engine."""
    report = await reconciliation_engine.run_reconciliation(db=db)
    return report.to_dict()

