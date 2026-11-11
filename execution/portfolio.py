"""
Paper Portfolio Tracker & Position Manager
Maintains virtual positions, real-time MTM valuation, automated Stop Loss / Target exits,
mandatory 15:15 IST square-off, and emergency risk halt fail-closed closure.
"""

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.db.models import PaperPositionModel
from backend.app.models.domain import (
    DirectionEnum,
    ExchangeEnum,
    ExecutionModeEnum,
    Instrument,
    RiskStatusEnum,
    SegmentEnum,
)
from execution.costs import cost_calculator
from execution.paper_broker import PaperOrder
from risk.engine import risk_engine

logger = get_logger("execution.portfolio")


class PaperPosition:
    """Represents an active or closed position in the paper portfolio."""

    def __init__(
        self,
        symbol: str,
        exchange: ExchangeEnum,
        direction: DirectionEnum,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        entry_time: Optional[datetime] = None,
        position_id: Optional[str] = None,
        order_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
    ) -> None:
        self.position_id: str = position_id or str(uuid4())
        self.order_id: Optional[str] = order_id
        self.proposal_id: Optional[str] = proposal_id
        self.symbol: str = symbol
        self.exchange: ExchangeEnum = exchange
        self.direction: DirectionEnum = direction
        self.quantity: int = quantity
        self.entry_price: float = round(entry_price, 2)
        self.current_price: float = round(entry_price, 2)
        self.stop_loss: float = round(stop_loss, 2)
        self.target: float = round(target, 2)
        self.entry_time: datetime = entry_time or clock.now()

        # Valuation
        self.unrealized_pnl: float = 0.0
        self.realized_pnl: float = 0.0
        self.total_charges: float = 0.0
        self.status: str = "OPEN"  # OPEN, CLOSED
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.exit_reason: Optional[str] = None

        # Provenance
        self.execution_mode: str = ExecutionModeEnum.PAPER.value
        self.provenance: str = "SIMULATED"

    def calculate_mtm(self, new_market_price: float) -> float:
        """Calculates unrealized P&L from latest authentic market price."""
        self.current_price = round(new_market_price, 2)
        if self.status != "OPEN":
            return self.unrealized_pnl

        if self.direction == DirectionEnum.LONG:
            self.unrealized_pnl = round((self.current_price - self.entry_price) * self.quantity, 2)
        else:
            self.unrealized_pnl = round((self.entry_price - self.current_price) * self.quantity, 2)
        return self.unrealized_pnl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "order_id": self.order_id,
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "exchange": self.exchange.value if isinstance(self.exchange, ExchangeEnum) else str(self.exchange),
            "direction": self.direction.value if isinstance(self.direction, DirectionEnum) else str(self.direction),
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "entry_time": self.entry_time.isoformat(),
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_charges": self.total_charges,
            "status": self.status,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason,
            "execution_mode": self.execution_mode,
            "provenance": self.provenance,
        }


