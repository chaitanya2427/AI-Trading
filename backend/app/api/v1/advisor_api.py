"""
Live Trade Advisor API Endpoint
Accepts user stock inputs (symbol, optional price, exchange, timeframe),
evaluates all enabled trading strategies, and returns structured trade plans.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.trade_advisor import TradePlanResponse, trade_advisor

router = APIRouter(prefix="/advisor", tags=["Live Trade Advisor"])


class StockAnalysisRequest(BaseModel):
    stock_symbol: str = Field(..., min_length=1, description="Indian stock symbol or name, e.g. RELIANCE or TCS")
    current_price: Optional[float] = Field(default=None, gt=0.0, description="Optional user-entered current price")
    exchange: Optional[str] = Field(default="NSE", description="NSE or BSE")
    timeframe: Optional[str] = Field(default="5m", description="Strategy timeframe (e.g. 5m, 15m, 60m)")
    trade_style: Optional[str] = Field(default="INTRADAY", description="INTRADAY or DELIVERY")


@router.post("/analyze", response_model=TradePlanResponse)
async def analyze_stock_trade_plan(payload: StockAnalysisRequest):
    """
    Evaluates every registered trading strategy against current market data
    for the specified Indian stock symbol and returns an evidence-backed trade plan.
    """
    try:
        plan = await trade_advisor.analyze_stock(
            stock_symbol=payload.stock_symbol,
            current_price=payload.current_price,
            exchange=payload.exchange,
            timeframe=payload.timeframe or "5m",
            trade_style=payload.trade_style or "INTRADAY",
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating trade advisor plan: {str(e)}")

