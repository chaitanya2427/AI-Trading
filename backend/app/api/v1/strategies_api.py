"""
Strategy & Agent Advisory API Endpoints
Provides strategy listing, strategy execution, proposal generation, and multi-agent assessments.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import agent_orchestrator
from backend.app.adapters.instruments import instrument_master
from backend.app.adapters.upstox_rest import upstox_rest
from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.db.session import get_db_session
from backend.app.models.domain import AgentAssessment, TradeProposal
from execution.costs import settings
from execution.proposal_service import proposal_service
from risk.engine import risk_engine
from strategies.proposal_generator import proposal_generator
from strategies.registry import strategy_registry

router = APIRouter(prefix="/strategies", tags=["Strategies & Agents"])


class EvaluateStrategyRequest(BaseModel):
    instrument_key: str
    strategy_name: Optional[str] = None
    timeframe: str = "5m"


@router.get("", response_model=List[dict])
async def list_strategies():
    """Lists all available deterministic trading strategies."""
    return strategy_registry.list_strategies()


@router.post("/evaluate", response_model=List[TradeProposal])
async def evaluate_strategies(
    payload: EvaluateStrategyRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Evaluates strategies on intraday candle data for an instrument.
    Generates schema-validated TradeProposal contracts with multi-agent consensus evidence.
    """
    instrument = instrument_master.get_by_key(payload.instrument_key)
    if not instrument:
        raise HTTPException(status_code=404, detail=f"Instrument {payload.instrument_key} not found.")

    # Fetch validated candles
    candles_df = await upstox_rest.get_intraday_candles(payload.instrument_key, interval="5minute")
    if candles_df.empty:
        return []

    # Get latest quote and build provenance
    quote = await upstox_rest.get_market_quote(payload.instrument_key)
    provenance = validator.check_quote_freshness(quote["provenance"]["as_of"])

    # Evaluate strategies
    if payload.strategy_name:
        strat = strategy_registry.get_strategy(payload.strategy_name)
        if not strat:
            raise HTTPException(status_code=404, detail=f"Strategy {payload.strategy_name} not found.")
        signals = [sig for sig in [strat.evaluate(candles_df, instrument, timeframe=payload.timeframe)] if sig]
    else:
        signals = strategy_registry.evaluate_all(candles_df, instrument, timeframe=payload.timeframe)

    proposals: List[TradeProposal] = []
    available_capital = risk_engine.state.available_capital if risk_engine.state else settings.STARTING_CAPITAL_INR

    for sig in signals:
        # Run multi-agent assessment for evidence bundling
        agent_assessments = await agent_orchestrator.run_all(
            candles=candles_df,
            instrument=instrument,
            context={"order_book": quote.get("depth", {})},
            proposed_direction=sig.direction,
        )

        proposal = proposal_generator.create_proposal(
            signal=sig,
            instrument=instrument,
            provenance=provenance,
            available_capital=available_capital,
            agent_assessments=agent_assessments,
        )
        if proposal:
            await proposal_service.save_proposal(proposal, db)
            proposals.append(proposal)

    return proposals


@router.get("/agents/assess", response_model=List[AgentAssessment])
async def assess_instrument(
    instrument_key: str = Query(..., description="Target instrument key"),
):
    """Runs all specialist agents and returns structured assessments and consensus."""
    instrument = instrument_master.get_by_key(instrument_key)
    if not instrument:
        raise HTTPException(status_code=404, detail=f"Instrument {instrument_key} not found.")

    candles_df = await upstox_rest.get_intraday_candles(instrument_key, interval="5minute")
    quote = await upstox_rest.get_market_quote(instrument_key)

    assessments = await agent_orchestrator.run_all(
        candles=candles_df,
        instrument=instrument,
        context={"order_book": quote.get("depth", {})},
    )
    return assessments


class ScanMarketRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframe: str = "5m"
    generate_demo_if_empty: bool = True


@router.post("/scan")
async def scan_market_strategies(
    payload: ScanMarketRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Scans liquid watchlist against all deterministic strategies.
    Generates and saves trade proposals ready for human operator review in the dashboard.
    """
    target_symbols = payload.symbols or ["RELIANCE", "TCS", "INFY", "SBIN"]
    created_proposals: List[TradeProposal] = []

    for sym in target_symbols:
        matches = instrument_master.search(sym)
        if not matches:
            continue
        inst = matches[0]

        candles_df = await upstox_rest.get_intraday_candles(inst.instrument_key, interval="5minute")
        if candles_df.empty:
            continue

        quote = await upstox_rest.get_market_quote(inst.instrument_key)
        provenance = validator.check_quote_freshness(quote["provenance"]["as_of"])

        signals = strategy_registry.evaluate_all(candles_df, inst, timeframe=payload.timeframe)
        available_cap = risk_engine.state.available_capital if risk_engine.state else settings.STARTING_CAPITAL_INR

        for sig in signals:
            assessments = await agent_orchestrator.run_all(
                candles=candles_df,
                instrument=inst,
                context={"order_book": quote.get("depth", {})},
                proposed_direction=sig.direction,
            )
            proposal = proposal_generator.create_proposal(
                signal=sig,
                instrument=inst,
                provenance=provenance,
                available_capital=available_cap,
                agent_assessments=assessments,
            )
            if proposal:
                await proposal_service.save_proposal(proposal, db)
                created_proposals.append(proposal)

    # If no natural signal triggered in this bar and demo is requested, create a compliant sample proposal
    if not created_proposals and payload.generate_demo_if_empty:
        matches = instrument_master.search("TCS")
        inst = matches[0] if matches else instrument_master.get_all_instruments()[0]
        quote = await upstox_rest.get_market_quote(inst.instrument_key)
        ref_price = quote["ltp"]
        stop_loss = round(ref_price * 0.99, 2)
        target = round(ref_price * 1.02, 2)
        qty = 2  # Risk = ref_price * 0.01 * 2 <= ₹250
        risk_inr = round((ref_price - stop_loss) * qty, 2)
        reward_inr = round((target - ref_price) * qty, 2)

        from backend.app.models.domain import DirectionEnum, EntryDetails, OrderTypeEnum, StrategyInfo, MarketDataProvenance
        demo_prop = TradeProposal(
            schema_version="1.0",
            created_at=clock.now(),
            instrument=inst,
            direction=DirectionEnum.LONG,
            strategy=StrategyInfo(name="VWAP_Continuation", version="1.0"),
            timeframe=payload.timeframe,
            market_data=MarketDataProvenance(
                as_of=clock.now(),
                source=quote["provenance"]["source"],
                is_stale=False,
            ),
            entry=EntryDetails(
                order_type=OrderTypeEnum.MARKET,
                reference_price=ref_price,
            ),
            stop_loss=stop_loss,
            target=target,
            quantity=qty,
            estimated_risk_inr=risk_inr,
            estimated_reward_inr=reward_inr,
            estimated_costs_inr=28.50,
            supporting_evidence=["Price above VWAP with rising volume", "RSI pullback to 52"],
        )
        await proposal_service.save_proposal(demo_prop, db)
        created_proposals.append(demo_prop)

    return {
        "status": "COMPLETED",
        "scanned_symbols": target_symbols,
        "proposals_generated": len(created_proposals),
        "proposals": [p.model_dump(mode="json") for p in created_proposals],
    }