class PortfolioTracker:
    """
    Portfolio Tracker for Paper Trading.
    Tracks live positions, recalculates MTM, enforces automated SL/Target and 15:15 IST square-off,
    and feeds live risk stats back into CentralRiskEngine.
    """

    def __init__(self) -> None:
        self._positions: Dict[str, PaperPosition] = {}
        logger.info("PortfolioTracker initialized.")

    def get_position(self, position_id: str) -> Optional[PaperPosition]:
        return self._positions.get(position_id)

    def get_open_positions(self) -> List[PaperPosition]:
        return [p for p in self._positions.values() if p.status == "OPEN"]

    def get_closed_positions(self) -> List[PaperPosition]:
        return [p for p in self._positions.values() if p.status == "CLOSED"]

    def open_position_from_fill(
        self,
        order: PaperOrder,
        stop_loss: float,
        target: float,
        instrument: Optional[Instrument] = None,
        db: Optional[AsyncSession] = None,
    ) -> PaperPosition:
        """
        Creates and opens a new PaperPosition from an executed PaperOrder fill.
        """
        if order.status != "FILLED" or order.filled_price is None:
            raise ValueError(f"Cannot open position from unfulfilled order: {order.status}")

        pos = PaperPosition(
            symbol=order.symbol,
            exchange=order.exchange,
            direction=order.direction,
            quantity=order.quantity,
            entry_price=order.filled_price,
            stop_loss=stop_loss,
            target=target,
            entry_time=order.filled_at or clock.now(),
            order_id=order.order_id,
            proposal_id=order.proposal_id,
        )

        # Estimate preliminary single-leg entry charges
        dummy_inst = instrument or Instrument(
            exchange=order.exchange,
            segment=SegmentEnum.EQ,
            symbol=order.symbol,
            instrument_key=f"{order.exchange.value}_{order.symbol}",
        )
        rt_costs = cost_calculator.calculate_round_trip_costs(
            dummy_inst,
            pos.entry_price,
            pos.entry_price,
            pos.quantity,
        )
        pos.total_charges = round(rt_costs["total_costs"] / 2.0, 2)

        self._positions[pos.position_id] = pos
        logger.info(
            "Opened %s position %s for %d %s @ ₹%s (SL: ₹%s, Target: ₹%s)",
            pos.direction.value,
            pos.position_id,
            pos.quantity,
            pos.symbol,
            pos.entry_price,
            pos.stop_loss,
            pos.target,
        )
        return pos

    async def update_market_price(
        self,
        symbol: str,
        current_price: float,
        timestamp: Optional[datetime] = None,
        db: Optional[AsyncSession] = None,
    ) -> List[PaperPosition]:
        """
        Updates MTM for all open positions of symbol and evaluates SL / Target triggers.
        Synchronizes aggregate P&L to CentralRiskEngine.
        """
        closed_this_tick: List[PaperPosition] = []
        open_positions = [p for p in self.get_open_positions() if p.symbol == symbol]

        for pos in open_positions:
            pos.calculate_mtm(current_price)

            # Automated SL / Target Intrabar Check
            exit_reason: Optional[str] = None
            exit_price: float = current_price

            if pos.direction == DirectionEnum.LONG:
                if current_price <= pos.stop_loss:
                    exit_reason = "STOP_LOSS"
                    exit_price = pos.stop_loss
                elif current_price >= pos.target:
                    exit_reason = "TARGET"
                    exit_price = pos.target
            elif pos.direction == DirectionEnum.SHORT:
                if current_price >= pos.stop_loss:
                    exit_reason = "STOP_LOSS"
                    exit_price = pos.stop_loss
                elif current_price <= pos.target:
                    exit_reason = "TARGET"
                    exit_price = pos.target

            if exit_reason:
                await self.close_position(
                    position_id=pos.position_id,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    exit_time=timestamp or clock.now(),
                    db=db,
                )
                closed_this_tick.append(pos)

        # Synchronize aggregate portfolio P&L to CentralRiskEngine
        if db is not None:
            await self.sync_to_risk_engine(db)

        return closed_this_tick

    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        exit_time: Optional[datetime] = None,
        db: Optional[AsyncSession] = None,
    ) -> PaperPosition:
        """
        Closes an open position, realizes P&L, computes statutory round-trip charges, and records closure.
        """
        pos = self._positions.get(position_id)
        if not pos:
            raise ValueError(f"Position {position_id} not found.")

        if pos.status == "CLOSED":
            return pos

        pos.exit_price = round(exit_price, 2)
        pos.exit_time = exit_time or clock.now()
        pos.exit_reason = exit_reason
        pos.status = "CLOSED"
        pos.unrealized_pnl = 0.0

        # Calculate Gross Realized P&L
        if pos.direction == DirectionEnum.LONG:
            gross_pnl = (pos.exit_price - pos.entry_price) * pos.quantity
        else:
            gross_pnl = (pos.entry_price - pos.exit_price) * pos.quantity
        pos.realized_pnl = round(gross_pnl, 2)

        # Calculate Total Round-Trip Costs
        dummy_inst = Instrument(
            exchange=pos.exchange,
            segment=SegmentEnum.EQ,
            symbol=pos.symbol,
            instrument_key=f"{pos.exchange.value}_{pos.symbol}",
        )
        rt_costs = cost_calculator.calculate_round_trip_costs(
            dummy_inst,
            pos.entry_price,
            pos.exit_price,
            pos.quantity,
        )
        pos.total_charges = rt_costs["total_costs"]

        logger.info(
            "Closed position %s (%s) @ ₹%s. Gross P&L: ₹%s, Costs: ₹%s, Reason: %s",
            pos.position_id,
            pos.symbol,
            pos.exit_price,
            pos.realized_pnl,
            pos.total_charges,
            pos.exit_reason,
        )

        # Sync to DB if session provided
        if db is not None:
            # Check if model exists or create it
            stmt = select(PaperPositionModel).where(PaperPositionModel.position_id == pos.position_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.status = "CLOSED"
                existing.exit_price = pos.exit_price
                existing.exit_time = pos.exit_time
                existing.exit_reason = pos.exit_reason
                existing.realized_pnl = pos.realized_pnl
                existing.unrealized_pnl = 0.0
                existing.total_charges = pos.total_charges
            else:
                db_pos = PaperPositionModel(
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
                    realized_pnl=pos.realized_pnl,
                    total_charges=pos.total_charges,
                    status="CLOSED",
                    exit_price=pos.exit_price,
                    exit_time=pos.exit_time,
                    exit_reason=pos.exit_reason,
                )
                db.add(db_pos)
            await db.commit()

            await self.sync_to_risk_engine(db)

        return pos

    async def check_intraday_square_off(
        self,
        current_time: datetime,
        current_prices: Optional[Dict[str, float]] = None,
        db: Optional[AsyncSession] = None,
    ) -> List[PaperPosition]:
        """
        Enforces mandatory 15:15 IST square-off. Closes all remaining open intraday positions.
        """
        closed_positions: List[PaperPosition] = []
        if current_time.time() >= time(15, 15):
            open_positions = self.get_open_positions()
            for pos in open_positions:
                exit_price = pos.current_price
                if current_prices and pos.symbol in current_prices:
                    exit_price = current_prices[pos.symbol]
                closed = await self.close_position(
                    position_id=pos.position_id,
                    exit_price=exit_price,
                    exit_reason="MANDATORY_SQUARE_OFF_1515",
                    exit_time=current_time,
                    db=db,
                )
                closed_positions.append(closed)
        return closed_positions

    async def square_off_all(
        self,
        exit_prices: Optional[Dict[str, float]] = None,
        reason: str = "MANUAL_SQUARE_OFF",
        db: Optional[AsyncSession] = None,
    ) -> List[PaperPosition]:
        """Closes all currently open positions immediately."""
        closed: List[PaperPosition] = []
        for pos in self.get_open_positions():
            exit_price = pos.current_price
            if exit_prices and pos.symbol in exit_prices:
                exit_price = exit_prices[pos.symbol]
            c = await self.close_position(
                position_id=pos.position_id,
                exit_price=exit_price,
                exit_reason=reason,
                db=db,
            )
            closed.append(c)
        return closed

    async def sync_to_risk_engine(self, db: AsyncSession) -> None:
        """Aggregates portfolio P&L metrics and synchronizes them with CentralRiskEngine."""
        total_realized = sum(p.realized_pnl for p in self._positions.values())
        total_unrealized = sum(p.unrealized_pnl for p in self.get_open_positions())
        total_charges = sum(p.total_charges for p in self._positions.values())
        open_count = len(self.get_open_positions())

        state = await risk_engine.update_pnl_and_exposure(
            realized_pnl=total_realized,
            unrealized_pnl=total_unrealized,
            charges=total_charges,
            open_positions_count=open_count,
            db=db,
        )

        # Fail-Closed: If risk engine halts or kill switch is active, square off all open positions!
        if state.status in (RiskStatusEnum.HALTED, RiskStatusEnum.KILL_SWITCH):
            if open_count > 0:
                logger.critical(
                    "RISK ENGINE HALT DETECTED (%s): Emergency square-off of %d open positions!",
                    state.status.value,
                    open_count,
                )
                await self.square_off_all(reason=f"RISK_HALT: {state.halt_reason}", db=db)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Provides high-level portfolio summary."""
        open_positions = self.get_open_positions()
        closed_positions = self.get_closed_positions()

        total_realized = sum(p.realized_pnl for p in self._positions.values())
        total_unrealized = sum(p.unrealized_pnl for p in open_positions)
        total_charges = sum(p.total_charges for p in self._positions.values())
        net_pnl = round(total_realized + total_unrealized - total_charges, 2)

        return {
            "execution_mode": ExecutionModeEnum.PAPER.value,
            "starting_capital_inr": settings.STARTING_CAPITAL_INR,
            "daily_loss_limit_inr": settings.DAILY_LOSS_LIMIT_INR,
            "open_positions_count": len(open_positions),
            "closed_positions_count": len(closed_positions),
            "realized_pnl_inr": round(total_realized, 2),
            "unrealized_pnl_inr": round(total_unrealized, 2),
            "total_charges_inr": round(total_charges, 2),
            "net_pnl_inr": net_pnl,
            "loss_limit_headroom_inr": round(settings.DAILY_LOSS_LIMIT_INR + net_pnl, 2),
            "provenance": "SIMULATED",
        }


portfolio_tracker = PortfolioTracker()

