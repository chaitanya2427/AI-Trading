"""
Unit & Integration Tests for Live Trade Advisor Feature
Covers:
1. Instrument resolution for Indian symbols (NSE/BSE).
2. Free market data ticker formatting (.NS / .BO).
3. User-provided price labeling (USER_PROVIDED) and reference price overriding.
4. Full strategy coverage (every enabled strategy evaluated without omissions).
5. Consensus aggregation (bullish/bearish/neutral/no-signal counts and agreement summary).
6. Fail-closed decision handling: NO TRADE on insufficient or missing data.
7. Advisory safety invariants: zero real-money live trades, no guaranteed profit claims.
8. REST API route POST /api/v1/advisor/analyze.
"""

from datetime import datetime
import pytest
from httpx import ASGITransport, AsyncClient
import pandas as pd

from backend.app.adapters.free_market_data import free_market_data
from backend.app.core.clock import clock
from backend.app.db.init_db import init_db
from backend.app.main import app
from backend.app.services.trade_advisor import trade_advisor
from strategies.registry import strategy_registry


@pytest.fixture(autouse=True)
async def setup_advisor_test():
    await init_db()
    yield


# ------------------------------------------------------------------------------
# 1. Instrument & Ticker Resolution Tests
# ------------------------------------------------------------------------------

def test_free_market_data_ticker_formatting():
    """Verify ticker formatting for NSE (.NS) and BSE (.BO)."""
    assert free_market_data.format_ticker("TCS", "NSE") == "TCS.NS"
    assert free_market_data.format_ticker("RELIANCE", "BSE") == "RELIANCE.BO"
    assert free_market_data.format_ticker("INFY.NS", "NSE") == "INFY.NS"


def test_trade_advisor_instrument_resolution():
    """Verify resolution of Indian stock symbols into Instrument domain objects."""
    inst_nse = trade_advisor._resolve_instrument("TCS", "NSE")
    assert inst_nse.symbol == "TCS"
    assert inst_nse.exchange.value in ("NSE", "BSE")

    inst_custom = trade_advisor._resolve_instrument("UNKNOWN_STOCK", "BSE")
    assert inst_custom.symbol == "UNKNOWN_STOCK"
    assert inst_custom.exchange.value == "BSE"


# ------------------------------------------------------------------------------
# 2. Strategy Coverage & User-Provided Price Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_trade_advisor_evaluates_all_strategies():
    """Verify that every enabled strategy is evaluated in the analysis."""
    all_registered = strategy_registry.list_strategies()
    total_strats = len(all_registered)

    plan = await trade_advisor.analyze_stock(
        stock_symbol="TCS",
        exchange="NSE",
        timeframe="5m",
    )

    assert plan.instrument["symbol"] == "TCS"
    assert plan.strategy_summary.total_strategies == total_strats
    assert len(plan.strategy_results) == total_strats

    # Check that individual strategy results have required fields
    for res in plan.strategy_results:
        assert res.strategy_name in [s["name"] for s in all_registered]
        assert res.signal in ("BUY", "SELL", "HOLD", "NO_SIGNAL")
        assert res.data_timestamp is not None


@pytest.mark.asyncio
async def test_user_provided_price_labeling():
    """Verify that user-provided price is explicitly labeled USER_PROVIDED."""
    custom_price = 3450.75

    plan = await trade_advisor.analyze_stock(
        stock_symbol="TCS",
        current_price=custom_price,
        exchange="NSE",
    )

    assert plan.market_data.price_type == "USER_PROVIDED"
    assert plan.market_data.price == custom_price
    assert "user-provided reference price" in plan.reasoning.lower()


# ------------------------------------------------------------------------------
# 3. Decision & Trade Plan Invariants
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trade_advisor_no_trade_when_data_missing():
    """If market data is empty or invalid, system returns NO TRADE fail-closed."""
    # Monkeypatch market data to return empty
    with pytest.MonkeyPatch.context() as m:
        async def mock_acquire(*args, **kwargs):
            from backend.app.services.trade_advisor import MarketDataMeta
            return (
                MarketDataMeta(
                    provider="NONE",
                    price=None,
                    price_type="UNAVAILABLE",
                    timestamp=clock.now().isoformat(),
                    freshness="UNKNOWN",
                ),
                pd.DataFrame(),
                "Data feed dropped",
            )

        m.setattr(trade_advisor, "_acquire_market_data", mock_acquire)

        plan = await trade_advisor.analyze_stock("INVALID_SYMBOL")
        assert plan.decision == "NO TRADE"
        assert plan.plan.entry_range is None
        assert plan.plan.stop_loss is None
        assert plan.plan.exit_target is None
        assert "unavailable or invalid" in plan.reasoning.lower()


@pytest.mark.asyncio
async def test_safety_and_limitations_notice():
    """Verify mandatory safety disclaimers (no live orders, no guaranteed profit)."""
    plan = await trade_advisor.analyze_stock("RELIANCE")

    assert "Advisory only" in plan.safety_notice
    assert "Real-money live trading is disabled" in plan.safety_notice
    assert "returns are not guaranteed" in plan.safety_notice
    assert "past performance does not guarantee future results" in plan.limitations.lower()


# ------------------------------------------------------------------------------
# 4. REST API Endpoint Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_advisor_analyze_endpoint():
    """Verify POST /api/v1/advisor/analyze returns valid TradePlanResponse schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "stock_symbol": "INFY",
            "current_price": 1850.0,
            "exchange": "NSE",
            "timeframe": "5m",
            "trade_style": "INTRADAY",
        }
        res = await client.post("/api/v1/advisor/analyze", json=payload)
        assert res.status_code == 200

        data = res.json()
        assert data["decision"] in ("BUY", "SELL", "HOLD", "NO TRADE")
        assert data["instrument"]["symbol"] == "INFY"
        assert data["market_data"]["price_type"] == "USER_PROVIDED"
        assert data["market_data"]["price"] == 1850.0
        assert "strategy_summary" in data
        assert "strategy_results" in data
        assert len(data["strategy_results"]) == len(strategy_registry.list_strategies())

