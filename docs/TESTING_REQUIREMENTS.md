# Testing, Verification & Hardening Requirements

## 1. Zero-Lookahead Backtesting Engine Protocol

To ensure realistic quantitative research, backtests (`backtesting/engine.py`) adhere to strict chronological invariants:
- **Decision Timestamp:** Strategy indicators and signals are calculated strictly on the completed candle bar at timestamp $t$ (Close).
- **Execution Timestamp:** The simulated order is executed on the *subsequent* candle bar at timestamp $t+1$ (Open) with half-spread adjustment and slippage added.
- **Intrabar Exit Resolution:**
  - If both Stop Loss and Profit Target levels are touched within the high-low span of the same candle bar, the conservative assumption assumes the **Stop Loss was triggered first**.
- **Mandatory 15:15 IST Square-Off:** All remaining positions are forcefully squared off at the 15:15 bar close price.
- **₹250 Daily Loss Limit:** Daily cumulative net P&L is tracked; if net loss breaches ₹250.00, trading halts for the remainder of that day.

---

## 2. Walk-Forward & Out-of-Sample Validation

- **Rolling Splits:** Training / In-Sample (IS) window and Validation / Out-of-Sample (OOS) window (e.g., 60 days IS, 20 days OOS).
- **Overfitting Prevention:** Performance metrics (Sharpe ratio, Profit Factor, Win Rate) are scored on out-of-sample periods to penalize over-optimized parameters.

---

## 3. Regression & Chaos Test Coverage

The test suite consists of **122 automated unit, integration, and chaos tests** across 12 test modules:

| Test File | Tests | Focus Area |
|---|---|---|
| `test_config.py` | 5 | Safe defaults, secret masking, and live trading locks |
| `test_clock.py` | 7 | IST market sessions, holiday calendar, pre-open & square-off windows |
| `test_instruments.py` | 4 | Instrument Master CSV/Gzip parsing, symbol lookup, option chains |
| `test_synthetic_feed.py` | 4 | Jump diffusion math, candle invariants, order book depth |
| `test_validator.py` | 7 | Price bounds, stale quote circuit breaker, tick deduplication |
| `test_indicators.py` | 7 | Vectorized SMA, EMA, RSI, VWAP, Supertrend, Bollinger Bands, ATR |
| `test_strategies.py` | 8 | 8 candidate strategies signal generation on completed bars |
| `test_costs_and_sizing.py` | 5 | Indian statutory costs (EQ & FO) and position sizer ($\le ₹250$ risk) |
| `test_agents.py` | 8 | Multi-agent evaluation, 2s timeouts, contradiction detection |
| `test_backtester.py` | 6 | Zero lookahead bias, conservative exit, walk-forward validator |
| `test_risk_enforcement.py` | 11 | 12 pre-trade gates, ₹250 loss halt, SQLite restart recovery |
| `test_paper_trading.py` | 13 | Paper broker, portfolio tracker MTM, SL/Target, reconciliation |
| `test_dashboard_and_telegram.py` | 8 | React UI serving, WebSocket/SSE streaming, Telegram commands |
| `test_chaos_and_hardening.py` | 6 | Concurrency race conditions, WAL stress, crash recovery, rate limit |

---

## 4. Execution Commands

```bash
# Run complete test suite with coverage
source .venv/bin/activate
pytest --cov=backend.app --cov=strategies --cov=agents --cov=execution --cov=backtesting --cov=risk tests/ -v

# Run chaos and hardening suite specifically
pytest tests/test_chaos_and_hardening.py -v

# Run frontend production build
cd frontend && npm run build
```
