# Specialist Agent Specifications

## 1. Overview & Operational Principles

The multi-agent framework provides specialized, independent analytical perspectives on market conditions.
Agents are strictly **advisory**:
- Agents do **NOT** have access to broker execution endpoints.
- Agents do **NOT** have authority to override risk parameters or place orders.
- Agent failures or timeouts do **NOT** allow an unvalidated trade to proceed.
- Agent responses must strictly conform to the `AgentAssessment` schema.

---

## 2. Core Agent Assessment Schema

Every agent emits a structured assessment adhering to:

```python
class AgentAssessment(BaseModel):
    agent_name: str
    stance: str          # "BULLISH" | "BEARISH" | "NEUTRAL" | "NO_SIGNAL"
    confidence: float    # 0.0 to 1.0
    evidence: List[str]  # Concrete data points supporting stance
    timestamp: datetime  # Authentic evaluation time (IST)
```

---

## 3. Specialist Agent Roster

### 3.1 Technical Analyst Agent (`agents/technical_analyst.py`)
- **Focus:** Multi-timeframe trend alignment, momentum oscillators, and volatility bands.
- **Inputs:** OHLCV DataFrame, calculated indicators (RSI, EMA 9/21, Supertrend, Bollinger Bands, ATR).
- **Evaluation Criteria:**
  - `BULLISH`: EMA 9 > EMA 21, Price > Supertrend, RSI between 50 and 70.
  - `BEARISH`: EMA 9 < EMA 21, Price < Supertrend, RSI between 30 and 50.
  - `NEUTRAL`: Conflicting indicator stances or RSI in extreme overbought/oversold territory (>75 or <25).
- **Timeout:** 2.0 seconds maximum.
- **Fallback Behavior:** Returns `NEUTRAL` with confidence `0.0` and fallback reason.

### 3.2 Price Action Agent (`agents/price_action.py`)
- **Focus:** Horizontal support and resistance levels, swing highs/lows, candle patterns, and opening range breakouts.
- **Inputs:** OHLCV DataFrame, recent session swing levels, current tick.
- **Evaluation Criteria:**
  - Identifies pin bars, engulfing candles, hammer/shooting stars, and range consolidations.
  - Checks if price is testing a major 15-minute or 60-minute support/resistance pivot.
  - Confirms volume expansion on breakout bars.
- **Timeout:** 2.0 seconds maximum.
- **Fallback Behavior:** Returns `NO_SIGNAL` if pattern confirmation is incomplete.

### 3.3 Quantitative Researcher Agent (`agents/quantitative_researcher.py`)
- **Focus:** Statistical properties, z-scores, mean reversion probability, and historical edge.
- **Inputs:** Historical candle returns series, current z-score relative to 20-period moving average.
- **Evaluation Criteria:**
  - Evaluates whether price deviation $|z| > 2.0$ represents an anomalous exhaustion or a strong momentum regime.
  - Computes Hurst exponent and variance ratio to differentiate trending vs mean-reverting regimes.
- **Timeout:** 2.0 seconds maximum.

### 3.4 Options Intelligence Agent (`agents/options_intelligence.py`)
- **Focus:** Put-Call Ratio (PCR), Open Interest (OI) buildup, max pain levels, and strike activity.
- **Inputs:** Upstox Option Chain snapshot (CE/PE strike data, OI, implied volatility).
- **Evaluation Criteria:**
  - PCR $> 1.2$: Bullish sentiment / heavy put writing support.
  - PCR $< 0.8$: Bearish sentiment / heavy call writing resistance.
  - High OI buildup at immediate strike identifies critical support/resistance boundaries.
- **Timeout:** 2.0 seconds maximum.

### 3.5 Market Microstructure Agent (`agents/market_microstructure.py`)
- **Focus:** Order book depth imbalances, bid-ask spread stability, and institutional sweep activity.
- **Inputs:** Level-2 5-depth order book (bids, asks, quantities).
- **Evaluation Criteria:**
  - Bid/Ask quantity ratio $> 1.5$ with tight spread: Bullish buyer pressure.
  - Bid/Ask quantity ratio $< 0.67$: Bearish seller pressure.
  - Flags abnormal spread widening ($> 3 \times$ tick size) as liquidity risk.
- **Timeout:** 2.0 seconds maximum.

### 3.6 Strategy Validator Agent (`agents/strategy_validator.py`)
- **Focus:** Cross-agent contradiction detection and consensus verification.
- **Inputs:** Collection of `AgentAssessment` outputs from all specialists, proposed trade direction.
- **Contradiction Detection Rules:**
  - If proposed direction is `LONG` and Technical Analyst is `BEARISH`: Flagged as severe contradiction.
  - If proposed direction is `SHORT` and Options Intelligence indicates heavy put writing support: Flagged as contradiction.
  - Conflicting signals lower the overall proposal confidence score and are documented in the Trade Proposal.

---

## 4. Agent Orchestrator (`agents/orchestrator.py`)

- **Execution Model:** Evaluates all specialist agents concurrently using `asyncio.gather(..., return_exceptions=True)`.
- **Fault Tolerance:** If any single agent crashes or exceeds its 2.0s timeout ceiling, the orchestrator logs the exception and replaces the output with a fail-closed `NEUTRAL` stance.
- **Consensus Scoring:**
  $$\text{Score} = \frac{\sum (\text{Stance Weight} \times \text{Confidence})}{\text{Total Responding Agents}}$$
- An overall confidence below $0.50$ halts proposal generation.
