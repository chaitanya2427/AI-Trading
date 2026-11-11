"""
Unit tests for Indian Market Statutory Costs and Conservative Position Sizing.
"""

import pytest
from backend.app.models.domain import ExchangeEnum, Instrument, SegmentEnum
from execution.costs import IndianMarketCostCalculator, PositionSizer

EQUITY_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.EQ,
    symbol="RELIANCE",
    instrument_key="NSE_EQ|INE002A01018",
    lot_size=1,
    tick_size=0.05,
)

OPTIONS_INST = Instrument(
    exchange=ExchangeEnum.NSE,
    segment=SegmentEnum.FO,
    symbol="NIFTY26NOV24000CE",
    instrument_key="NSE_FO|NIFTY26NOV24000CE",
    lot_size=25,
    tick_size=0.05,
)


def test_equity_intraday_statutory_costs():
    # Buy 10 shares of RELIANCE at 2500, Sell at 2520
    # Turnover Buy: 25,000, Turnover Sell: 25,200. Total Turnover: 50,200
    costs = IndianMarketCostCalculator.calculate_round_trip_costs(
        instrument=EQUITY_INST,
        entry_price=2500.0,
        exit_price=2520.0,
        quantity=10,
    )

    # Brokerage: 0.05% of 25,000 = 12.50 (entry), 0.05% of 25,200 = 12.60 (exit) -> Total = 25.10
    assert costs["brokerage"] == 25.10
    # STT on sell: 0.025% of 25,200 = 6.30
    assert costs["stt"] == 6.30
    # GST on brokerage + exchange + sebi (18%)
    assert costs["gst"] > 0.0
    # Stamp duty on buy: 0.003% of 25,000 = 0.75
    assert costs["stamp_duty"] == 0.75
    # Total costs must be non-zero and reasonable (< 100 for a 10-share trade)
    assert 30.0 < costs["total_costs"] < 50.0


def test_options_intraday_statutory_costs():
    # Buy 1 lot (25 qty) of Nifty Call at 100, Sell at 120
    # Turnover Buy: 2,500, Turnover Sell: 3,000. Total: 5,500
    costs = IndianMarketCostCalculator.calculate_round_trip_costs(
        instrument=OPTIONS_INST,
        entry_price=100.0,
        exit_price=120.0,
        quantity=25,
    )

    # Brokerage: Flat ₹20 per executed leg -> ₹40.00
    assert costs["brokerage"] == 40.00
    # STT: 0.1% on sell premium: 0.001 * 3,000 = 3.00
    assert costs["stt"] == 3.00
    # Total costs includes GST (18%)
    assert costs["total_costs"] > 45.0


def test_position_sizing_respects_max_risk_250_inr():
    # Entry: 2500, Stop Loss: 2475 (Stop distance = ₹25.00)
    # Available Capital: 25,000
    # Max risk allowed: ₹250.00
    # Max shares by risk: 250 / 25 = 10 shares
    qty, risk_inr = PositionSizer.calculate_quantity(
        instrument=EQUITY_INST,
        entry_price=2500.0,
        stop_loss=2475.0,
        available_capital=25000.0,
        max_risk_inr=250.0,
    )

    assert qty == 10
    assert risk_inr == 250.0  # 10 * 25.00 = 250.00


def test_position_sizing_respects_capital_ceiling():
    # Entry: 2500, Stop Loss: 2495 (Stop distance = ₹5.00)
    # By risk: 250 / 5 = 50 shares
    # Capital needed for 50 shares: 50 * 2500 = 125,000 (Exceeds 25,000 capital!)
    # Max shares by capital: 25,000 / 2500 = 10 shares
    qty, risk_inr = PositionSizer.calculate_quantity(
        instrument=EQUITY_INST,
        entry_price=2500.0,
        stop_loss=2495.0,
        available_capital=25000.0,
        max_risk_inr=250.0,
    )

    assert qty == 10
    assert risk_inr == 50.0  # 10 * 5.00 = 50.00 (Well within ₹250 limit)


def test_position_sizing_fo_lot_multiples():
    # Options lot size = 25
    # Option premium: 50, Stop: 40 (Stop distance = 10)
    # Max risk = 250 -> 250 / 10 = 25 shares = 1 lot of 25
    qty, risk_inr = PositionSizer.calculate_quantity(
        instrument=OPTIONS_INST,
        entry_price=50.0,
        stop_loss=40.0,
        available_capital=25000.0,
        max_risk_inr=250.0,
    )

    assert qty == 25  # Exactly 1 lot of 25
    assert risk_inr == 250.0

