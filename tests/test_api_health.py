"""
Unit tests for FastAPI Health and Status endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.init_db import init_db


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Ensure database tables are created before running API tests."""
    await init_db()


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "HEALTHY"
        assert data["database_connected"] is True
        assert data["execution_mode"] == "PAPER"
        assert data["live_trading_enabled"] is False
        assert data["daily_loss_limit_inr"] == 250.0


@pytest.mark.asyncio
async def test_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "session_phase" in data
        assert "capital_summary" in data
        assert data["capital_summary"]["daily_loss_limit_inr"] == 250.0


@pytest.mark.asyncio
async def test_kill_switch_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger kill switch
        resp1 = await client.post(
            "/api/v1/risk/kill-switch",
            json={"reason": "Testing operator emergency button"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "SUCCESS"

        # Check status reflects active kill switch
        status_resp = await client.get("/api/v1/status")
        assert status_resp.json()["kill_switch_active"] is True

        # Reset kill switch
        resp2 = await client.post(
            "/api/v1/risk/kill-switch/reset",
            json={"reason": "Testing operator reset button with valid rationale"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "SUCCESS"
