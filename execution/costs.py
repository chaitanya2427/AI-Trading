"""
Indian Market Statutory Cost Calculator & Deterministic Position Sizer
Models Brokerage, STT, Exchange Turnover, GST, SEBI fees, and Stamp Duty.
"""

from typing import Dict, Tuple
from backend.app.core.config import settings
from backend.app.models.domain import DirectionEnum, Instrument, SegmentEnum


class IndianMarketCostCalculator:
    """Accurately calculates total round-trip statutory costs for Indian financial markets."""

    @staticmethod
    def calculate_round_trip_costs(
        instrument: Instrument,
        entry_price: float,
        exit_price: float,
        quantity: int,
    ) -> Dict[str, float]:
        """
        Calculates all round-trip fees (Buy + Sell).
        """
        turnover_entry = entry_price * quantity
        turnover_exit = exit_price * quantity
        total_turnover = turnover_entry + turnover_exit

        # 1. Brokerage
        if instrument.segment == SegmentEnum.EQ:
            # ₹20 or 0.05% whichever is lower per order leg
            brokerage_entry = min(20.0, turnover_entry * 0.0005)
            brokerage_exit = min(20.0, turnover_exit * 0.0005)
            total_brokerage = round(brokerage_entry + brokerage_exit, 2)
        else:
            # F&O Flat ₹20 per executed order leg
            total_brokerage = 40.00

        # 2. Securities Transaction Tax (STT) - Charged on SELL side for intraday
        if instrument.segment == SegmentEnum.EQ:
            stt = round(turnover_exit * 0.00025, 2)  # 0.025% on sell
        elif instrument.segment == SegmentEnum.FO:
            stt = round(turnover_exit * 0.001, 2)  # 0.1% on sell premium
        else:
            stt = 0.0

        # 3. Exchange Turnover Charges (NSE: ~0.00297%)
        if instrument.segment == SegmentEnum.EQ:
            exchange_turnover = round(total_turnover * 0.0000297, 2)
        elif instrument.segment == SegmentEnum.FO:
            exchange_turnover = round(total_turnover * 0.0003503, 2)
        else:
            exchange_turnover = round(total_turnover * 0.000026, 2)

        # 4. SEBI Turnover Charges (₹10 / Crore = 0.0001%)
        sebi_charges = round(total_turnover * 0.000001, 2)

        # 5. GST (18% on Brokerage + Exchange Turnover + SEBI Charges)
        gst = round((total_brokerage + exchange_turnover + sebi_charges) * 0.18, 2)

        # 6. Stamp Duty (Charged on BUY side only: 0.003%)
        stamp_duty = round(turnover_entry * 0.00003, 2)

        total_costs = round(
            total_brokerage + stt + exchange_turnover + sebi_charges + gst + stamp_duty,
            2,
        )

        return {
            "brokerage": total_brokerage,
            "stt": stt,
            "exchange_turnover": exchange_turnover,
            "sebi_charges": sebi_charges,
            "gst": gst,
            "stamp_duty": stamp_duty,
            "total_costs": total_costs,
        }


class PositionSizer:
    """Calculates safe, deterministic position sizing respecting ₹250 loss ceiling and available capital."""

    @staticmethod
    def calculate_quantity(
        instrument: Instrument,
        entry_price: float,
        stop_loss: float,
        available_capital: float,
        max_risk_inr: float = settings.MAX_RISK_PER_TRADE_INR,
    ) -> Tuple[int, float]:
        """
        Determines the maximum allowable quantity adhering to:
        1. Max risk per trade (<= ₹250)
        2. Available capital
        3. Instrument lot size
        Returns (quantity, calculated_risk_inr).
        """
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            return 0, 0.0

        # Max shares allowed by risk ceiling
        max_shares_by_risk = int(max_risk_inr / stop_distance)

        # Max shares allowed by cash capital
        max_shares_by_capital = int(available_capital / entry_price)

        shares = min(max_shares_by_risk, max_shares_by_capital)

        # Handle lot size multiples for F&O
        if instrument.lot_size > 1:
            lots = shares // instrument.lot_size
            shares = lots * instrument.lot_size

        if shares <= 0:
            return 0, 0.0

        calculated_risk = round(shares * stop_distance, 2)
        return shares, calculated_risk


cost_calculator = IndianMarketCostCalculator()
position_sizer = PositionSizer()

