"""
Market Microstructure Specialist Agent
Analyzes order book depth, bid-ask spread, and order flow imbalance.
"""

from typing import Dict
import pandas as pd

from agents.base import BaseAgent
from backend.app.core.clock import clock
from backend.app.models.domain import AgentAssessment, Instrument


class MarketMicrostructureAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="MicrostructureAnalyst", timeout_seconds=2.0)

    async def _evaluate(
        self,
        candles: pd.DataFrame,
        instrument: Instrument,
        context: Dict,
    ) -> AgentAssessment:
        now = clock.now()
        book = context.get("order_book", {})
        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids or not asks:
            return AgentAssessment(
                agent_name=self.name,
                stance="NEUTRAL",
                confidence=0.50,
                evidence=["Level 2 depth not available in historical replay; relying on spread"],
                timestamp=now,
            )

        total_bid_vol = sum(b.get("quantity", 0) for b in bids)
        total_ask_vol = sum(a.get("quantity", 0) for a in asks)
        total_vol = total_bid_vol + total_ask_vol

        spread = book.get("spread", 0.05)
        evidence = [
            f"Top 5 depth: Bid Volume {total_bid_vol} vs Ask Volume {total_ask_vol}",
            f"Bid-Ask spread: ₹{spread:.2f}",
        ]

        # Order Flow Imbalance (OFI)
        if total_vol > 0:
            imbalance = (total_bid_vol - total_ask_vol) / total_vol
            evidence.append(f"Depth order flow imbalance: {imbalance:+.2f}")

            if imbalance > 0.25:
                stance = "BULLISH"
                confidence = round(0.50 + abs(imbalance) * 0.4, 2)
                evidence.append("Strong buyer bid depth absorption")
            elif imbalance < -0.25:
                stance = "BEARISH"
                confidence = round(0.50 + abs(imbalance) * 0.4, 2)
                evidence.append("Strong seller ask overhang")
            else:
                stance = "NEUTRAL"
                confidence = 0.50
        else:
            stance = "NEUTRAL"
            confidence = 0.50

        return AgentAssessment(
            agent_name=self.name,
            stance=stance,
            confidence=confidence,
            evidence=evidence,
            timestamp=now,
        )

