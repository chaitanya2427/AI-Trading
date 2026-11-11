"""
Integration tests for Market Data FastAPI endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.init_db import init_db
from backend.app.adapters.instruments import instrument_master


@pytest.fixture(autouse=True)
async def setup_environment():
    await init_db()
    instrument_master.initialize()


@pytest.mark.asyncio
async def test_api_instrument_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/market/instruments/search?query=RELIANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["symbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_api_quote_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/market/quote/NSE_EQ|INE002A01018")
        assert resp.status_code == 200
        data = resp.json()
        assert "ltp" in data
        assert "provenance" in data
        assert data["provenance"]["is_stale"] is False


@pytest.mark.asyncio
async def test_api_candles_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/market/candles/NSE_EQ|INE002A01018?interval=5minute")
        assert resp.status_code == 200
        data = resp.json()
        assert data["interval"] == "5minute"
        assert len(data["candles"]) > 0
        candle = data["candles"][0]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle


@pytest.mark.asyncio
async def test_api_option_chain_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/market/option-chain?underlying=NIFTY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "NIFTY"
        assert data["contracts_count"] > 0

