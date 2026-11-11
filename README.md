# AI Multi-Agent Trading System — Indian Financial Markets

A modular, locally hosted AI-powered multi-agent quantitative trading research, strategy validation, backtesting, paper-trading, and human-in-the-loop platform engineered specifically for Indian financial markets (NSE and BSE cash equities and F&O derivatives).

> **Operating Mode:** Conservative Research & Paper Trading Only (`EXECUTION_MODE=PAPER`, `LIVE_TRADING_ENABLED=false`).  
> **Risk Sovereignty:** Central Risk Engine enforces a hard daily loss limit of **₹250.00 maximum** across realized P&L, unrealized mark-to-market P&L, and full Indian statutory transaction costs. Restarts cannot reset the halt.

---

## 1. System Architecture

```
AI-TRADING-SYSTEM/
├── backend/app/
│   ├── adapters/          # Upstox REST, WebSocket Feed V3 Proto, Synthetic Feed, Telegram Bot
│   ├── api/v1/            # FastAPI REST routes (Market Data, Strategies, Backtest, Risk, Execution, Stream)
│   ├── core/              # Config, Secret-Masking Logger, IST Clock (Session/Holidays)
│   ├── db/                # SQLite WAL persistence, models, async session factory
│   └── models/            # Pydantic schemas (Trade Proposal v1.0, Instrument, RiskState)
│
├── frontend/              # Local Web Dashboard (React 18 + TypeScript + Tailwind CSS + Vite)
│   ├── src/components/    # Header, RiskCapitalBar, ProposalDeck, PositionsTable, OrdersHistory, Reconciliation
│   └── dist/              # Production compiled bundle mounted directly on FastAPI
│
├── agents/                # Specialist Advisory Agents (Technical Analyst, Price Action, Quant, Options, Microstructure)
├── strategies/            # 8 Deterministic Strategies (VWAP, EMA, RSI, ORB, Supertrend, SR Breakout, Volume, Mean Reversion)
├── risk/                  # Deterministic Central Risk Engine (12 Pre-Trade Gates, ₹250 Loss Halt, Kill Switch)
├── execution/             # Paper Broker (Spread/Slippage Model), Portfolio Tracker, Proposal Service, Reconciliation
├── backtesting/           # Event-Driven Zero-Lookahead Engine, Tear Sheet Metrics, Walk-Forward Validator
├── data/                  # SQLite WAL database & Upstox instrument master cache
├── docs/                  # Architectural, Strategy, Risk, API, and Testing specifications
└── tests/                 # 122 Unit, Integration, and Chaos tests (82% code coverage)
```

---

## 2. Key Features

- **Deterministic Central Risk Engine:** 12 non-bypassable pre-trade risk gates protecting capital ($\le ₹25,000$). When net session losses reach ₹250.00, trading halts fail-closed for the rest of the day. A crash or restart recovers `HALTED` state directly from SQLite without resetting the counter.
- **Accurate Indian Statutory Charges:** Accurately models Brokerage, STT ($0.025\%$ sell for equity, $0.1\%$ sell premium for options), Exchange Turnover (NSE $0.00297\%$), GST ($18\%$), SEBI turnover fees, and Stamp Duty ($0.003\%$ buy side).
- **Multi-Agent Advisory Team:** Independent specialist agents evaluate technical indicators, price action pivots, quantitative z-scores, option chain PCR/OI, and order book depth with 2.0s timeout isolation and contradiction detection.
- **Human-in-the-Loop Proposal Workflow:** Strategies generate structured Trade Proposals (Schema v1.0). The operator approves or rejects trades via the Web Dashboard or Telegram bot before the Risk Engine evaluates and paper broker executes.
- **Microstructure Paper Broker:** Realistic simulated execution crossing the bid-ask spread with tick-level slippage modeling. Every order and position carries authentic data provenance (`execution_mode="PAPER"`, `provenance="SIMULATED"`).
- **Mandatory 15:15 IST Square-Off:** Intraday positions are automatically closed at 15:15 IST to avoid overnight risk.
- **Real-Time Web Dashboard:** Responsive dark-mode dashboard streaming live session metrics, ₹250 limit progress bar, active proposals deck, open positions, order history, and reconciliation status.
- **Fail-Closed Safety Barrier:** `LiveBrokerAdapter` physically prohibits live order placement by raising `SafetyViolationError`.

---

## 3. Quick Start & Setup

### Prerequisites
- macOS (Apple Silicon M-series or Intel)
- Python 3.11+
- Node.js v18+ and npm

### Installation
```bash
# 1. Clone repository and navigate to root
cd "AI Trading"

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install and build frontend dashboard
cd frontend
npm install
npm run build
cd ..
```

### Running the System
```bash
# Start the unified backend and dashboard
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```
The compiled React dashboard will load immediately, connecting to the FastAPI backend and real-time streaming endpoints.

---

## 4. Verification & Testing Suite

The repository includes a comprehensive test suite of **122 automated unit, integration, and chaos tests** with **82% code coverage**:

```bash
# Run full test suite with coverage
source .venv/bin/activate
pytest --cov=backend.app --cov=strategies --cov=agents --cov=execution --cov=backtesting --cov=risk tests/ -v
```

### Running Chaos & Hardening Tests
```bash
pytest tests/test_chaos_and_hardening.py -v
```

---

## 5. System Safety & Operating Rules
- Real-money live trading is barred by design (`LIVE_TRADING_ENABLED=false`, `EXECUTION_MODE=PAPER`).
- The Central Risk Engine cannot be bypassed by any agent or LLM.
- Daily hard loss ceiling: **₹250.00 maximum**.
- Stale market quotes ($> 5.0$ seconds) are rejected fail-closed.
- Zero Git staging, commits, or pushes unless explicitly instructed by the user.
