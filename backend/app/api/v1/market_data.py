"""
Market Data API Routes & Real-Time WebSocket Streaming
Provides search, live quotes, validated candle series, option chain contracts, and WebSocket broadcast.
"""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.app.adapters.instruments import instrument_master
from backend.app.adapters.upstox_rest import upstox_rest
from backend.app.adapters.upstox_ws import upstox_ws
from backend.app.models.domain import ExchangeEnum, Instrument, SegmentEnum

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/instruments/search", response_model=List[Instrument])
async def search_instruments(
    query: str = Query(..., min_length=1, description="Symbol or instrument key query"),
    exchange: Optional[ExchangeEnum] = Query(default=None),
    segment: Optional[SegmentEnum] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Searches instrument master for symbols, indices, or derivative contracts."""
    return instrument_master.search(query=query, exchange=exchange, segment=segment, limit=limit)


@router.get("/quote/{instrument_key:path}")
async def get_quote(instrument_key: str):
    """Returns the latest quote, depth, and provenance for an instrument."""
    quote = await upstox_rest.get_market_quote(instrument_key)
    return quote


@router.get("/candles/{instrument_key:path}")
async def get_candles(
    instrument_key: str,
    interval: str = Query(default="5minute", pattern="^(1minute|5minute|15minute|30minute|day)$"),
):
    """Returns validated intraday OHLCV candles."""
    df = await upstox_rest.get_intraday_candles(instrument_key, interval=interval)
    # Convert dataframe to JSON records
    records = df.to_dict(orient="records")
    for r in records:
        if hasattr(r["timestamp"], "isoformat"):
            r["timestamp"] = r["timestamp"].isoformat()
    return {
        "instrument_key": instrument_key,
        "interval": interval,
        "count": len(records),
        "candles": records,
    }


@router.get("/option-chain")
async def get_option_chain(
    underlying: str = Query(default="NIFTY", description="Underlying symbol, e.g. NIFTY, BANKNIFTY"),
):
    """Returns option chain contracts for an underlying."""
    contracts = instrument_master.get_option_chain_contracts(underlying_symbol=underlying)
    return {
        "underlying": underlying,
        "contracts_count": len(contracts),
        "contracts": contracts,
    }


@router.websocket("/stream")
async def market_data_websocket(websocket: WebSocket):
    """
    Local WebSocket feed broadcasting real-time ticks to the web dashboard.
    """
    await websocket.accept()
    queue = asyncio.Queue(maxsize=100)

    def on_tick(tick: dict):
        try:
            queue.put_nowait(tick)
        except asyncio.QueueFull:
            pass  # Drop oldest tick on slow consumer

    upstox_ws.add_callback(on_tick)
    try:
        while True:
            tick = await queue.get()
            await websocket.send_json(tick)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        if on_tick in upstox_ws.callbacks:
            upstox_ws.callbacks.remove(on_tick)
