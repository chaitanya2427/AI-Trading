"""
Portfolio & Broker Reconciliation Engine
Audits in-memory positions, paper orders, SQLite database tables, and Central Risk Engine P&L
to detect discrepancies, orphan orders, unclosed intraday positions, or MTM mismatch.
"""

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.core.logging import get_logger
from backend.app.db.models import PaperOrderModel, PaperPositionModel
from execution.paper_broker import paper_broker
from execution.portfolio import portfolio_tracker
from risk.engine import risk_engine

logger = get_logger("execution.reconciliation")


class ReconciliationReport:
    """Structured reconciliation audit report."""

    def __init__(
        self,
        is_clean: bool,
        discrepancies: List[str],
        stats: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.is_clean = is_clean
        self.discrepancies = discrepancies
        self.stats = stats
        self.timestamp = timestamp or clock.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "is_clean": self.is_clean,
            "discrepancy_count": len(self.discrepancies),
            "discrepancies": self.discrepancies,
            "stats": self.stats,
            "execution_mode": "PAPER",
            "provenance": "SIMULATED",
        }


class ReconciliationEngine:
    """Audits consistency across In-Memory Portfolio, DB Persistence, and Risk Engine."""

    async def run_reconciliation(self, db: AsyncSession) -> ReconciliationReport:
        """
        Executes complete reconciliation audit.
        """
        discrepancies: List[str] = []
        now_ist = clock.now()

        # 1. Audit In-Memory Positions vs Database Positions
        in_memory_open = portfolio_tracker.get_open_positions()
        stmt = select(PaperPositionModel).where(PaperPositionModel.status == "OPEN")
        res = await db.execute(stmt)
        db_open = res.scalars().all()

        if len(in_memory_open) != len(db_open):
            discrepancies.append(
                f"Position Count Mismatch: In-Memory Open={len(in_memory_open)}, DB Open={len(db_open)}"
            )

        db_positions_by_id = {p.position_id: p for p in db_open}
        for mem_pos in in_memory_open:
            if mem_pos.position_id not in db_positions_by_id:
                discrepancies.append(f"Orphan In-Memory Position: {mem_pos.position_id} ({mem_pos.symbol}) not in DB.")
            else:
                db_p = db_positions_by_id[mem_pos.position_id]
                if mem_pos.quantity != db_p.quantity:
                    discrepancies.append(
                        f"Quantity Mismatch for {mem_pos.position_id}: Mem={mem_pos.quantity}, DB={db_p.quantity}"
                    )
                if mem_pos.direction.value != db_p.direction:
                    discrepancies.append(
                        f"Direction Mismatch for {mem_pos.position_id}: Mem={mem_pos.direction.value}, DB={db_p.direction}"
                    )

        # 2. Audit Paper Orders vs DB Orders
        mem_orders = paper_broker.list_orders(limit=200)
        stmt_orders = select(PaperOrderModel)
        res_orders = await db.execute(stmt_orders)
        db_orders = {o.order_id: o for o in res_orders.scalars().all()}

        for mem_order in mem_orders:
            if mem_order.status == "FILLED" and mem_order.order_id not in db_orders:
                discrepancies.append(f"Orphan Filled Order: {mem_order.order_id} ({mem_order.symbol}) missing from DB.")

        # 3. Post-15:15 IST Unclosed Intraday Positions Check
        if now_ist.time() >= time(15, 15):
            if len(in_memory_open) > 0:
                discrepancies.append(
                    f"Session Integrity Violation: {len(in_memory_open)} open positions exist after 15:15 IST square-off cut-off."
                )

        # 4. Risk Engine P&L Reconciliation
        summary = portfolio_tracker.get_portfolio_summary()
        if risk_engine.state is not None:
            calc_net_pnl = summary["net_pnl_inr"]
            risk_net_pnl = risk_engine.state.net_pnl
            diff = abs(calc_net_pnl - risk_net_pnl)
            if diff > 0.05:  # Tolerance of 5 paise for rounding
                discrepancies.append(
                    f"P&L Desynchronization: Portfolio Net P&L (₹{calc_net_pnl:.2f}) != Risk Engine Net P&L (₹{risk_net_pnl:.2f})"
                )

        is_clean = len(discrepancies) == 0
        if not is_clean:
            logger.warning("Reconciliation found %d discrepancies: %s", len(discrepancies), discrepancies)
        else:
            logger.info("Reconciliation check clean: All positions, orders, and P&L fully synchronized.")

        return ReconciliationReport(
            is_clean=is_clean,
            discrepancies=discrepancies,
            stats={
                "in_memory_open_positions": len(in_memory_open),
                "db_open_positions": len(db_open),
                "portfolio_net_pnl_inr": summary["net_pnl_inr"],
                "risk_engine_net_pnl_inr": risk_engine.state.net_pnl if risk_engine.state else 0.0,
                "realized_pnl_inr": summary["realized_pnl_inr"],
                "unrealized_pnl_inr": summary["unrealized_pnl_inr"],
                "total_charges_inr": summary["total_charges_inr"],
            },
            timestamp=now_ist,
        )


reconciliation_engine = ReconciliationEngine()

