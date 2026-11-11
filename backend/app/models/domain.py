"""
Typed Domain Models & Schema Definitions
Strict adherence to Trade Proposal Schema v1.0 and Indian Market Segment specifications.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator, model_validator


class ExchangeEnum(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    MCX = "MCX"


class SegmentEnum(str, Enum):
    EQ = "EQ"
    FO = "FO"
    COM = "COM"


class DirectionEnum(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderTypeEnum(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL_M"


class DecisionEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExecutionModeEnum(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class RiskStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    HALTED = "HALTED"
    KILL_SWITCH = "KILL_SWITCH"


# ------------------------------------------------------------------------------
# Core Components
# ------------------------------------------------------------------------------

class Instrument(BaseModel):
    exchange: ExchangeEnum
    segment: SegmentEnum
    symbol: str
    instrument_key: str
    expiry: Optional[date] = None
    lot_size: int = Field(default=1, ge=1)
    tick_size: float = Field(default=0.05, gt=0.0)
    is_tradable: bool = True


class StrategyInfo(BaseModel):
    name: str
    version: str = "1.0"


class MarketDataProvenance(BaseModel):
    as_of: datetime
    source: str
    is_stale: bool = False
    latency_ms: Optional[float] = None


class EntryDetails(BaseModel):
    order_type: OrderTypeEnum
    reference_price: float = Field(gt=0.0)
    limit_price: Optional[float] = Field(default=None, gt=0.0)


class AgentAssessment(BaseModel):
    agent_name: str
    stance: str  # BULLISH | BEARISH | NEUTRAL | NO_SIGNAL
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    timestamp: datetime


# ------------------------------------------------------------------------------
# Trade Proposal Contract (Version 1.0)
# ------------------------------------------------------------------------------

class TradeProposal(BaseModel):
    schema_version: str = "1.0"
    proposal_id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    instrument: Instrument
    direction: DirectionEnum
    strategy: StrategyInfo
    timeframe: str
    market_data: MarketDataProvenance
    entry: EntryDetails
    stop_loss: float = Field(gt=0.0)
    target: float = Field(gt=0.0)
    quantity: int = Field(gt=0)
    estimated_risk_inr: float = Field(gt=0.0)
    estimated_reward_inr: float = Field(gt=0.0)
    estimated_costs_inr: float = Field(ge=0.0)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    agent_statuses: List[AgentAssessment] = Field(default_factory=list)
    risk_decision: DecisionEnum = DecisionEnum.PENDING
    human_decision: DecisionEnum = DecisionEnum.PENDING
    execution_mode: ExecutionModeEnum = ExecutionModeEnum.PAPER

    @model_validator(mode="after")
    def validate_price_levels_and_risk(self) -> "TradeProposal":
        entry_price = self.entry.limit_price or self.entry.reference_price
        
        # Long direction invariants
        if self.direction == DirectionEnum.LONG:
            if self.stop_loss >= entry_price:
                raise ValueError(
                    f"Invalid LONG levels: stop_loss ({self.stop_loss}) must be below entry ({entry_price})."
                )
            if self.target <= entry_price:
                raise ValueError(
                    f"Invalid LONG levels: target ({self.target}) must be above entry ({entry_price})."
                )
        
        # Short direction invariants
        elif self.direction == DirectionEnum.SHORT:
            if self.stop_loss <= entry_price:
                raise ValueError(
                    f"Invalid SHORT levels: stop_loss ({self.stop_loss}) must be above entry ({entry_price})."
                )
            if self.target >= entry_price:
                raise ValueError(
                    f"Invalid SHORT levels: target ({self.target}) must be below entry ({entry_price})."
                )

        # Risk verification: estimated risk must align with stop loss distance
        calculated_risk = abs(entry_price - self.stop_loss) * self.quantity
        if abs(calculated_risk - self.estimated_risk_inr) > 1.0:
            raise ValueError(
                f"estimated_risk_inr ({self.estimated_risk_inr}) does not match "
                f"stop distance * quantity ({calculated_risk:.2f})."
            )

        return self


# ------------------------------------------------------------------------------
# Risk & Portfolio State
# ------------------------------------------------------------------------------

class DailyRiskState(BaseModel):
    date: date
    status: RiskStatusEnum = RiskStatusEnum.ACTIVE
    starting_capital: float
    available_capital: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_charges: float = 0.0
    net_pnl: float = 0.0
    halt_reason: Optional[str] = None
    halt_timestamp: Optional[datetime] = None
    open_positions_count: int = 0
    today_trades_count: int = 0
    kill_switch_active: bool = False

    def calculate_net_pnl(self) -> float:
        self.net_pnl = round(self.realized_pnl + self.unrealized_pnl - self.total_charges, 2)
        return self.net_pnl

