"""
Market Data Sanitizer & Validator
Enforces mathematical price invariants, chronological sequence, gap detection, and staleness circuit-breaker.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import pandas as pd

from backend.app.core.clock import clock
from backend.app.models.domain import MarketDataProvenance

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class DataValidationError(Exception):
    """Raised when critical price invariant or structural anomaly is violated."""
    pass


class MarketDataValidator:
    """Deterministic validator for candles, ticks, and quotes."""

    @staticmethod
    def validate_candle_invariants(
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates standard OHLCV invariants:
        1. Low > 0
        2. High >= max(Open, Close)
        3. Low <= min(Open, Close)
        4. Volume >= 0
        """
        if low <= 0:
            return False, f"Invalid candle: Low ({low}) must be strictly positive."
        if open_ <= 0 or high <= 0 or close <= 0:
            return False, f"Invalid candle: Price values must be positive (O:{open_}, H:{high}, C:{close})."
        if high < max(open_, close):
            return False, f"Invalid candle: High ({high}) is lower than max(Open, Close) ({max(open_, close)})."
        if low > min(open_, close):
            return False, f"Invalid candle: Low ({low}) is higher than min(Open, Close) ({min(open_, close)})."
        if volume < 0:
            return False, f"Invalid candle: Volume ({volume}) cannot be negative."

        return True, None

    @staticmethod
    def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Validates, deduplicates, and sorts OHLCV DataFrame.
        Expected columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
        """
        if df.empty:
            return df

        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            raise DataValidationError(f"Missing required candle columns: {missing}")

        cleaned = df.copy()

        # Convert timestamp to IST datetime if string
        if not pd.api.types.is_datetime64_any_dtype(cleaned["timestamp"]):
            cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"])

        # Deduplicate and sort chronologically
        cleaned = cleaned.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # Invariant filtering
        valid_mask = (
            (cleaned["low"] > 0)
            & (cleaned["high"] >= cleaned[["open", "close"]].max(axis=1))
            & (cleaned["low"] <= cleaned[["open", "close"]].min(axis=1))
            & (cleaned["volume"] >= 0)
        )

        invalid_count = len(cleaned) - valid_mask.sum()
        if invalid_count > 0:
            logger.warning(f"Filtered out {invalid_count} corrupted candles violating OHLCV invariants.")
            cleaned = cleaned[valid_mask].reset_index(drop=True)

        return cleaned

    @staticmethod
    def detect_gaps(
        df: pd.DataFrame,
        timeframe_minutes: int = 5,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detects missing intraday candle intervals within regular trading sessions (09:15-15:30 IST).
        """
        if len(df) < 2:
            return []

        gaps: List[Tuple[datetime, datetime]] = []
        expected_delta = timedelta(minutes=timeframe_minutes)

        for i in range(1, len(df)):
            prev_ts = df.iloc[i - 1]["timestamp"]
            curr_ts = df.iloc[i]["timestamp"]

            # Only check within the same trading session
            if prev_ts.date() == curr_ts.date():
                delta = curr_ts - prev_ts
                if delta > expected_delta:
                    # Found gap
                    gaps.append((prev_ts, curr_ts))

        return gaps

    @staticmethod
    def check_quote_freshness(
        quote_timestamp: datetime,
        max_age_seconds: float = 5.0,
    ) -> MarketDataProvenance:
        """
        Determines quote freshness relative to IST clock.
        If delta > 5.0 seconds, flags is_stale = True.
        """
        now = clock.now()
        if quote_timestamp.tzinfo is None:
            quote_timestamp = quote_timestamp.replace(tzinfo=IST)

        age_seconds = (now - quote_timestamp).total_seconds()
        is_stale = age_seconds > max_age_seconds or age_seconds < -1.0  # Future timestamps also invalid

        return MarketDataProvenance(
            as_of=quote_timestamp,
            source="MARKET_FEED",
            is_stale=is_stale,
            latency_ms=round(max(0.0, age_seconds * 1000.0), 2),
        )


validator = MarketDataValidator()

