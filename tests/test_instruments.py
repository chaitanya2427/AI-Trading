"""
Unit tests for Instrument Master Service and Offline Fixtures.
"""

from datetime import date
import pytest
from backend.app.adapters.instruments import InstrumentMasterService, instrument_master
from backend.app.models.domain import ExchangeEnum, SegmentEnum


def test_instrument_master_fixture_initialization():
    service = InstrumentMasterService()
    count = service.initialize()
    assert count > 0

    # Verify key lookups
    reliance = service.get_by_key("NSE_EQ|INE002A01018")
    assert reliance is not None
    assert reliance.symbol == "RELIANCE"
    assert reliance.exchange == ExchangeEnum.NSE
    assert reliance.segment == SegmentEnum.EQ
    assert reliance.lot_size == 1
    assert reliance.tick_size == 0.05

    nifty = service.get_by_key("NSE_INDEX|Nifty 50")
    assert nifty is not None
    assert nifty.symbol == "Nifty 50"


def test_instrument_master_symbol_search():
    instrument_master.initialize()
    results = instrument_master.search(query="TCS")
    assert len(results) > 0
    assert any(inst.symbol == "TCS" for inst in results)

    # Search with filter
    fo_results = instrument_master.search(query="NIFTY", segment=SegmentEnum.FO)
    assert len(fo_results) > 0
    assert all(inst.segment == SegmentEnum.FO for inst in fo_results)


def test_instrument_master_option_chain_contracts():
    instrument_master.initialize()
    contracts = instrument_master.get_option_chain_contracts(
        underlying_symbol="NIFTY",
        expiry=date(2026, 11, 26),
    )
    assert len(contracts) > 0
    for c in contracts:
        assert c.segment == SegmentEnum.FO
        assert c.lot_size == 25
        assert c.expiry == date(2026, 11, 26)


def test_instrument_row_parsing():
    service = InstrumentMasterService()
    row = {
        "tradingsymbol": "SBIN",
        "instrument_key": "NSE_EQ|INE062A01020",
        "exchange": "NSE_EQ",
        "instrument_type": "EQ",
        "lot_size": "1",
        "tick_size": "0.05",
        "expiry": "",
    }
    inst = service._parse_upstox_row(row)
    assert inst is not None
    assert inst.symbol == "SBIN"
    assert inst.exchange == ExchangeEnum.NSE
    assert inst.segment == SegmentEnum.EQ


def test_instrument_load_from_csv(tmp_path):
    csv_file = tmp_path / "test_instruments.csv"
    csv_content = (
        "tradingsymbol,instrument_key,exchange,instrument_type,lot_size,tick_size,expiry\n"
        "WIPRO,NSE_EQ|INE075A01022,NSE_EQ,EQ,1,0.05,\n"
        "NIFTY26NOV25000CE,NSE_FO|NIFTY26NOV25000CE,NSE_FO,CE,25,0.05,2026-11-26\n"
    )
    csv_file.write_text(csv_content)

    service = InstrumentMasterService()
    count = service._load_from_csv(csv_file)
    assert count == 2

    wipro = service.get_by_key("NSE_EQ|INE075A01022")
    assert wipro is not None
    assert wipro.symbol == "WIPRO"


def test_instrument_load_from_gzip(tmp_path):
    import gzip
    gz_file = tmp_path / "test_instruments.csv.gz"
    csv_content = (
        "tradingsymbol,instrument_key,exchange,instrument_type,lot_size,tick_size,expiry\n"
        "MARUTI,NSE_EQ|INE585B01010,NSE_EQ,EQ,1,0.05,\n"
    )
    with gzip.open(gz_file, "wt", encoding="utf-8") as f:
        f.write(csv_content)

    service = InstrumentMasterService()
    count = service._load_from_gzip(gz_file)
    assert count == 1
    maruti = service.get_by_key("NSE_EQ|INE585B01010")
    assert maruti is not None
    assert maruti.symbol == "MARUTI"

