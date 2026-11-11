"""
FastAPI Backend Application Entry Point
Modular AI-Powered Indian Financial Markets Trading Platform (Research & Paper Trading).
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.instruments import instrument_master
from backend.app.api.v1.endpoints import router as api_v1_router
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.db.init_db import init_db
from backend.app.db.session import AsyncSessionLocal, get_db_session
from risk.engine import risk_engine

logger = setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Initializing Indian Multi-Agent Trading System...")
    logger.info(f"Execution Mode: {settings.EXECUTION_MODE} | Live Trading: {settings.LIVE_TRADING_ENABLED}")
    logger.info(f"Capital: ₹{settings.STARTING_CAPITAL_INR:.2f} | Hard Loss Cap: ₹{settings.DAILY_LOSS_LIMIT_INR:.2f}")

    # Initialize SQLite tables
    await init_db()

    # Initialize Instrument Master
    instrument_master.initialize()

    # Initialize Risk Engine session
    async with AsyncSessionLocal() as session:
        await risk_engine.initialize_session(session)

    yield

    # Shutdown sequence
    logger.info("Trading system shutting down cleanly.")


app = FastAPI(
    title="Indian Multi-Agent Trading Platform",
    description="Deterministic research, backtesting, paper trading and risk management for Indian markets.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Routes
app.include_router(api_v1_router)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Primary health check endpoint returning system, session, and risk state."""
    db_healthy = False
    try:
        res = await db.execute(text("SELECT 1;"))
        db_healthy = bool(res.scalar() == 1)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    now_ist = clock.now()
    phase = clock.get_session_phase(now_ist)

    return {
        "status": "HEALTHY" if db_healthy else "DEGRADED",
        "system": "Indian Multi-Agent Trading Platform",
        "version": "1.0.0",
        "database_connected": db_healthy,
        "database_mode": "WAL",
        "execution_mode": settings.EXECUTION_MODE,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "time_ist": now_ist.isoformat(),
        "session_phase": phase.value,
        "is_trading_day": clock.is_trading_day(now_ist),
        "is_market_open": clock.is_market_open(now_ist),
        "risk_status": risk_engine.state.status.value if risk_engine.state else "INITIALIZING",
        "kill_switch_active": risk_engine.kill_switch_active,
        "daily_loss_limit_inr": settings.DAILY_LOSS_LIMIT_INR,
    }


# Mount compiled dashboard UI if available
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )

