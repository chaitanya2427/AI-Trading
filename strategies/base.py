"""
Base Strategy Definition & Candidate Signal Contracts
All quantitative trading strategies inherit from BaseStrategy and produce typed StrategySignals.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import pandas as pd

from backend.app.models.domain import DirectionEnum, Instrument


class StrategySignal(BaseModel):
    """Raw signal produced by a deterministic strategy before risk gate evaluation."""
    strategy_name: str
    strategy_version: str = "1.0"
    direction: DirectionEnum
    timeframe: str
    entry_price: float = Field(gt=0.0)
    stop_loss: float = Field(gt=0.0)
    target: float = Field(gt=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)


class BaseStrategy(ABC):
    """
    Abstract Base Class for deterministic quantitative strategies.
    Strategies never submit orders directly; they return advisory StrategySignals.
    """

    def __init__(self, name: str, version: str = "1.0", min_candles_required: int = 30):
        self.name = name
        self.version = version
        self.min_candles_required = min_candles_required

    def has_sufficient_data(self, candles: pd.DataFrame) -> bool:
        """Verifies candle count meets minimum statistical threshold."""
        return len(candles) >= self.min_candles_required

    @abstractmethod
    def evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        timeframe: str = "5m",
    ) -> Optional[StrategySignal]:
        """
        Evaluates validated candles and emits a StrategySignal if entry conditions are met.
        Returns None if no trade setup is detected.
        """
        pass

