"""
Instrument Master Ingestion, Caching, and Lookup
Handles Upstox daily instrument files and provides fast in-memory indexing with verified offline fixtures.
"""

import csv
import gzip
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
import httpx

from backend.app.core.clock import clock
from backend.app.models.domain import ExchangeEnum, Instrument, SegmentEnum

logger = logging.getLogger(__name__)

INSTRUMENTS_DIR = Path("data/instruments")
UPSTOX_INSTRUMENT_CDN_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"

# Fallback verified fixture of representative Indian market instruments for offline development
VERIFIED_FIXTURE_INSTRUMENTS: List[Dict] = [
    # Benchmark Indices
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "Nifty 50",
        "instrument_key": "NSE_INDEX|Nifty 50",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "Nifty Bank",
        "instrument_key": "NSE_INDEX|Nifty Bank",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    # Large-Cap Equities
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "RELIANCE",
        "instrument_key": "NSE_EQ|INE002A01018",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "TCS",
        "instrument_key": "NSE_EQ|INE467B01029",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "INFY",
        "instrument_key": "NSE_EQ|INE009A01021",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "HDFCBANK",
        "instrument_key": "NSE_EQ|INE040A01034",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "ICICIBANK",
        "instrument_key": "NSE_EQ|INE090A01021",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "SBIN",
        "instrument_key": "NSE_EQ|INE062A01020",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "TATAMOTORS",
        "instrument_key": "NSE_EQ|INE155A01022",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "EQ",
        "symbol": "AXISBANK",
        "instrument_key": "NSE_EQ|INE238A01034",
        "lot_size": 1,
        "tick_size": 0.05,
    },
    # Nifty Derivatives (Options Representative Sample)
    {
        "exchange": "NSE",
        "segment": "FO",
        "symbol": "NIFTY26NOV24000CE",
        "instrument_key": "NSE_FO|NIFTY26NOV24000CE",
        "expiry": date(2026, 11, 26),
        "lot_size": 25,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "FO",
        "symbol": "NIFTY26NOV24000PE",
        "instrument_key": "NSE_FO|NIFTY26NOV24000PE",
        "expiry": date(2026, 11, 26),
        "lot_size": 25,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "FO",
        "symbol": "NIFTY26NOV24500CE",
        "instrument_key": "NSE_FO|NIFTY26NOV24500CE",
        "expiry": date(2026, 11, 26),
        "lot_size": 25,
        "tick_size": 0.05,
    },
    {
        "exchange": "NSE",
        "segment": "FO",
        "symbol": "NIFTY26NOV24500PE",
        "instrument_key": "NSE_FO|NIFTY26NOV24500PE",
        "expiry": date(2026, 11, 26),
        "lot_size": 25,
        "tick_size": 0.05,
    },
]


