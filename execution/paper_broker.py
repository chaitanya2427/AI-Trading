"""
Paper Execution Engine (Simulated Broker)
Simulates realistic broker order execution with spread crossing, slippage modeling,
Indian statutory charges calculation, and strict data provenance tagging.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import math

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.models.domain import (
    DirectionEnum,
    ExchangeEnum,
    ExecutionModeEnum,
    Instrument,
    OrderTypeEnum,
    SegmentEnum,
)
from execution.costs import cost_calculator

logger = get_logger("execution.paper_broker")


class PaperOrder:
    """Represents an order within the paper execution sandbox."""

    def __init__(
        self,
        symbol: str,
        exchange: ExchangeEnum,
        direction: DirectionEnum,
        quantity: int,
        order_type: OrderTypeEnum,
        reference_price: float,
        limit_price: Optional[float] = None,
        proposal_id: Optional[str] = None,
        order_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.order_id: str = order_id or str(uuid4())
        self.proposal_id: Optional[str] = proposal_id
        self.created_at: datetime = created_at or clock.now()
        self.symbol: str = symbol
        self.exchange: ExchangeEnum = exchange
        self.direction: DirectionEnum = direction
        self.quantity: int = quantity
        self.order_type: OrderTypeEnum = order_type
        self.reference_price: float = round(reference_price, 2)
        self.limit_price: Optional[float] = round(limit_price, 2) if limit_price else None

        # Execution results
        self.status: str = "NEW"  # NEW, SUBMITTED, FILLED, REJECTED, CANCELLED
        self.filled_price: Optional[float] = None
        self.filled_at: Optional[datetime] = None
        self.slippage_inr: float = 0.0
        self.charges_inr: float = 0.0
        self.reject_reason: Optional[str] = None

        # Provenance
        self.execution_mode: str = ExecutionModeEnum.PAPER.value
        self.provenance: str = "SIMULATED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "proposal_id": self.proposal_id,
            "created_at": self.created_at.isoformat(),
            "symbol": self.symbol,
            "exchange": self.exchange.value if isinstance(self.exchange, ExchangeEnum) else str(self.exchange),
            "direction": self.direction.value if isinstance(self.direction, DirectionEnum) else str(self.direction),
            "quantity": self.quantity,
            "order_type": self.order_type.value if isinstance(self.order_type, OrderTypeEnum) else str(self.order_type),
            "reference_price": self.reference_price,
            "limit_price": self.limit_price,
            "status": self.status,
            "filled_price": self.filled_price,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "slippage_inr": self.slippage_inr,
            "charges_inr": self.charges_inr,
            "reject_reason": self.reject_reason,
            "execution_mode": self.execution_mode,
            "provenance": self.provenance,
        }


class PaperBroker:
    """
    Paper Trading Broker with realistic market microstructure simulation.
    - Bid-Ask spread crossing
    - Deterministic / tick-based slippage
    - Authentic provenance labeling (PAPER / SIMULATED)
    - Full order lifecycle state management
    """

    def __init__(
        self,
        default_slippage_pct: float = 0.0002,  # 0.02% base slippage
        min_tick_size: float = 0.05,
    ) -> None:
        self.default_slippage_pct = default_slippage_pct
        self.min_tick_size = min_tick_size
        self._orders: Dict[str, PaperOrder] = {}
        logger.info(
            "PaperBroker initialized in PAPER execution mode. Slippage=%s%%, Tick=%s",
            self.default_slippage_pct * 100,
            self.min_tick_size,
        )

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        return self._orders.get(order_id)

    def list_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[PaperOrder]:
        orders = list(self._orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        if status:
            orders = [o for o in orders if o.status == status]
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders[:limit]

    def create_order(
        self,
        symbol: str,
        exchange: ExchangeEnum,
        direction: DirectionEnum,
        quantity: int,
        order_type: OrderTypeEnum,
        reference_price: float,
        limit_price: Optional[float] = None,
        proposal_id: Optional[str] = None,
    ) -> PaperOrder:
        """Creates a new order in NEW state."""
        order = PaperOrder(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            quantity=quantity,
            order_type=order_type,
            reference_price=reference_price,
            limit_price=limit_price,
            proposal_id=proposal_id,
        )
        self._orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: str, reason: str = "CANCELLED_BY_USER") -> PaperOrder:
        """Cancels an existing unfilled order."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found.")

        if order.status in ("FILLED", "REJECTED", "CANCELLED"):
            raise ValueError(f"Cannot cancel order {order_id} in terminal state '{order.status}'.")

        order.status = "CANCELLED"
        order.reject_reason = reason
        logger.info("Order %s cancelled: %s", order_id, reason)
        return order

    def execute_order(
        self,
        order: PaperOrder,
        current_market_price: float,
        quote_timestamp: Optional[datetime] = None,
        instrument: Optional[Instrument] = None,
        apply_spread: bool = True,
        apply_slippage: bool = True,
    ) -> PaperOrder:
        """
        Executes order against current market price using realistic microstructure rules.
        """
        order.status = "SUBMITTED"

        # Validate price authenticity
        if current_market_price <= 0:
            order.status = "REJECTED"
            order.reject_reason = f"Invalid market execution price: {current_market_price}"
            return order

        # Staleness verification if quote timestamp is provided
        if quote_timestamp:
            quote_age = (clock.now() - quote_timestamp).total_seconds()
            if quote_age > settings.MAX_QUOTE_AGE_SECONDS:
                order.status = "REJECTED"
                order.reject_reason = f"Stale market price rejected (age: {quote_age:.2f}s > {settings.MAX_QUOTE_AGE_SECONDS}s)"
                logger.warning("Paper order %s rejected: %s", order.order_id, order.reject_reason)
                return order

        # Limit order condition verification
        if order.order_type == OrderTypeEnum.LIMIT and order.limit_price is not None:
            if order.direction == DirectionEnum.LONG and current_market_price > order.limit_price:
                # Market has not reached buy limit price
                logger.info(
                    "Order %s waiting: Market %s > Buy Limit %s",
                    order.order_id,
                    current_market_price,
                    order.limit_price,
                )
                return order
            elif order.direction == DirectionEnum.SHORT and current_market_price < order.limit_price:
                # Market has not reached sell limit price
                logger.info(
                    "Order %s waiting: Market %s < Sell Limit %s",
                    order.order_id,
                    current_market_price,
                    order.limit_price,
                )
                return order

        # Calculate realistic executed fill price
        tick = instrument.tick_size if instrument else self.min_tick_size
        spread = tick if apply_spread else 0.0

        base_price = order.limit_price if order.order_type == OrderTypeEnum.LIMIT and order.limit_price else current_market_price

        # Realistic slippage (0.01% - 0.02% or min 1 tick)
        slippage = 0.0
        if apply_slippage:
            slippage = max(tick, round(base_price * self.default_slippage_pct, 2))

        if order.direction == DirectionEnum.LONG:
            # Buying crosses the ask: price + half spread + slippage
            fill_price = round(base_price + (spread / 2.0) + slippage, 2)
            # Ensure price aligns to tick size
            fill_price = round(round(fill_price / tick) * tick, 2)
            total_slippage = round((fill_price - base_price) * order.quantity, 2)
        else:
            # Selling hits the bid: price - half spread - slippage
            fill_price = round(base_price - (spread / 2.0) - slippage, 2)
            fill_price = round(round(fill_price / tick) * tick, 2)
            total_slippage = round((base_price - fill_price) * order.quantity, 2)

        # Statutory costs estimation for single entry leg
        dummy_instrument = instrument or Instrument(
            exchange=order.exchange,
            segment=SegmentEnum.EQ,
            symbol=order.symbol,
            instrument_key=f"{order.exchange.value}_{order.symbol}",
            lot_size=1,
            tick_size=tick,
        )
        
        # Calculate half round-trip statutory costs for this leg
        round_trip = cost_calculator.calculate_round_trip_costs(
            instrument=dummy_instrument,
            entry_price=fill_price,
            exit_price=fill_price,
            quantity=order.quantity,
        )
        leg_charges = round(round_trip["total_costs"] / 2.0, 2)

        order.filled_price = fill_price
        order.filled_at = clock.now()
        order.slippage_inr = total_slippage
        order.charges_inr = leg_charges
        order.status = "FILLED"

        logger.info(
            "Paper order %s FILLED: %s %d %s @ ₹%s (slippage: ₹%s, charges: ₹%s)",
            order.order_id,
            order.direction.value,
            order.quantity,
            order.symbol,
            order.filled_price,
            order.slippage_inr,
            order.charges_inr,
        )
        return order


paper_broker = PaperBroker()

