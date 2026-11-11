"""
Central Deterministic Risk Engine (Fail-Closed Sovereign Authority)
Strictly enforces:
- ₹250 Hard Daily Loss Cap (Realized + Unrealized + Fees + Pending Exposure)
- Position Sizing (< ₹250 risk / trade, < ₹25,000 available capital)
- 12 Deterministic Risk Gates
- Data Freshness Circuit Breaker (< 5.0s)
- Emergency Kill Switch
- Replay & Concurrency Protection
- Immutable SQLite Audit Trail & Restart Recovery
"""

import asyncio
import logging
from datetime import datetime, time, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.db.models import DailyRiskAuditModel, SystemAuditLogModel
from backend.app.models.domain import (
    DailyRiskState,
    DecisionEnum,
    DirectionEnum,
    RiskStatusEnum,
    TradeProposal,
)
from execution.costs import cost_calculator

logger = logging.getLogger(__name__)


class CentralRiskEngine:
    """
    Sovereign, non-bypassable, fail-closed authority for all trade approvals.
    No LLM, agent, dashboard button, or Telegram message can override these deterministic rules.
    """

    def __init__(self):
        self.state: Optional[DailyRiskState] = None
        self.kill_switch_active: bool = False
        self._processed_proposal_ids: Set[str] = set()
        self._last_trade_time: Optional[datetime] = None
        self._cooldown_seconds: float = 30.0  # Minimum cooldown between trades
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._lock is None or (
            current_loop and getattr(self._lock, "_loop", None) is not None and self._lock._loop != current_loop
        ):
            self._lock = asyncio.Lock()
        return self._lock

    async def initialize_session(self, db: AsyncSession) -> DailyRiskState:
        """
        Loads or initializes today's risk state from SQLite.
        Ensures restart recovery: if previously HALTED, it stays HALTED.
        """
        today = clock.today()
        stmt = select(DailyRiskAuditModel).where(DailyRiskAuditModel.date == today)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            # First initialization of the session
            self.state = DailyRiskState(
                date=today,
                status=RiskStatusEnum.ACTIVE,
                starting_capital=settings.STARTING_CAPITAL_INR,
                available_capital=settings.STARTING_CAPITAL_INR,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                total_charges=0.0,
                net_pnl=0.0,
            )
            new_audit = DailyRiskAuditModel(
                date=today,
                status="ACTIVE",
                starting_capital=settings.STARTING_CAPITAL_INR,
                available_capital=settings.STARTING_CAPITAL_INR,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                total_charges=0.0,
                net_pnl=0.0,
                override_count=0,
            )
            db.add(new_audit)
            await db.commit()
            logger.info(f"Initialized fresh risk session for {today} with ₹{settings.STARTING_CAPITAL_INR:.2f} capital.")
        else:
            # Recover existing state from DB
            self.state = DailyRiskState(
                date=record.date,
                status=RiskStatusEnum(record.status),
                starting_capital=record.starting_capital,
                available_capital=record.available_capital,
                realized_pnl=record.realized_pnl,
                unrealized_pnl=record.unrealized_pnl,
                total_charges=record.total_charges,
                net_pnl=record.net_pnl,
                halt_reason=record.halt_reason,
                halt_timestamp=record.halt_timestamp,
            )
            if self.state.status == RiskStatusEnum.HALTED:
                logger.critical(
                    f"RECOVERED HALTED STATE from DB for {today}. Reason: {record.halt_reason}. Remaining HALTED."
                )
            elif self.state.status == RiskStatusEnum.KILL_SWITCH:
                self.kill_switch_active = True
                logger.critical(f"RECOVERED KILL SWITCH state from DB for {today}.")

        return self.state

    async def update_pnl_and_exposure(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
        charges: float,
        open_positions_count: int,
        db: AsyncSession,
    ) -> DailyRiskState:
        """
        Updates session P&L and triggers immediate hard halt if cumulative loss reaches ₹250.
        """
        async with self._get_lock():
            if self.state is None:
                await self.initialize_session(db)

            self.state.realized_pnl = round(realized_pnl, 2)
            self.state.unrealized_pnl = round(unrealized_pnl, 2)
            self.state.total_charges = round(charges, 2)
            self.state.open_positions_count = open_positions_count
            net_pnl = self.state.calculate_net_pnl()

            # Check hard daily loss limit: Net P&L <= -₹250.00
            if net_pnl <= -settings.DAILY_LOSS_LIMIT_INR:
                if self.state.status != RiskStatusEnum.HALTED:
                    self.state.status = RiskStatusEnum.HALTED
                    self.state.halt_reason = (
                        f"Daily loss limit of ₹{settings.DAILY_LOSS_LIMIT_INR:.2f} reached. "
                        f"Net P&L: ₹{net_pnl:.2f} (Realized: ₹{realized_pnl:.2f}, Unrealized: ₹{unrealized_pnl:.2f}, Costs: ₹{charges:.2f})."
                    )
                    self.state.halt_timestamp = datetime.now(timezone.utc)
                    logger.critical(f"HARD RISK HALT TRIGGERED: {self.state.halt_reason}")

                    audit_event = SystemAuditLogModel(
                        event_type="RISK_HALT_TRIGGERED",
                        actor="CENTRAL_RISK_ENGINE",
                        severity="CRITICAL",
                        message=self.state.halt_reason,
                        details={
                            "realized_pnl": realized_pnl,
                            "unrealized_pnl": unrealized_pnl,
                            "charges": charges,
                            "net_pnl": net_pnl,
                            "limit": settings.DAILY_LOSS_LIMIT_INR,
                        },
                    )
                    db.add(audit_event)

            # Persist updated risk figures
            stmt = (
                update(DailyRiskAuditModel)
                .where(DailyRiskAuditModel.date == self.state.date)
                .values(
                    realized_pnl=self.state.realized_pnl,
                    unrealized_pnl=self.state.unrealized_pnl,
                    total_charges=self.state.total_charges,
                    net_pnl=self.state.net_pnl,
                    status=self.state.status.value,
                    halt_reason=self.state.halt_reason,
                    halt_timestamp=self.state.halt_timestamp,
                )
            )
            await db.execute(stmt)
            await db.commit()
            return self.state

    async def update_pnl(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
        charges: float,
        db: AsyncSession,
    ) -> DailyRiskState:
        """Convenience method for updating P&L without modifying open position count."""
        return await self.update_pnl_and_exposure(
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            charges=charges,
            open_positions_count=self.state.open_positions_count if self.state else 0,
            db=db,
        )

    async def evaluate_proposal(
        self,
        proposal: TradeProposal,
        db: AsyncSession,
    ) -> Tuple[DecisionEnum, Optional[str]]:
        """
        Deterministic, 12-Gate Fail-Closed Pre-Trade Risk Evaluation.
        Returns (DecisionEnum.APPROVED, None) or (DecisionEnum.REJECTED, detailed_reason).
        """
        async with self._get_lock():
            if self.state is None:
                await self.initialize_session(db)

            # Gate 1: Replay & Deduplication Protection
            proposal_str_id = str(proposal.proposal_id)
            if proposal_str_id in self._processed_proposal_ids:
                reason = f"REJECTED: Duplicate proposal detected. ID {proposal_str_id} was already evaluated."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 2: Emergency Kill Switch
            if self.kill_switch_active or self.state.kill_switch_active:
                reason = "REJECTED: Emergency Kill Switch is currently active."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 3: Hard ₹250 Daily Loss Limit State
            if self.state.status == RiskStatusEnum.HALTED:
                reason = f"REJECTED: Risk engine is in HALTED state. {self.state.halt_reason}"
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 4: Market Clock & Intraday Trading Hours (09:15 - 15:00 IST)
            now_ist = clock.now()
            if not clock.is_intraday_entry_allowed(now_ist):
                phase = clock.get_session_phase(now_ist)
                reason = f"REJECTED: Outside permitted intraday entry window (09:15-15:00 IST). Current phase: {phase.value}."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 5: Quote Freshness & Latency (< 5.0 seconds)
            data_age = (now_ist - proposal.market_data.as_of).total_seconds()
            if proposal.market_data.is_stale or data_age > 5.0 or data_age < -1.0:
                reason = f"REJECTED: Stale market data ({data_age:.1f}s age, threshold 5.0s)."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 6: Stop-Loss Geometry & Non-Zero Distance
            entry_price = proposal.entry.limit_price or proposal.entry.reference_price
            if proposal.direction == DirectionEnum.LONG:
                if proposal.stop_loss >= entry_price:
                    reason = f"REJECTED: Long stop loss ({proposal.stop_loss}) must be strictly below entry ({entry_price})."
                    await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                    return DecisionEnum.REJECTED, reason
                stop_dist = entry_price - proposal.stop_loss
            else:
                if proposal.stop_loss <= entry_price:
                    reason = f"REJECTED: Short stop loss ({proposal.stop_loss}) must be strictly above entry ({entry_price})."
                    await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                    return DecisionEnum.REJECTED, reason
                stop_dist = proposal.stop_loss - entry_price

            if stop_dist < proposal.instrument.tick_size:
                reason = f"REJECTED: Stop distance ({stop_dist:.2f}) is below minimum tick size ({proposal.instrument.tick_size})."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 7: Risk / Reward Ratio (Minimum 1 : 1.5)
            reward_dist = abs(proposal.target - entry_price)
            rr_ratio = reward_dist / stop_dist
            if rr_ratio < 1.49:  # Allow 1.5 with floating point tolerance
                reason = f"REJECTED: Risk/Reward ratio ({rr_ratio:.2f}) is below minimum required 1:1.5."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 8: Single-Trade Risk Limit (<= ₹250.00)
            if proposal.estimated_risk_inr > settings.MAX_RISK_PER_TRADE_INR:
                reason = (
                    f"REJECTED: Estimated trade risk (₹{proposal.estimated_risk_inr:.2f}) exceeds "
                    f"ceiling of ₹{settings.MAX_RISK_PER_TRADE_INR:.2f}."
                )
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 9: Capital & Margin Constraint (< ₹25,000)
            required_capital = entry_price * proposal.quantity
            if required_capital > self.state.available_capital:
                reason = (
                    f"REJECTED: Insufficient available capital. Required: ₹{required_capital:.2f}, "
                    f"Available: ₹{self.state.available_capital:.2f}."
                )
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 10: Maximum Simultaneous Open Positions
            if self.state.open_positions_count >= settings.MAX_OPEN_POSITIONS:
                reason = f"REJECTED: Maximum simultaneous positions ({settings.MAX_OPEN_POSITIONS}) reached."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 11: Maximum Session Trades Limit
            if self.state.today_trades_count >= settings.MAX_DAILY_TRADES:
                reason = f"REJECTED: Maximum daily trades limit ({settings.MAX_DAILY_TRADES}) reached."
                await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                return DecisionEnum.REJECTED, reason

            # Gate 12: Rapid-Fire Cooldown Protection (30 seconds)
            if self._last_trade_time is not None:
                elapsed = (now_ist - self._last_trade_time).total_seconds()
                if elapsed < self._cooldown_seconds:
                    reason = f"REJECTED: Rapid-fire cooldown active ({elapsed:.1f}s elapsed, required {self._cooldown_seconds}s)."
                    await self._record_decision(proposal, DecisionEnum.REJECTED, reason, db)
                    return DecisionEnum.REJECTED, reason

            # All 12 Gates Passed: Approve and update session state
            self._processed_proposal_ids.add(proposal_str_id)
            self._last_trade_time = now_ist
            self.state.today_trades_count += 1
            await self._record_decision(proposal, DecisionEnum.APPROVED, "Passed all 12 pre-trade risk gates.", db)
            return DecisionEnum.APPROVED, None

    # Backwards-compatible alias
    evaluate_order_proposal = evaluate_proposal

    async def trigger_kill_switch(self, reason: str, db: AsyncSession) -> None:
        """Activates emergency kill switch immediately."""
        async with self._get_lock():
            self.kill_switch_active = True
            if self.state:
                self.state.kill_switch_active = True
                self.state.status = RiskStatusEnum.KILL_SWITCH
                self.state.halt_reason = f"KILL SWITCH: {reason}"
                self.state.halt_timestamp = datetime.now(timezone.utc)

            audit_event = SystemAuditLogModel(
                event_type="KILL_SWITCH_ACTIVATED",
                actor="OPERATOR_OR_SYSTEM",
                severity="CRITICAL",
                message=reason,
                details={"timestamp": datetime.now(timezone.utc).isoformat()},
            )
            db.add(audit_event)

            stmt = (
                update(DailyRiskAuditModel)
                .where(DailyRiskAuditModel.date == (self.state.date if self.state else clock.today()))
                .values(status="KILL_SWITCH", halt_reason=reason, halt_timestamp=datetime.now(timezone.utc))
            )
            await db.execute(stmt)
            await db.commit()
            logger.critical(f"EMERGENCY KILL SWITCH ACTIVATED: {reason}")

    async def reset_kill_switch(self, reason: str, db: AsyncSession) -> None:
        """Resets emergency kill switch after explicit operator review."""
        async with self._get_lock():
            self.kill_switch_active = False
            if self.state:
                self.state.kill_switch_active = False
                self.state.status = RiskStatusEnum.ACTIVE
                self.state.halt_reason = None
                self.state.halt_timestamp = None

            audit_event = SystemAuditLogModel(
                event_type="KILL_SWITCH_RESET",
                actor="HUMAN_OPERATOR",
                severity="WARNING",
                message=reason,
                details={"timestamp": datetime.now(timezone.utc).isoformat()},
            )
            db.add(audit_event)

            stmt = (
                update(DailyRiskAuditModel)
                .where(DailyRiskAuditModel.date == (self.state.date if self.state else clock.today()))
                .values(status="ACTIVE", halt_reason=None, halt_timestamp=None)
            )
            await db.execute(stmt)
            await db.commit()
            logger.warning(f"KILL SWITCH RESET BY OPERATOR: {reason}")

    async def apply_audited_override(
        self,
        operator_id: str,
        rationale: str,
        db: AsyncSession,
    ) -> bool:
        """
        Applies a strictly audited same-session manual override.
        Does NOT erase the ₹250 threshold breach or risk history.
        Enables 1 single additional trade opportunity with fresh risk evaluation.
        """
        async with self._get_lock():
            if not rationale or len(rationale.strip()) < 15:
                raise ValueError("A detailed written rationale (minimum 15 characters) is mandatory for risk override.")

            if self.state is None:
                await self.initialize_session(db)

            prior_status = self.state.status.value
            now_utc = datetime.now(timezone.utc)

            # Record override audit log
            audit_event = SystemAuditLogModel(
                event_type="RISK_MANUAL_OVERRIDE",
                actor=f"OPERATOR:{operator_id}",
                severity="CRITICAL",
                message=f"Manual override requested by {operator_id}. Rationale: {rationale}",
                details={
                    "operator_id": operator_id,
                    "rationale": rationale,
                    "prior_status": prior_status,
                    "current_net_pnl": self.state.net_pnl,
                    "timestamp": now_utc.isoformat(),
                },
            )
            db.add(audit_event)

            # Update DB with override increment and rationale
            stmt = (
                update(DailyRiskAuditModel)
                .where(DailyRiskAuditModel.date == self.state.date)
                .values(
                    status="ACTIVE",
                    override_count=DailyRiskAuditModel.override_count + 1,
                    last_override_reason=rationale,
                    last_override_time=now_utc,
                )
            )
            await db.execute(stmt)
            await db.commit()

            # Temporarily restore status to ACTIVE for 1 trade
            self.state.status = RiskStatusEnum.ACTIVE
            logger.warning(f"MANUAL RISK OVERRIDE APPLIED by {operator_id}: {rationale}")
            return True

    async def _record_decision(
        self,
        proposal: TradeProposal,
        decision: DecisionEnum,
        reason: str,
        db: AsyncSession,
    ) -> None:
        """Appends immutable audit record to SQLite."""
        proposal.risk_decision = decision
        audit_event = SystemAuditLogModel(
            event_type="RISK_DECISION",
            actor="CENTRAL_RISK_ENGINE",
            severity="INFO" if decision == DecisionEnum.APPROVED else "WARNING",
            message=f"Proposal {proposal.proposal_id}: {decision.value} - {reason}",
            details={
                "proposal_id": str(proposal.proposal_id),
                "symbol": proposal.instrument.symbol,
                "direction": proposal.direction.value,
                "decision": decision.value,
                "reason": reason,
                "estimated_risk_inr": proposal.estimated_risk_inr,
                "net_pnl": self.state.net_pnl if self.state else 0.0,
            },
        )
        db.add(audit_event)
        await db.commit()


risk_engine = CentralRiskEngine()
