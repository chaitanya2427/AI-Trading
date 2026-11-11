"""
Upstox API v2 / v3 Read-Only REST Client
Enforces rate limits (50 req/s), token lifecycle handling, and provenance tracking.
Includes fallback to synthetic fixtures when credentials are absent or network is unavailable.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import httpx
import pandas as pd

from backend.app.adapters.synthetic_feed import synthetic_feed
from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.models.domain import MarketDataProvenance

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

UPSTOX_BASE_URL = "https://api.upstox.com"


class UpstoxRateLimiter:
    """Token bucket rate limiter capping requests at 50 requests/sec."""

    def __init__(self, rate_limit: int = 45):  # Keep slight safety buffer below 50
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            if elapsed >= 1.0:
                self.tokens = self.rate_limit
                self.last_refill = now
            elif self.tokens < 1:
                sleep_time = 1.0 - elapsed
                await asyncio.sleep(sleep_time)
                self.tokens = self.rate_limit
                self.last_refill = time.monotonic()

            self.tokens -= 1


class UpstoxRestClient:
    """
    Read-only Upstox client for market quotes, candles, and option chains.
    Live order endpoints are strictly NOT implemented here.
    """

    def __init__(self):
        self.limiter = UpstoxRateLimiter()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
        }
        if settings.UPSTOX_ACCESS_TOKEN:
            headers["Authorization"] = f"Bearer {settings.UPSTOX_ACCESS_TOKEN}"
        return headers

    def is_configured(self) -> bool:
        """Returns True if a real access token is configured."""
        return bool(settings.UPSTOX_ACCESS_TOKEN and len(settings.UPSTOX_ACCESS_TOKEN) > 20)

    async def get_market_quote(self, instrument_key: str) -> Dict:
        """
        Fetches live LTP and market depth for an instrument.
        Falls back to synthetic fixture if credentials are not set.
        """
        if not self.is_configured():
            logger.debug(f"Upstox credentials not configured. Generating synthetic quote for {instrument_key}")
            symbol = instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
            return synthetic_feed.generate_quote(symbol, 2500.0)

        await self.limiter.acquire()
        url = f"{UPSTOX_BASE_URL}/v3/market-quote/quotes"
        params = {"instrument_key": instrument_key}

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self._get_headers(), params=params)
                latency_ms = (time.monotonic() - start_time) * 1000.0

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    quote_data = data.get(instrument_key.replace("|", ":"), {})
                    now = clock.now()
                    return {
                        "symbol": quote_data.get("symbol", instrument_key),
                        "ltp": quote_data.get("last_price", 0.0),
                        "ltt": quote_data.get("timestamp"),
                        "ltq": quote_data.get("volume", 0),
                        "depth": quote_data.get("depth", {}),
                        "provenance": MarketDataProvenance(
                            as_of=now,
                            source="UPSTOX_REST",
                            is_stale=False,
                            latency_ms=round(latency_ms, 2),
                        ).model_dump(),
                    }
                elif resp.status_code == 401:
                    logger.error("Upstox access token expired or invalid (HTTP 401).")
                elif resp.status_code == 429:
                    logger.warning("Upstox rate limit exceeded (HTTP 429). Backing off.")
        except Exception as e:
            logger.error(f"Error fetching Upstox market quote ({e}). Falling back to synthetic.")

        symbol = instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
        return synthetic_feed.generate_quote(symbol, 2500.0)

    async def get_intraday_candles(
        self,
        instrument_key: str,
        interval: str = "5minute",
    ) -> pd.DataFrame:
        """
        Fetches today's intraday candles for an instrument.
        Intervals: 1minute, 5minute, 15minute, 30minute.
        """
        if not self.is_configured():
            logger.debug(f"Using synthetic intraday candles for {instrument_key}")
            symbol = instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
            minutes = 5
            if "1m" in interval or "1minute" in interval:
                minutes = 1
            elif "15m" in interval or "15minute" in interval:
                minutes = 15
            return synthetic_feed.generate_candles(symbol=symbol, timeframe_minutes=minutes)

        await self.limiter.acquire()
        url = f"{UPSTOX_BASE_URL}/v2/historical-candle/intraday/{instrument_key}/{interval}"

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    candles = resp.json().get("data", {}).get("candles", [])
                    # Upstox candle format: [timestamp, open, high, low, close, volume, open_interest]
                    df_data = []
                    for c in reversed(candles):
                        df_data.append(
                            {
                                "timestamp": c[0],
                                "open": float(c[1]),
                                "high": float(c[2]),
                                "low": float(c[3]),
                                "close": float(c[4]),
                                "volume": int(c[5]),
                            }
                        )
                    raw_df = pd.DataFrame(df_data)
                    return validator.sanitize_dataframe(raw_df)
                else:
                    logger.warning(f"Upstox historical candle returned HTTP {resp.status_code}.")
        except Exception as e:
            logger.error(f"Error fetching Upstox intraday candles: {e}")

        # Fallback to synthetic
        symbol = instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
        return synthetic_feed.generate_candles(symbol=symbol)


upstox_rest = UpstoxRestClient()

