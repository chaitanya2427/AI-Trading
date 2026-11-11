"""
Backtesting API Endpoints
Provides on-demand historical simulations, tear-sheet reports, and walk-forward validation.
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.adapters.instruments import instrument_master
from backtesting.runner import backtest_runner
from backtesting.walk_forward import WalkForwardValidator
from strategies.registry import strategy_registry

router = APIRouter(prefix="/backtest", tags=["Backtesting & Historical Evaluation"])


class RunBacktestRequest(BaseModel):
    strategy_name: str
    instrument_key: str
    days: int = Field(default=5, ge=1, le=30)
    timeframe_minutes: int = Field(default=5, ge=1, le=60)


class WalkForwardRequest(BaseModel):
    strategy_name: str
    instrument_key: str
    days: int = Field(default=10, ge=3, le=30)
    n_splits: int = Field(default=3, ge=2, le=5)


@router.post("/run")
async def run_backtest(payload: RunBacktestRequest):
    """
    Executes an event-driven backtest for a strategy over multi-day historical candles.
    Reports institutional tear-sheet net of all statutory Indian market costs.
    """
    try:
        results = backtest_runner.run_strategy_backtest(
            strategy_name=payload.strategy_name,
            instrument_key=payload.instrument_key,
            days=payload.days,
            timeframe_minutes=payload.timeframe_minutes,
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.post("/walk-forward")
async def run_walk_forward(payload: WalkForwardRequest):
    """
    Executes chronological walk-forward out-of-sample validation to detect overfitting.
    """
    strategy = strategy_registry.get_strategy(payload.strategy_name)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {payload.strategy_name} not found.")

    instrument = instrument_master.get_by_key(payload.instrument_key)
    if not instrument:
        raise HTTPException(status_code=404, detail=f"Instrument {payload.instrument_key} not found.")

    candles_df = backtest_runner.generate_multi_day_dataset(
        symbol=instrument.symbol,
        days=payload.days,
        timeframe_minutes=5,
    )

    validator = WalkForwardValidator(
        strategy=strategy,
        instrument=instrument,
        n_splits=payload.n_splits,
    )
    return validator.run(candles_df)

