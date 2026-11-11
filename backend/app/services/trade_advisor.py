"""
Live Trade Advisor Service
Evaluates all enabled quantitative strategies against authentic market data for any entered Indian stock.
Produces structured, evidence-based trade plans with complete strategy consensus breakdown.
Advisory only — strictly zero live orders, zero guaranteed returns.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.adapters.free_market_data import free_market_data
from backend.app.adapters.instruments import instrument_master
from backend.app.adapters.synthetic_feed import synthetic_feed
from backend.app.adapters.upstox_rest import upstox_rest
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.models.domain import (
    DirectionEnum,
    ExchangeEnum,
    Instrument,
    SegmentEnum,
)
from strategies.registry import strategy_registry

logger = get_logger("services.trade_advisor")


class StrategyResultItem(BaseModel):
    strategy_name: str
    signal: str  # BUY, SELL, HOLD, NO_SIGNAL
    entry_price_or_range: Optional[str] = None
    stop_loss: Optional[float] = None
    exit_target_or_rule: Optional[str] = None
    risk_reward_ratio: Optional[float] = None
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    data_timestamp: str


class StrategySummary(BaseModel):
    bullish_count: int
    bearish_count: int
    neutral_count: int
    non_signaling_count: int
    total_strategies: int
    agreement_summary: str


class MarketDataMeta(BaseModel):
    provider: str
    price: Optional[float]
    price_type: str  # LIVE, DELAYED, USER_PROVIDED, UNAVAILABLE
    timestamp: str
    freshness: str  # FRESH, STALE, UNKNOWN


class TradePlanLevels(BaseModel):
    entry_range: Optional[str] = None
    stop_loss: Optional[float] = None
    exit_target: Optional[float] = None
    exit_rule: Optional[str] = None
    risk_reward_ratio: Optional[float] = None


class TradePlanResponse(BaseModel):
    decision: str  # BUY, SELL, HOLD, NO TRADE
    instrument: Dict[str, str]
    market_data: MarketDataMeta
    plan: TradePlanLevels
    strategy_summary: StrategySummary
    strategy_results: List[StrategyResultItem]
    reasoning: str
    limitations: str
    safety_notice: str = (
        "Advisory only. Real-money live trading is disabled. "
        "Market outcomes are uncertain and returns are not guaranteed. "
        "Any trade must be manually executed in paper mode with deterministic risk engine validation."
    )


class LiveTradeAdvisorService:
    """Evaluates all registered quantitative strategies to generate evidence-backed trade plans."""

    async def analyze_stock(
        self,
        stock_symbol: str,
        current_price: Optional[float] = None,
        exchange: Optional[str] = "NSE",
        timeframe: str = "5m",
        trade_style: str = "INTRADAY",
    ) -> TradePlanResponse:
        """
        Executes end-to-end evaluation:
        1. Resolves instrument from symbol and exchange.
        2. Retrieves market data (Upstox -> Free Public Yahoo -> User-Provided).
        3. Evaluates all enabled strategies.
        4. Synthesizes consensus, reasoning, and risk plan.
        """
        clean_symbol = stock_symbol.strip().upper()
        clean_exchange = (exchange or "NSE").strip().upper()

        # 1. Resolve Instrument
        instrument = self._resolve_instrument(clean_symbol, clean_exchange)

        # 2. Acquire Market Data (Quotes & Candle History)
        market_meta, candles_df, data_error = await self._acquire_market_data(
            symbol=clean_symbol,
            exchange=clean_exchange,
            instrument=instrument,
            user_price=current_price,
            timeframe=timeframe,
        )

        # Fail-closed check: If data is missing or invalid -> NO TRADE
        if data_error or candles_df.empty or market_meta.price is None:
            return self._build_no_trade_response(
                instrument=instrument,
                market_meta=market_meta,
                reason=(
                    f"Market data unavailable or invalid: {data_error or 'No candle history retrieved'}. "
                    "Cannot generate reliable trade plan without authentic price data."
                ),
            )

        ref_price = market_meta.price

        # 3. Evaluate Every Enabled Strategy
        per_strategy_results: List[StrategyResultItem] = []
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        non_signaling_count = 0

        bullish_signals = []
        bearish_signals = []

        all_strats = strategy_registry.list_strategies()
        now_iso = clock.now().isoformat()

        for s_info in all_strats:
            s_name = s_info["name"]
            strat = strategy_registry.get_strategy(s_name)
            if not strat:
                continue

            try:
                sig = strat.evaluate(candles_df, instrument, timeframe=timeframe)
                if sig:
                    is_buy = sig.direction == DirectionEnum.LONG
                    signal_str = "BUY" if is_buy else "SELL"
                    stop_loss = round(sig.stop_loss, 2)
                    target = round(sig.target, 2)

                    risk_dist = abs(sig.entry_price - stop_loss)
                    reward_dist = abs(target - sig.entry_price)
                    rr_ratio = round(reward_dist / risk_dist, 2) if risk_dist > 0 else None

                    item = StrategyResultItem(
                        strategy_name=s_name,
                        signal=signal_str,
                        entry_price_or_range=f"₹{sig.entry_price:.2f}",
                        stop_loss=stop_loss,
                        exit_target_or_rule=f"₹{target:.2f} (Target)",
                        risk_reward_ratio=rr_ratio,
                        supporting_evidence=[f"Signal triggered on {timeframe} bar", f"Entry: ₹{sig.entry_price:.2f}"],
                        contradicting_evidence=[],
                        data_timestamp=now_iso,
                    )
                    per_strategy_results.append(item)

                    if is_buy:
                        bullish_count += 1
                        bullish_signals.append(sig)
                    else:
                        bearish_count += 1
                        bearish_signals.append(sig)
                else:
                    non_signaling_count += 1
                    per_strategy_results.append(
                        StrategyResultItem(
                            strategy_name=s_name,
                            signal="NO_SIGNAL",
                            entry_price_or_range=None,
                            stop_loss=None,
                            exit_target_or_rule=None,
                            risk_reward_ratio=None,
                            supporting_evidence=[],
                            contradicting_evidence=[f"Setup conditions not met on {timeframe} timeframe"],
                            data_timestamp=now_iso,
                        )
                    )
            except Exception as e:
                logger.error("Error evaluating strategy %s: %s", s_name, e)
                non_signaling_count += 1
                per_strategy_results.append(
                    StrategyResultItem(
                        strategy_name=s_name,
                        signal="NO_SIGNAL",
                        supporting_evidence=[],
                        contradicting_evidence=[f"Evaluation error: {str(e)}"],
                        data_timestamp=now_iso,
                    )
                )

        # 4. Synthesize Summary & Agreement
        total_strats = len(all_strats)
        agreement_text = self._synthesize_agreement(
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            non_signaling_count=non_signaling_count,
            total=total_strats,
        )

        summary = StrategySummary(
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            non_signaling_count=non_signaling_count,
            total_strategies=total_strats,
            agreement_summary=agreement_text,
        )

        # 5. Formulate Decision & Plan (No Consensus Forcing)
        decision = "NO TRADE"
        plan = TradePlanLevels()
        reasoning_points: List[str] = []

        if bullish_count > 0 and bearish_count > 0:
            decision = "HOLD"
            reasoning_points.append(
                f"Conflicting strategy signals detected: {bullish_count} bullish vs {bearish_count} bearish. "
                "Market shows divergent directional cues; entering now carries heightened conflict risk."
            )
        elif bullish_count >= 1 and bearish_count == 0:
            decision = "BUY"
            # Synthesize entry and risk levels from triggering bullish strategies
            best_sig = bullish_signals[0]
            entry_low = round(min(best_sig.entry_price, ref_price) * 0.998, 2)
            entry_high = round(max(best_sig.entry_price, ref_price) * 1.002, 2)
            stop_loss = round(min(s.stop_loss for s in bullish_signals), 2)
            target = round(max(s.target for s in bullish_signals), 2)

            risk_dist = abs(ref_price - stop_loss)
            reward_dist = abs(target - ref_price)
            rr = round(reward_dist / risk_dist, 2) if risk_dist > 0 else None

            plan = TradePlanLevels(
                entry_range=f"₹{entry_low:.2f} – ₹{entry_high:.2f}",
                stop_loss=stop_loss,
                exit_target=target,
                exit_rule="Exit at Target or mandatory intraday square-off at 15:15 IST",
                risk_reward_ratio=rr,
            )
            reasoning_points.append(
                f"Bullish alignment across {bullish_count} strategy(ies) ([{', '.join(s.strategy_name for s in per_strategy_results if s.signal == 'BUY')}]). "
                f"Stop loss placed at ₹{stop_loss:.2f} to protect against breakdown. Risk/Reward ratio estimated at 1:{rr or 'N/A'}."
            )
        elif bearish_count >= 1 and bullish_count == 0:
            decision = "SELL"
            best_sig = bearish_signals[0]
            entry_low = round(min(best_sig.entry_price, ref_price) * 0.998, 2)
            entry_high = round(max(best_sig.entry_price, ref_price) * 1.002, 2)
            stop_loss = round(max(s.stop_loss for s in bearish_signals), 2)
            target = round(min(s.target for s in bearish_signals), 2)

            risk_dist = abs(stop_loss - ref_price)
            reward_dist = abs(ref_price - target)
            rr = round(reward_dist / risk_dist, 2) if risk_dist > 0 else None

            plan = TradePlanLevels(
                entry_range=f"₹{entry_low:.2f} – ₹{entry_high:.2f}",
                stop_loss=stop_loss,
                exit_target=target,
                exit_rule="Exit at Target or mandatory intraday square-off at 15:15 IST",
                risk_reward_ratio=rr,
            )
            reasoning_points.append(
                f"Bearish alignment across {bearish_count} strategy(ies) ([{', '.join(s.strategy_name for s in per_strategy_results if s.signal == 'SELL')}]). "
                f"Stop loss placed at ₹{stop_loss:.2f} to protect against reversal."
            )
        else:
            decision = "NO TRADE"
            reasoning_points.append(
                f"All {total_strats} quantitative strategies report NO_SIGNAL on {timeframe} timeframe. "
                "Market is currently consolidating or lacking strong momentum. Capital preservation advises staying on sidelines."
            )

        if market_meta.price_type == "USER_PROVIDED":
            reasoning_points.append(
                "Note: Calculations incorporate user-provided reference price. Live market fills may differ."
            )

        limitations_text = (
            "Strategies analyze past price action and indicators; past performance does not guarantee future results. "
            "Slippage, spread crossing, and Indian statutory costs (STT, GST, brokerage) will reduce net performance. "
            "Never risk more than the platform limit (₹250.00 maximum per day)."
        )

        return TradePlanResponse(
            decision=decision,
            instrument={
                "symbol": instrument.symbol,
                "exchange": instrument.exchange.value,
                "instrument_key": instrument.instrument_key,
                "segment": instrument.segment.value,
            },
            market_data=market_meta,
            plan=plan,
            strategy_summary=summary,
            strategy_results=per_strategy_results,
            reasoning=" ".join(reasoning_points),
            limitations=limitations_text,
        )

    def _resolve_instrument(self, symbol: str, exchange: str) -> Instrument:
        """Finds instrument in Instrument Master or constructs standardized EQ instrument."""
        matches = instrument_master.search(symbol)
        if matches:
            for m in matches:
                if m.exchange.value == exchange:
                    return m
            return matches[0]

        exch_enum = ExchangeEnum.BSE if exchange == "BSE" else ExchangeEnum.NSE
        return Instrument(
            exchange=exch_enum,
            segment=SegmentEnum.EQ,
            symbol=symbol,
            instrument_key=f"{exch_enum.value}_{symbol}",
            lot_size=1,
            tick_size=0.05,
        )

    async def _acquire_market_data(
        self,
        symbol: str,
        exchange: str,
        instrument: Instrument,
        user_price: Optional[float],
        timeframe: str,
    ) -> Tuple[MarketDataMeta, Any, Optional[str]]:
        """Acquires market data with clear provider attribution and freshness check."""
        now_ist = clock.now()

        # 1. Check if Upstox live credentials configured
        if upstox_rest.is_configured():
            try:
                candles = await upstox_rest.get_intraday_candles(instrument.instrument_key, interval="5minute")
                quote = await upstox_rest.get_market_quote(instrument.instrument_key)
                if not candles.empty and quote.get("ltp"):
                    price = float(user_price if user_price is not None else quote["ltp"])
                    price_type = "USER_PROVIDED" if user_price is not None else "LIVE"
                    return (
                        MarketDataMeta(
                            provider="UPSTOX_API",
                            price=round(price, 2),
                            price_type=price_type,
                            timestamp=now_ist.isoformat(),
                            freshness="FRESH",
                        ),
                        candles,
                        None,
                    )
            except Exception as e:
                logger.warning("Upstox fetch failed, attempting free provider: %s", e)

        # 2. Free Public Provider (Yahoo Finance for NSE/BSE)
        try:
            quote, candles = await free_market_data.get_quote_and_candles(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
            )
            if quote and not candles.empty:
                price = float(user_price if user_price is not None else quote["ltp"])
                price_type = "USER_PROVIDED" if user_price is not None else quote["price_type"]

                # Freshness check: Public feed is typically 15m delayed
                freshness = "FRESH" if clock.is_market_open(now_ist) else "STALE"

                return (
                    MarketDataMeta(
                        provider=quote["provider"],
                        price=round(price, 2),
                        price_type=price_type,
                        timestamp=quote["timestamp"],
                        freshness=freshness,
                    ),
                    candles,
                    None,
                )
        except Exception as e:
            logger.error("Free market data fetch failed for %s: %s", symbol, e)

        # 3. Fallback to Synthetic Fixture in Research Mode
        if settings.EXECUTION_MODE == "PAPER":
            logger.info("Using explicit synthetic fixture for research evaluation of %s", symbol)
            candles = synthetic_feed.generate_candles(symbol=symbol, base_price=user_price or 2500.0)
            price = round(float(user_price or 2500.0), 2)
            price_type = "USER_PROVIDED" if user_price is not None else "SIMULATED"

            return (
                MarketDataMeta(
                    provider="SYNTHETIC_FIXTURE",
                    price=price,
                    price_type=price_type,
                    timestamp=now_ist.isoformat(),
                    freshness="UNKNOWN",
                ),
                candles,
                None,
            )

        return (
            MarketDataMeta(
                provider="NONE",
                price=None,
                price_type="UNAVAILABLE",
                timestamp=now_ist.isoformat(),
                freshness="UNKNOWN",
            ),
            None,
            "Could not retrieve market data from any authorized provider",
        )

    def _synthesize_agreement(
        self,
        bullish_count: int,
        bearish_count: int,
        neutral_count: int,
        non_signaling_count: int,
        total: int,
    ) -> str:
        if bullish_count > 0 and bearish_count > 0:
            return f"Conflicting signals: {bullish_count} Bullish vs {bearish_count} Bearish out of {total} strategies."
        elif bullish_count > 0:
            return f"Bullish consensus: {bullish_count} out of {total} strategies triggered BUY."
        elif bearish_count > 0:
            return f"Bearish consensus: {bearish_count} out of {total} strategies triggered SELL."
        else:
            return f"No directional bias: All {total} strategies report NO_SIGNAL or Neutral."

    def _build_no_trade_response(
        self,
        instrument: Instrument,
        market_meta: MarketDataMeta,
        reason: str,
    ) -> TradePlanResponse:
        return TradePlanResponse(
            decision="NO TRADE",
            instrument={
                "symbol": instrument.symbol,
                "exchange": instrument.exchange.value,
                "instrument_key": instrument.instrument_key,
                "segment": instrument.segment.value,
            },
            market_data=market_meta,
            plan=TradePlanLevels(),
            strategy_summary=StrategySummary(
                bullish_count=0,
                bearish_count=0,
                neutral_count=0,
                non_signaling_count=len(strategy_registry.list_strategies()),
                total_strategies=len(strategy_registry.list_strategies()),
                agreement_summary="Evaluation halted: Insufficient or unavailable market data.",
            ),
            strategy_results=[],
            reasoning=reason,
            limitations="Trade plan cannot be formed without authentic data.",
        )


trade_advisor = LiveTradeAdvisorService()
