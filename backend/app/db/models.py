"""
SQLAlchemy ORM Models for Persistence
Stores trade proposals, paper orders, positions, daily risk audit logs, and immutable system audit trails.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TradeProposalModel(Base):
    __tablename__ = "trade_proposals"

    proposal_id = Column(String(36), primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), nullable=False)
    segment = Column(String(16), nullable=False)
    direction = Column(String(8), nullable=False)
    strategy_name = Column(String(64), nullable=False)
    timeframe = Column(String(16), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    estimated_risk_inr = Column(Float, nullable=False)
    estimated_reward_inr = Column(Float, nullable=False)
    estimated_costs_inr = Column(Float, nullable=False)
    risk_decision = Column(String(16), nullable=False, default="PENDING")
    risk_reason = Column(String(256), nullable=True)
    human_decision = Column(String(16), nullable=False, default="PENDING")
    human_reason = Column(String(256), nullable=True)
    execution_mode = Column(String(16), nullable=False, default="PAPER")
    raw_payload = Column(JSON, nullable=False)

    orders = relationship("PaperOrderModel", back_populates="proposal")


class PaperOrderModel(Base):
    __tablename__ = "paper_orders"

    order_id = Column(String(36), primary_key=True, index=True)
    proposal_id = Column(String(36), ForeignKey("trade_proposals.proposal_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String(64), nullable=False)
    exchange = Column(String(16), nullable=False)
    direction = Column(String(8), nullable=False)
    order_type = Column(String(16), nullable=False)
    quantity = Column(Integer, nullable=False)
    reference_price = Column(Float, nullable=False)
    filled_price = Column(Float, nullable=True)
    slippage_inr = Column(Float, default=0.0)
    charges_inr = Column(Float, default=0.0)
    status = Column(String(16), nullable=False, default="NEW")  # NEW, SUBMITTED, FILLED, REJECTED, CANCELLED
    reject_reason = Column(String(256), nullable=True)

    proposal = relationship("TradeProposalModel", back_populates="orders")


class PaperPositionModel(Base):
    __tablename__ = "paper_positions"

    position_id = Column(String(36), primary_key=True, index=True)
    symbol = Column(String(64), nullable=False, index=True)
    exchange = Column(String(16), nullable=False)
    direction = Column(String(8), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    total_charges = Column(Float, default=0.0)
    status = Column(String(16), nullable=False, default="OPEN")  # OPEN, CLOSED
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_reason = Column(String(64), nullable=True)


class DailyRiskAuditModel(Base):
    __tablename__ = "daily_risk_audit"

    date = Column(Date, primary_key=True, index=True)
    status = Column(String(16), nullable=False, default="ACTIVE")  # ACTIVE, HALTED, KILL_SWITCH
    starting_capital = Column(Float, nullable=False)
    available_capital = Column(Float, nullable=False)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_charges = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    halt_reason = Column(String(256), nullable=True)
    halt_timestamp = Column(DateTime, nullable=True)
    override_count = Column(Integer, default=0)
    last_override_reason = Column(Text, nullable=True)
    last_override_time = Column(DateTime, nullable=True)


class SystemAuditLogModel(Base):
    __tablename__ = "system_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), nullable=False)  # RISK_ENGINE, HUMAN_OPERATOR, SYSTEM, AGENT
    severity = Column(String(16), nullable=False, default="INFO")  # INFO, WARNING, CRITICAL
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)

