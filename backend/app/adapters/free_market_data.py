"""
Free Market Data Provider for Indian Financial Markets
Fetches free authentic market data (quotes and intraday OHLCV candles)
for NSE and BSE equities without requiring API keys or subscriptions.
Explicitly labels data as DELAYED or LIVE with timestamp and provenance.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import httpx
import pandas as pd

from backend.app.core.clock import clock
from backend.app.core.logging import get_logger

logger = get_logger("adapters.free_market_data")
IST = ZoneInfo("Asia/Kolkata")


class FreeMarketDataProvider:
    """
    Public market data adapter for Indian stock exchanges.
    Provides free real quotes and candle histories for NSE and BSE.
    Labels data accurately (e.g. YAHOO_FINANCE_FREE, DELAYED).
    """

    PROVIDER_NAME = "YAHOO_FINANCE_FREE"

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def format_ticker(self, symbol: str, exchange: str = "NSE") -> str:
        """Formats Indian stock symbol into exchange-qualified ticker."""
        clean_sym = symbol.strip().upper().replace(" ", "")
        # Strip existing suffix if present
        clean_sym = clean_sym.replace(".NS", "").replace(".BO", "")
        if exchange.upper() == "BSE":
            return f"{clean_sym}.BO"
        return f"{clean_sym}.NS"

    async def get_quote_and_candles(
        self,
        symbol: str,
        exchange: str = "NSE",
        timeframe: str = "5m",
    ) -> Tuple[Optional[Dict[str, Any]], pd.DataFrame]:
        """
        Fetches latest quote metadata and intraday OHLCV candle DataFrame.
        Returns (quote_dict, candles_df).
        """
        ticker = self.format_ticker(symbol, exchange)
        interval = "5m"
        range_param = "1d"

        if timeframe in ("15m", "15minute"):
            interval = "15m"
            range_param = "5d"
        elif timeframe in ("60m", "1h", "60minute"):
            interval = "60m"
            range_param = "1mo"
        elif timeframe in ("1d", "day"):
            interval = "1d"
            range_param = "3mo"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_param}"

        start_monotonic = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url, headers=self.headers)
                latency_ms = (time.monotonic() - start_monotonic) * 1000.0

                if resp.status_code != 200:
                    logger.warning(
                        "Free market data query returned HTTP %s for %s: %s",
                        resp.status_code,
                        ticker,
                        resp.text[:100],
                    )
                    return None, pd.DataFrame()

                data = resp.json()
                chart = data.get("chart", {})
                results = chart.get("result", [])
                if not results:
                    logger.warning("No chart results returned for %s", ticker)
                    return None, pd.DataFrame()

                res = results[0]
                meta = res.get("meta", {})
                timestamps = res.get("timestamp", [])
                indicators = res.get("indicators", {}).get("quote", [{}])[0]

                if not timestamps or not indicators.get("close"):
                    return None, pd.DataFrame()

                # Build candle DataFrame
                records = []
                opens = indicators.get("open", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                closes = indicators.get("close", [])
                volumes = indicators.get("volume", [])

                for i in range(len(timestamps)):
                    o = opens[i]
                    h = highs[i]
                    l = lows[i]
                    c = closes[i]
                    v = volumes[i] if i < len(volumes) else 0

                    # Filter out bars with None values
                    if o is not None and h is not None and l is not None and c is not None:
                        dt = datetime.fromtimestamp(timestamps[i], tz=timezone.utc).astimezone(IST)
                        records.append({
                            "timestamp": dt,
                            "open": round(float(o), 2),
                            "high": round(float(h), 2),
                            "low": round(float(l), 2),
                            "close": round(float(c), 2),
                            "volume": float(v or 0.0),
                        })

                if not records:
                    return None, pd.DataFrame()

                df = pd.DataFrame(records)

                # Build quote dictionary
                regular_price = meta.get("regularMarketPrice") or df.iloc[-1]["close"]
                prev_close = meta.get("chartPreviousClose") or meta.get("previousClose") or regular_price
                market_time_unix = meta.get("regularMarketTime") or timestamps[-1]
                quote_time = datetime.fromtimestamp(market_time_unix, tz=timezone.utc).astimezone(IST)

                quote = {
                    "symbol": symbol.strip().upper(),
                    "ticker": ticker,
                    "exchange": exchange.upper(),
                    "ltp": round(float(regular_price), 2),
                    "previous_close": round(float(prev_close), 2),
                    "provider": self.PROVIDER_NAME,
                    "price_type": "DELAYED",  # Explicitly label public free feed as DELAYED
                    "timestamp": quote_time.isoformat(),
                    "latency_ms": round(latency_ms, 1),
                    "currency": meta.get("currency", "INR"),
                }

                return quote, df

        except Exception as e:
            logger.error("Error retrieving free market data for %s: %s", ticker, e)
            return None, pd.DataFrame()


free_market_data = FreeMarketDataProvider()

