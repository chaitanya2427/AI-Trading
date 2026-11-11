"""
Unit tests for Trade Proposal Schema v1.0 and invariant validations.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from pydantic import ValidationError

from backend.app.models.domain import (
    DirectionEnum,
    EntryDetails,
    ExchangeEnum,
    ExecutionModeEnum,
    Instrument,
    MarketDataProvenance,
    OrderTypeEnum,
    SegmentEnum,
    StrategyInfo,
    TradeProposal,
)

IST = ZoneInfo("Asia/Kolkata")


def create_valid_proposal(direction=DirectionEnum.LONG):
    now = datetime(2026, 11, 4, 10, 0, tzinfo=IST)
    if direction == DirectionEnum.LONG:
        entry_price = 2500.0
        stop_loss = 2490.0  # ₹10 stop distance
        target = 2520.0
    else:
        entry_price = 2500.0
        stop_loss = 2510.0  # ₹10 stop distance
        target = 2480.0

    qty = 10
    risk_inr = 100.0  # ₹10 * 10 = ₹100

    return TradeProposal(
        created_at=now,
        instrument=Instrument(
            exchange=ExchangeEnum.NSE,
            segment=SegmentEnum.EQ,
            symbol="RELIANCE",
            instrument_key="NSE_EQ|INE002A01018",
            lot_size=1,
            tick_size=0.05,
        ),
        direction=direction,
        strategy=StrategyInfo(name="VWAP_CONTINUATION", version="1.0"),
        timeframe="5m",
        market_data=MarketDataProvenance(
            as_of=now,
            source="UPSTOX_WS_FEED_V3",
            is_stale=False,
        ),
        entry=EntryDetails(
            order_type=OrderTypeEnum.LIMIT,
            reference_price=entry_price,
            limit_price=entry_price,
        ),
        stop_loss=stop_loss,
        target=target,
        quantity=qty,
        estimated_risk_inr=risk_inr,
        estimated_reward_inr=200.0,
        estimated_costs_inr=25.0,
        execution_mode=ExecutionModeEnum.PAPER,
    )


def test_valid_long_proposal():
    prop = create_valid_proposal(DirectionEnum.LONG)
    assert prop.schema_version == "1.0"
    assert prop.direction == DirectionEnum.LONG
    assert prop.stop_loss == 2490.0
    assert prop.target == 2520.0


def test_valid_short_proposal():
    prop = create_valid_proposal(DirectionEnum.SHORT)
    assert prop.direction == DirectionEnum.SHORT
    assert prop.stop_loss == 2510.0
    assert prop.target == 2480.0


def test_invalid_long_stop_loss_above_entry():
    with pytest.raises(ValidationError):
        # Stop loss at 2510 is ABOVE entry 2500 for a LONG
        prop = create_valid_proposal(DirectionEnum.LONG)
        TradeProposal(
            **{
                **prop.model_dump(),
                "stop_loss": 2510.0,
                "estimated_risk_inr": 100.0,
            }
        )


def test_invalid_short_stop_loss_below_entry():
    with pytest.raises(ValidationError):
        # Stop loss at 2490 is BELOW entry 2500 for a SHORT
        prop = create_valid_proposal(DirectionEnum.SHORT)
        TradeProposal(
            **{
                **prop.model_dump(),
                "stop_loss": 2490.0,
                "estimated_risk_inr": 100.0,
            }
        )


def test_invalid_risk_calculation_mismatch():
    with pytest.raises(ValidationError):
        # Stop distance is 10, qty is 10 -> true risk is 100, but reporting 500
        prop = create_valid_proposal(DirectionEnum.LONG)
        TradeProposal(
            **{
                **prop.model_dump(),
                "estimated_risk_inr": 500.0,
            }
        )