class InstrumentMasterService:
    """Manages instrument master registry, search, and CDN downloads."""

    def __init__(self):
        self._by_key: Dict[str, Instrument] = {}
        self._by_symbol: Dict[str, List[Instrument]] = {}
        self._is_initialized = False

    def initialize(self) -> int:
        """Loads cached instruments or initializes from verified offline fixtures."""
        INSTRUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self._by_key.clear()
        self._by_symbol.clear()

        # Load verified fixtures first
        for item in VERIFIED_FIXTURE_INSTRUMENTS:
            inst = Instrument(**item)
            self._add_instrument(inst)

        # Check for local cached file from today
        today_str = clock.today().isoformat()
        cached_file = INSTRUMENTS_DIR / f"instruments_{today_str}.csv"
        cached_gz = INSTRUMENTS_DIR / f"instruments_{today_str}.csv.gz"

        if cached_file.exists():
            self._load_from_csv(cached_file)
        elif cached_gz.exists():
            self._load_from_gzip(cached_gz)

        self._is_initialized = True
        logger.info(f"Instrument master initialized with {len(self._by_key)} instruments.")
        return len(self._by_key)

    async def sync_from_cdn(self) -> int:
        """Downloads the latest instrument master from Upstox CDN if network allows."""
        today_str = clock.today().isoformat()
        dest_gz = INSTRUMENTS_DIR / f"instruments_{today_str}.csv.gz"

        try:
            logger.info(f"Downloading instrument master from {UPSTOX_INSTRUMENT_CDN_URL}...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(UPSTOX_INSTRUMENT_CDN_URL)
                if resp.status_code == 200:
                    with open(dest_gz, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"Saved {len(resp.content)} bytes to {dest_gz}")
                    count = self._load_from_gzip(dest_gz)
                    return count
                else:
                    logger.warning(f"Upstox CDN returned HTTP {resp.status_code}. Using cached/fixture data.")
        except Exception as e:
            logger.warning(f"Could not reach Upstox CDN ({e}). Using local cached/fixture data.")

        return len(self._by_key)

    def _add_instrument(self, inst: Instrument) -> None:
        self._by_key[inst.instrument_key] = inst
        sym_key = inst.symbol.upper()
        if sym_key not in self._by_symbol:
            self._by_symbol[sym_key] = []
        self._by_symbol[sym_key].append(inst)

    def _load_from_gzip(self, file_path: Path) -> int:
        count = 0
        try:
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    inst = self._parse_upstox_row(row)
                    if inst:
                        self._add_instrument(inst)
                        count += 1
            self._is_initialized = True
            logger.info(f"Loaded {count} instruments from {file_path}")
        except Exception as e:
            logger.error(f"Error parsing gzip instrument master {file_path}: {e}")
        return count

    def _load_from_csv(self, file_path: Path) -> int:
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    inst = self._parse_upstox_row(row)
                    if inst:
                        self._add_instrument(inst)
                        count += 1
            self._is_initialized = True
            logger.info(f"Loaded {count} instruments from {file_path}")
        except Exception as e:
            logger.error(f"Error parsing CSV instrument master {file_path}: {e}")
        return count

    def _parse_upstox_row(self, row: Dict[str, str]) -> Optional[Instrument]:
        try:
            raw_exchange = row.get("exchange", "").upper()
            if "NSE" in raw_exchange:
                exchange = ExchangeEnum.NSE
            elif "BSE" in raw_exchange:
                exchange = ExchangeEnum.BSE
            elif "MCX" in raw_exchange:
                exchange = ExchangeEnum.MCX
            else:
                return None

            instrument_type = row.get("instrument_type", "").upper()
            if instrument_type in ("CE", "PE", "FUT"):
                segment = SegmentEnum.FO
            elif "COM" in raw_exchange:
                segment = SegmentEnum.COM
            else:
                segment = SegmentEnum.EQ

            expiry = None
            raw_expiry = row.get("expiry")
            if raw_expiry and raw_expiry != "":
                try:
                    expiry = datetime.strptime(raw_expiry, "%Y-%m-%d").date()
                except ValueError:
                    pass

            lot_size = int(row.get("lot_size", 1) or 1)
            tick_size = float(row.get("tick_size", 0.05) or 0.05)

            return Instrument(
                exchange=exchange,
                segment=segment,
                symbol=row.get("tradingsymbol", ""),
                instrument_key=row.get("instrument_key", ""),
                expiry=expiry,
                lot_size=max(1, lot_size),
                tick_size=max(0.01, tick_size),
                is_tradable=True,
            )
        except Exception:
            return None

    def get_by_key(self, instrument_key: str) -> Optional[Instrument]:
        """Lookup instrument by instrument_key (e.g. 'NSE_EQ|INE002A01018')."""
        if not self._is_initialized:
            self.initialize()
        return self._by_key.get(instrument_key)

    def get_by_symbol(self, symbol: str) -> List[Instrument]:
        """Lookup instruments by trading symbol."""
        if not self._is_initialized:
            self.initialize()
        return self._by_symbol.get(symbol.upper(), [])

    def search(
        self,
        query: str,
        exchange: Optional[ExchangeEnum] = None,
        segment: Optional[SegmentEnum] = None,
        limit: int = 20,
    ) -> List[Instrument]:
        """Search instruments matching query substring."""
        if not self._is_initialized:
            self.initialize()
        query_upper = query.upper()
        results: List[Instrument] = []

        for inst in self._by_key.values():
            if exchange and inst.exchange != exchange:
                continue
            if segment and inst.segment != segment:
                continue
            if query_upper in inst.symbol.upper() or query_upper in inst.instrument_key.upper():
                results.append(inst)
                if len(results) >= limit:
                    break

        return results

    def get_option_chain_contracts(
        self,
        underlying_symbol: str,
        expiry: Optional[date] = None,
    ) -> List[Instrument]:
        """Returns option contracts matching underlying and optional expiry."""
        if not self._is_initialized:
            self.initialize()
        matches: List[Instrument] = []
        underlying_upper = underlying_symbol.upper()

        for inst in self._by_key.values():
            if inst.segment == SegmentEnum.FO and underlying_upper in inst.symbol.upper():
                if expiry is None or inst.expiry == expiry:
                    matches.append(inst)

        return matches


instrument_master = InstrumentMasterService()
