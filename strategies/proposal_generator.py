"""
Trade Proposal Generator
Transforms StrategySignals into schema-validated TradeProposal contracts (Schema Version 1.0).
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.models.domain import (
    AgentAssessment,
    DecisionEnum,
    EntryDetails,
    ExecutionModeEnum,
    Instrument,
    MarketDataProvenance,
    OrderTypeEnum,
    StrategyInfo,
    TradeProposal,
)
from execution.costs import cost_calculator, position_sizer
from strategies.base import StrategySignal


class TradeProposalGenerator:
    """Assembles and validates complete TradeProposal contracts."""

    @staticmethod
    def create_proposal(
        signal: StrategySignal,
        instrument: Instrument,
        provenance: MarketDataProvenance,
        available_capital: float = settings.STARTING_CAPITAL_INR,
        agent_assessments: Optional[List[AgentAssessment]] = None,
    ) -> Optional[TradeProposal]:
        """
        Creates a TradeProposal with deterministic sizing and fee estimation.
        Returns None if risk bounds cannot be satisfied (e.g. quantity == 0).
        """
        # Sizing calculation
        quantity, actual_risk = position_sizer.calculate_quantity(
            instrument=instrument,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            available_capital=available_capital,
            max_risk_inr=settings.MAX_RISK_PER_TRADE_INR,
        )

        if quantity <= 0:
            return None

        # Estimated reward
        reward_dist = abs(signal.target - signal.entry_price)
        estimated_reward = round(reward_dist * quantity, 2)

        # Estimated round-trip costs
        costs = cost_calculator.calculate_round_trip_costs(
            instrument=instrument,
            entry_price=signal.entry_price,
            exit_price=signal.target,
            quantity=quantity,
        )

        proposal = TradeProposal(
            schema_version="1.0",
            proposal_id=uuid4(),
            created_at=clock.now(),
            instrument=instrument,
            direction=signal.direction,
            strategy=StrategyInfo(name=signal.strategy_name, version=signal.strategy_version),
            timeframe=signal.timeframe,
            market_data=provenance,
            entry=EntryDetails(
                order_type=OrderTypeEnum.LIMIT,
                reference_price=signal.entry_price,
                limit_price=signal.entry_price,
            ),
            stop_loss=signal.stop_loss,
            target=signal.target,
            quantity=quantity,
            estimated_risk_inr=actual_risk,
            estimated_reward_inr=estimated_reward,
            estimated_costs_inr=costs["total_costs"],
            supporting_evidence=signal.supporting_evidence,
            contradicting_evidence=signal.contradicting_evidence,
            agent_statuses=agent_assessments or [],
            risk_decision=DecisionEnum.PENDING,
            human_decision=DecisionEnum.PENDING,
            execution_mode=ExecutionModeEnum.PAPER,
        )

        return proposal


proposal_generator = TradeProposalGenerator()

