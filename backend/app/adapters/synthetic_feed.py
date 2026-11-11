"""
Synthetic Market Data Generator
Provides stochastic price simulation (Merton Jump Diffusion), realistic intraday volume curves,
and Level 2 order book depth for deterministic offline research and weekend backtesting.
"""

import math
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.models.domain import MarketDataProvenance

IST = ZoneInfo("Asia/Kolkata")


class SyntheticMarketFeed:
    """
    Generates synthetic but mathematically consistent OHLCV candles, ticks, and order books.
    All output is explicitly tagged with source='SYNTHETIC_FIXTURE'.
    """

    def __init__(self, seed: Optional[int] = 42):
        self.rng = np.random.default_rng(seed)

    def generate_candles(
        self,
        symbol: str = "RELIANCE",
        trading_date: Optional[date] = None,
        base_price: float = 2500.0,
        annual_volatility: float = 0.22,
        timeframe_minutes: int = 5,
        trend: float = 0.0005,  # Slight drift
    ) -> pd.DataFrame:
        """
        Generates 1 trading session (09:15 to 15:30 IST) of intraday candles
        using Merton Jump Diffusion and realistic U-shaped volume profiles.
        """
        target_date = trading_date or clock.today()
        start_dt = datetime.combine(target_date, time(9, 15), tzinfo=IST)
        end_dt = datetime.combine(target_date, time(15, 30), tzinfo=IST)

        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        num_candles = total_minutes // timeframe_minutes

        dt = timeframe_minutes / (375.0 * 252.0)  # Fraction of trading year
        sigma = annual_volatility
        jump_lambda = 0.05  # Jump intensity
        jump_mean = 0.0
        jump_std = 0.005

        prices = [base_price]
        timestamps = [start_dt]
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        current_price = base_price

        for i in range(num_candles):
            candle_start = start_dt + timedelta(minutes=i * timeframe_minutes)
            timestamps.append(candle_start)

            # Sub-steps per candle to generate realistic intra-candle High/Low
            sub_steps = 10
            sub_dt = dt / sub_steps
            sub_prices = [current_price]

            for _ in range(sub_steps):
                z = self.rng.standard_normal()
                # Jump component
                jump = 0.0
                if self.rng.random() < jump_lambda:
                    jump = self.rng.normal(jump_mean, jump_std)

                ret = (trend - 0.5 * sigma**2) * sub_dt + sigma * math.sqrt(sub_dt) * z + jump
                next_price = round(sub_prices[-1] * math.exp(ret), 2)
                sub_prices.append(next_price)

            o = sub_prices[0]
            c = sub_prices[-1]
            h = max(sub_prices)
            l = min(sub_prices)

            # Invariant safety: ensure Low <= min(O, C) and High >= max(O, C)
            h = max(h, o, c)
            l = min(l, o, c)

            # U-shaped volume curve (Heavy at open & close, quiet at midday)
            time_fraction = i / max(1, num_candles)
            volume_multiplier = 2.5 * ((time_fraction - 0.5) ** 2) + 0.5
            base_vol = self.rng.integers(1000, 5000)
            vol = int(base_vol * volume_multiplier * 5)

            opens.append(o)
            highs.append(h)
            lows.append(l)
            closes.append(c)
            volumes.append(vol)

            current_price = c

        df = pd.DataFrame(
            {
                "timestamp": timestamps[1:],
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )

        return validator.sanitize_dataframe(df)

    def generate_order_book(
        self,
        mid_price: float,
        tick_size: float = 0.05,
        depth: int = 5,
    ) -> Dict:
        """
        Generates realistic Level 2 bid/ask depth for a given price.
        """
        half_spread = tick_size * self.rng.integers(1, 3)
        best_bid = round((mid_price - half_spread) / tick_size) * tick_size
        best_ask = round((mid_price + half_spread) / tick_size) * tick_size

        bids = []
        asks = []

        for i in range(depth):
            bid_p = round(best_bid - i * tick_size, 2)
            ask_p = round(best_ask + i * tick_size, 2)
            bid_q = int(self.rng.integers(100, 1500) * (depth - i * 0.15))
            ask_q = int(self.rng.integers(100, 1500) * (depth - i * 0.15))

            bids.append({"price": bid_p, "quantity": bid_q, "orders": int(self.rng.integers(1, 10))})
            asks.append({"price": ask_p, "quantity": ask_q, "orders": int(self.rng.integers(1, 10))})

        return {
            "source": "SYNTHETIC_FIXTURE",
            "timestamp": clock.now().isoformat(),
            "bids": bids,
            "asks": asks,
            "spread": round(best_ask - best_bid, 2),
            "mid_price": round((best_bid + best_ask) / 2.0, 2),
        }

    def generate_quote(self, symbol: str, current_price: float) -> Dict:
        """Generates a single live quote tagged with SYNTHETIC_FIXTURE provenance."""
        now = clock.now()
        book = self.generate_order_book(current_price)
        return {
            "symbol": symbol,
            "ltp": current_price,
            "ltt": now.isoformat(),
            "ltq": int(self.rng.integers(1, 50)),
            "volume": int(self.rng.integers(50000, 500000)),
            "depth": book,
            "provenance": MarketDataProvenance(
                as_of=now,
                source="SYNTHETIC_FIXTURE",
                is_stale=False,
                latency_ms=0.5,
            ).model_dump(),
        }


synthetic_feed = SyntheticMarketFeed()

