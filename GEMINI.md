# AI Trading System — Gemini & AI Agent Directives

## 1. Primary Operating Principles

* **Specification Document:** Read and follow [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md).
* **Research & Paper Mode Only:** Real-money trading is disabled by design (`LIVE_TRADING_ENABLED=false`, `EXECUTION_MODE=PAPER`).
* **Deterministic Risk Sovereignty:** The Central Risk Engine is fail-closed, deterministic, and non-bypassable. An AI agent or LLM must NEVER have a tool, route, or authority to override the risk engine or place live orders.
* **Capital & Loss Thresholds:**
  - Configured capital strictly constrained (under ₹25,000 starting capital).
  - Hard daily loss limit: **₹250 maximum** across realized P&L, unrealized P&L, and all statutory transaction costs (brokerage, STT, GST, exchange fees, SEBI, stamp duty).
  - When the ₹250 threshold is reached, transition immediately to `HALTED` state. A restart or power interruption must never reset this halt.
* **Fail-Closed Stance:** If quotes are stale (>5s), contract details are ambiguous, API connection drops, or any check fails, refuse the trade proposal.
* **No Git Modifications:** Never stage, commit, or push Git changes unless explicitly instructed by the user.
* **Data Provenance:** Every displayed price or quote must have an authentic source and timestamp. Never invent prices or fills. Simulated results must always be explicitly marked as `PAPER` or `SIMULATED`.

