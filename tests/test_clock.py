"""
Unit tests for deterministic Indian Market Clock (NSE / BSE).
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from backend.app.core.clock import MarketClock, MarketSessionPhase

IST = ZoneInfo("Asia/Kolkata")


def test_clock_weekend_detection():
    clock = MarketClock()
    # 2026-11-07 is a Saturday
    saturday_dt = datetime(2026, 11, 7, 10, 0, tzinfo=IST)
    clock.set_simulated_time(saturday_dt)

    assert clock.is_weekend() is True
    assert clock.is_trading_day() is False
    assert clock.get_session_phase() == MarketSessionPhase.WEEKEND
    assert clock.is_market_open() is False


def test_clock_holiday_detection():
    clock = MarketClock()
    # 2026-01-26 is Republic Day (Monday)
    republic_day = datetime(2026, 1, 26, 11, 0, tzinfo=IST)
    clock.set_simulated_time(republic_day)

    assert clock.is_holiday() is True
    assert clock.is_trading_day() is False
    assert clock.get_session_phase() == MarketSessionPhase.HOLIDAY
    assert clock.is_market_open() is False


def test_clock_regular_trading_hours():
    clock = MarketClock()
    # 2026-11-04 is a Wednesday (Regular trading day) at 10:30 IST
    regular_dt = datetime(2026, 11, 4, 10, 30, tzinfo=IST)
    clock.set_simulated_time(regular_dt)

    assert clock.is_trading_day() is True
    assert clock.is_market_open() is True
    assert clock.is_intraday_entry_allowed() is True
    assert clock.is_squareoff_time() is False
    assert clock.get_session_phase() == MarketSessionPhase.REGULAR_TRADING


def test_clock_intraday_entry_cutoff():
    clock = MarketClock()
    # 15:05 IST on a regular trading day (Past 15:00 cutoff)
    cutoff_dt = datetime(2026, 11, 4, 15, 5, tzinfo=IST)
    clock.set_simulated_time(cutoff_dt)

    assert clock.is_market_open() is True
    # New intraday entries must be blocked
    assert clock.is_intraday_entry_allowed() is False
    assert clock.get_session_phase() == MarketSessionPhase.INTRADAY_CLOSING


def test_clock_square_off_window():
    clock = MarketClock()
    # 15:20 IST on a regular trading day (Square-off window 15:15-15:30)
    square_off_dt = datetime(2026, 11, 4, 15, 20, tzinfo=IST)
    clock.set_simulated_time(square_off_dt)

    assert clock.is_market_open() is True
    assert clock.is_intraday_entry_allowed() is False
    assert clock.is_squareoff_time() is True
    assert clock.get_session_phase() == MarketSessionPhase.SQUARE_OFF_WINDOW


def test_clock_pre_open_session():
    clock = MarketClock()
    # 09:05 IST
    pre_open_dt = datetime(2026, 11, 4, 9, 5, tzinfo=IST)
    clock.set_simulated_time(pre_open_dt)

    assert clock.is_trading_day() is True
    assert clock.is_market_open() is False
    assert clock.get_session_phase() == MarketSessionPhase.PRE_OPEN


def test_clock_after_hours():
    clock = MarketClock()
    # 16:30 IST
    after_hours_dt = datetime(2026, 11, 4, 16, 30, tzinfo=IST)
    clock.set_simulated_time(after_hours_dt)

    assert clock.is_market_open() is False
    assert clock.is_intraday_entry_allowed() is False
    assert clock.get_session_phase() == MarketSessionPhase.CLOSED

