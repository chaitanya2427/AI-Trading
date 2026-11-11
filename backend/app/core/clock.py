"""
Deterministic Indian Market Session Clock (NSE / BSE)
Provides market session awareness, exchange holiday calendars, and timeframe boundary calculations.
Supports both live system clock and simulated time injection for backtesting.
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Optional, Set
from zoneinfo import ZoneInfo

IST_TZ = ZoneInfo("Asia/Kolkata")

# Standard Exchange Trading Session Times (IST)
MARKET_PRE_OPEN_START = time(9, 0)
MARKET_PRE_OPEN_END = time(9, 8)
MARKET_OPEN = time(9, 15)
MARKET_INTRADAY_ENTRY_CUTOFF = time(15, 0)
MARKET_SQUARE_OFF = time(15, 15)
MARKET_CLOSE = time(15, 30)
MARKET_POST_CLOSE_START = time(15, 40)
MARKET_POST_CLOSE_END = time(16, 0)

# Exchange Holidays for NSE/BSE (2026/2025/2024 representative calendar)
EXCHANGE_HOLIDAYS: Set[date] = {
    # 2026 Holidays
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 3),   # Mahashivratri
    date(2026, 3, 20),  # Id-Ul-Fitr
    date(2026, 3, 27),  # Good Friday
    date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),   # Maharashtra Day
    date(2026, 5, 27),  # Bakri Id
    date(2026, 6, 26),  # Muharram
    date(2026, 8, 15),  # Independence Day
    date(2026, 9, 4),   # Ganesh Chaturthi
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti
    date(2026, 10, 20), # Dussehra
    date(2026, 11, 8),  # Diwali Laxmi Pujan (Muhurat session separate)
    date(2026, 11, 10), # Diwali Balipratipada
    date(2026, 11, 24), # Gurunanak Jayanti
    date(2026, 12, 25), # Christmas
}


class MarketSessionPhase(str, Enum):
    CLOSED = "CLOSED"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    PRE_OPEN = "PRE_OPEN"
    PRE_OPEN_BUFFER = "PRE_OPEN_BUFFER"
    REGULAR_TRADING = "REGULAR_TRADING"
    INTRADAY_CLOSING = "INTRADAY_CLOSING"  # Between 15:00 and 15:15
    SQUARE_OFF_WINDOW = "SQUARE_OFF_WINDOW"  # Between 15:15 and 15:30
    POST_CLOSE = "POST_CLOSE"


class MarketClock:
    """
    Deterministic clock for Indian financial markets.
    Can operate in live mode or simulated mode (with injected datetime).
    """

    def __init__(self, simulated_time: Optional[datetime] = None):
        self._simulated_time: Optional[datetime] = simulated_time

    def set_simulated_time(self, dt: Optional[datetime]) -> None:
        """Sets or resets the simulated time."""
        if dt is not None and dt.tzinfo is None:
            self._simulated_time = dt.replace(tzinfo=IST_TZ)
        else:
            self._simulated_time = dt

    def now(self) -> datetime:
        """Returns the current IST time (live or simulated)."""
        if self._simulated_time is not None:
            return self._simulated_time
        return datetime.now(IST_TZ)

    def today(self) -> date:
        """Returns the current IST date."""
        return self.now().date()

    def is_weekend(self, dt: Optional[datetime] = None) -> bool:
        """Saturday (5) or Sunday (6)."""
        current_dt = dt or self.now()
        return current_dt.weekday() in (5, 6)

    def is_holiday(self, dt: Optional[datetime] = None) -> bool:
        """Returns True if date is an exchange holiday."""
        current_date = (dt or self.now()).date()
        return current_date in EXCHANGE_HOLIDAYS

    def is_trading_day(self, dt: Optional[datetime] = None) -> bool:
        """Trading day if neither weekend nor exchange holiday."""
        current_dt = dt or self.now()
        return not (self.is_weekend(current_dt) or self.is_holiday(current_dt))

    def get_session_phase(self, dt: Optional[datetime] = None) -> MarketSessionPhase:
        """Determines the active session phase."""
        current_dt = dt or self.now()
        if self.is_weekend(current_dt):
            return MarketSessionPhase.WEEKEND
        if self.is_holiday(current_dt):
            return MarketSessionPhase.HOLIDAY

        current_time = current_dt.time()
        if current_time < MARKET_PRE_OPEN_START:
            return MarketSessionPhase.CLOSED
        if MARKET_PRE_OPEN_START <= current_time < MARKET_PRE_OPEN_END:
            return MarketSessionPhase.PRE_OPEN
        if MARKET_PRE_OPEN_END <= current_time < MARKET_OPEN:
            return MarketSessionPhase.PRE_OPEN_BUFFER
        if MARKET_OPEN <= current_time < MARKET_INTRADAY_ENTRY_CUTOFF:
            return MarketSessionPhase.REGULAR_TRADING
        if MARKET_INTRADAY_ENTRY_CUTOFF <= current_time < MARKET_SQUARE_OFF:
            return MarketSessionPhase.INTRADAY_CLOSING
        if MARKET_SQUARE_OFF <= current_time < MARKET_CLOSE:
            return MarketSessionPhase.SQUARE_OFF_WINDOW
        if MARKET_POST_CLOSE_START <= current_time < MARKET_POST_CLOSE_END:
            return MarketSessionPhase.POST_CLOSE
        return MarketSessionPhase.CLOSED

    def is_market_open(self, dt: Optional[datetime] = None) -> bool:
        """Returns True if market is in regular trading session (09:15 - 15:30)."""
        phase = self.get_session_phase(dt)
        return phase in (
            MarketSessionPhase.REGULAR_TRADING,
            MarketSessionPhase.INTRADAY_CLOSING,
            MarketSessionPhase.SQUARE_OFF_WINDOW,
        )

    def is_intraday_entry_allowed(self, dt: Optional[datetime] = None) -> bool:
        """
        New intraday entries are strictly allowed between 09:15 and 15:00 IST.
        After 15:00 IST, no new positions may be initiated.
        """
        return self.get_session_phase(dt) == MarketSessionPhase.REGULAR_TRADING

    def is_squareoff_time(self, dt: Optional[datetime] = None) -> bool:
        """Returns True if we are in or past the mandatory square-off window (>= 15:15 IST)."""
        current_dt = dt or self.now()
        if not self.is_trading_day(current_dt):
            return False
        return current_dt.time() >= MARKET_SQUARE_OFF


# Global Clock Instance
clock = MarketClock()

