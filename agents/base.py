"""
Multi-Agent Base Architecture
Enforces fail-safe timeouts (2.0s ceiling), structured AgentAssessment outputs, and error isolation.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd

from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract Base Class for specialist advisory agents.
    Agents produce non-binding opinions. Under no circumstances can an agent submit orders.
    """

    def __init__(self, name: str, timeout_seconds: float = 2.0):
        self.name = name
        self.timeout_seconds = timeout_seconds

    async def assess(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Optional[Dict] = None,
    ) -> AgentAssessment:
        """
        Executes agent evaluation with strict timeout and exception isolation.
        """
        now = clock.now()
        try:
            assessment = await asyncio.wait_for(
                self._evaluate(candles, instrument, context or {}),
                timeout=self.timeout_seconds,
            )
            return assessment
        except asyncio.TimeoutError:
            logger.warning(f"Agent {self.name} timed out after {self.timeout_seconds}s.")
            return AgentAssessment(
                agent_name=self.name,
                stance="NO_SIGNAL",
                confidence=0.0,
                evidence=[f"Agent execution exceeded timeout limit ({self.timeout_seconds}s)"],
                timestamp=now,
            )
        except Exception as e:
            logger.error(f"Agent {self.name} encountered error: {e}")
            return AgentAssessment(
                agent_name=self.name,
                stance="NO_SIGNAL",
                confidence=0.0,
                evidence=[f"Agent failed safely: {type(e).__name__}"],
                timestamp=now,
            )

    @abstractmethod
    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        """Subclass implementation of specialist analysis."""
        pass

