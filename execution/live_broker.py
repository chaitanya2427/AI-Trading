"""
Live Broker Adapter (Safety Sandbox Guard)
Ensures real-money live order execution is physically and architecturally barred.
Any invocation throws a fatal SafetyViolationError fail-closed.
"""

from typing import Any, Dict
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger("execution.live_broker")


class SafetyViolationError(RuntimeError):
    """Raised when an unauthorized or unsafe live trading action is attempted."""
    pass


class LiveBrokerAdapter:
    """
    Isolated live broker adapter stub.
    Permanently fail-closed. Live trading is barred by design in this build.
    """

    def __init__(self) -> None:
        if not settings.LIVE_TRADING_ENABLED or settings.EXECUTION_MODE != "LIVE":
            logger.critical(
                "CRITICAL SECURITY: Unauthorized attempt to instantiate LiveBrokerAdapter! "
                "LIVE_TRADING_ENABLED=%s, EXECUTION_MODE=%s",
                settings.LIVE_TRADING_ENABLED,
                settings.EXECUTION_MODE,
            )
            raise SafetyViolationError(
                "FATAL SAFETY VIOLATION: Real-money live trading is disabled by design. "
                "LIVE_TRADING_ENABLED must be False and EXECUTION_MODE must be PAPER."
            )

    async def place_order(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Fail-closed barrier preventing any live order placement."""
        raise SafetyViolationError(
            "FATAL SAFETY VIOLATION: Live order placement is blocked. "
            "No live orders are permitted in this build."
        )

    async def cancel_order(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Fail-closed barrier preventing live cancellation."""
        raise SafetyViolationError("FATAL SAFETY VIOLATION: Live order operations are blocked.")

    async def get_positions(self) -> Dict[str, Any]:
        """Fail-closed barrier preventing live position queries."""
        raise SafetyViolationError("FATAL SAFETY VIOLATION: Live broker access is blocked.")

