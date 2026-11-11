# Indian Multi-Agent Trading System — Project Specification

> **Document type:** implementation specification  
> **Status:** initial build brief; inspect the repository and environment before changing anything  
> **Primary rule:** begin in research and paper-trading mode. Real-money trading is off by default and outside the initial implementation scope.

## README: How to use this brief

1. Open the existing project folder in Antigravity and provide it with this file as the project brief.
2. Ask the coding agent to inspect the repository, machine, installed tools, and existing configuration first. It must return an inventory, proposed architecture, risks, dependencies, and a phase-by-phase plan before editing files.
3. Authorize and implement one phase at a time. Require the agent to run and report the phase's checks before proceeding. Do not ask it to generate the whole platform in one pass.
4. Keep this file as `docs/PROJECT_SPEC.md` in the project. Add a concise `GEMINI.md` that points to this specification and reiterates its safety rules.
5. Do not provide broker secrets in chat or commit them to source control. Configure secrets locally using the project's documented secret mechanism.

### Initial instruction to Antigravity

> Read `docs/PROJECT_SPEC.md` completely. Before coding, inspect the existing project and local macOS environment without overwriting files. Report what exists, what is missing, any official API or data-access constraints, the proposed architecture, key risks, and an incremental implementation plan. Do not place or enable live orders. Wait for my approval of the plan before implementing Phase 1. Never stage, commit, or push Git changes unless I explicitly ask.

---

## 1. Project intent

<project>
  <name>Indian Multi-Agent Intraday Trading Research and Paper-Trading Platform</name>
  <purpose>Build a modular, locally hosted system for Indian market research, deterministic strategy evaluation, backtesting, paper trading, risk monitoring, and human-reviewed trade proposals.</purpose>
  <operator>One individual operating their own system</operator>
  <primary_outcome>A reliable local platform that measures net-of-cost strategy performance and protects limited capital; profitability is not promised.</primary_outcome>
</project>

The system is not a guaranteed-profit product. Never fabricate prices, fills, performance, or data provenance. Use AI for research, summarization, and coordination; use explicit, deterministic, testable code for signal rules, position sizing, risk checks, and order-state handling. An LLM must never have a tool or path that can bypass the risk engine or place live orders.

## 2. User requirements and operating context

| Requirement | Specification |
|---|---|
| Computer | Apple MacBook Pro with M2; local macOS deployment |
| Broker | Upstox; use its official, current API documentation |
| Starting capital | Under ₹25,000; treat the configured available capital as a strict constraint |
| Currency and timezone | INR and `Asia/Kolkata` |
| Style | Intraday for supported tradable segments |
| Risk preference | Conservative; prioritize capital preservation and low trade frequency |
| Daily loss limit | ₹250 maximum; hard halt on new entries when reached |
| Halt response | Stop new entries and require explicit human review; record any authorized manual override in an audit log and repeat risk checks. The system must never reset the loss counter silently. Default behavior after a halt is remain halted for the session. |
| Execution | Hybrid workflow: agents propose; human approves proposals; deterministic controls validate; paper execution first |
| Default execution mode | Paper only; no live trading by default |
| Timeframes | At minimum 1m, 5m, 15m, and 60m where valid data is available; configurable and instrument-aware |
| Interfaces | Local web dashboard and optional Telegram notifications/approval controls |
| Source control | Do not stage, commit, or push unless explicitly asked |

The laptop may stop processing when asleep, shut down, or disconnected. Display system connectivity and last successful market-data time clearly. Never imply monitoring continues while the application is stopped.

## 3. Markets and instrument scope

<markets>
  <intraday>
    <segment>NSE cash equities</segment>
    <segment>BSE cash equities</segment>
    <segment>NSE index and stock futures and options</segment>
    <segment>BSE index and stock derivatives where supported and eligible</segment>
    <segment>MCX commodities, subject to verified broker access, contract specifications, and sessions</segment>
  </intraday>
  <separate_module name="Mutual funds and ETFs">
    <rule>Keep mutual funds in a separate non-intraday investment/portfolio module. Do not route mutual fund transactions through intraday strategies.</rule>
    <rule>ETFs may be exchange-traded, but keep the requested funds/ETF holdings and investment workflows separate from intraday strategy execution unless a later explicit design decision changes this.</rule>
  </separate_module>
</markets>

Requirements:

- Represent exchange, segment, instrument identifier, expiry, lot size, tick size, trading status, and currency explicitly.
- Obtain current instrument masters, lot sizes, expiry calendars, exchange sessions, and margin requirements from authoritative sources or supported broker endpoints. Timestamp and identify the source.
- Reject an order proposal if the contract is unavailable, expired, stale, unaffordable, or has insufficient margin. Do not assume that futures or options are affordable with the stated capital.
- Respect exchange holidays, special sessions, market breaks, and segment-specific hours. Never hardcode schedules without a source and update strategy.
- Respect broker permissions, API limits, exchange rules, and applicable market-data licensing. Do not scrape restricted sources.

## 4. System architecture

Build a modular local application with clear boundaries:

1. **Market data adapters:** Upstox OAuth/API/WebSocket adapters and an explicitly labeled synthetic/test-data adapter. No synthetic or stale data may be represented as live.
2. **Data validation and storage:** validate timestamps, instrument identity, duplicates, gaps, and freshness; persist market data and provenance where licensing permits.
3. **Deterministic strategy engine:** calculate indicators and strategy signals from validated data using versioned rules.
4. **Agent services:** independent specialists produce structured findings, evidence, timestamps, confidence rationale, and data references. Agent output is advisory.
5. **Orchestrator and proposal service:** schedule agents, collect results, deduplicate proposals, surface disagreements, and assemble a human-readable trade proposal.
6. **Central risk engine:** deterministic, fail-closed authority for capital, sizing, loss limits, session state, instrument eligibility, costs, exposure, and kill switch. It cannot be overridden by agents.
7. **Approval and execution boundary:** proposal review and authenticated approval; paper execution only. A future live adapter must remain isolated and disabled.
8. **Portfolio and reconciliation:** record simulated orders, positions, charges, P&L, and discrepancies. Clearly label simulated values.
9. **Interfaces:** local dashboard, optional Telegram bot, API, health status, and audit trail.

Prefer a single-process or modest local service architecture initially. Avoid unnecessary distributed systems or cloud dependencies. Inspect the existing project and choose compatible tools rather than replacing a working stack without cause.

## 5. Specialist agents

Implement incrementally; do not build all agents in one pass. Each agent must declare its inputs, outputs, permitted tools, timeout, failure behavior, and whether it uses deterministic code or an external model. Validate all outputs against schemas. An agent failure must not cause a trade to proceed.

1. **Market Intelligence:** summarize market-moving news and corporate announcements; preserve source, timestamp, and verified/unverified distinction. No unsourced claims.
2. **Technical Analysis:** calculate indicators such as RSI, MACD, VWAP, EMA/SMA, Supertrend, Bollinger Bands, ATR, ADX, and volume measures; return evidence and timeframe-specific bullish/bearish/neutral assessments.
3. **Price Action:** identify trends, support/resistance, breakouts, false breakouts, opening ranges, candle patterns, and volume confirmation using explicit rules where possible.
4. **Quantitative Research:** evaluate momentum, mean reversion, and breakout hypotheses; report expectancy, costs, drawdown, and robustness; prevent look-ahead bias and leakage.
5. **AI/ML Research:** provide an offline research framework for features, baseline comparisons, probabilistic forecasts, volatility/trend classification, and chronological out-of-sample validation. LLM-generated price predictions are not signals.
6. **Options Intelligence:** analyze option chains, OI/change, PCR, IV, Greeks, expiry, spread, liquidity, and affordability when supported data exists. Reject illiquid or unaffordable contracts.
7. **Market Microstructure:** analyze available spread, depth, liquidity, imbalance, and slippage data. State when historical candles cannot support an order-book conclusion.
8. **Strategy Validator:** compare evidence and conflicts, reject weak proposals, and explain a measurable confidence assessment. Do not merely average agent confidence scores.
9. **Risk Management:** enforce the central risk rules in Section 6. This is a deterministic service/agent boundary, not an LLM decision.
10. **Portfolio Monitor:** track open simulated positions, realized/unrealized P&L, available funds, charges, exposure, stops, and reconciliation differences.
11. **Execution:** paper order lifecycle, simulated fills, transaction costs, rejects, and audit records. No live order capability in the initial release.

Every agent must state data freshness and provenance. Missing, malformed, contradictory, stale, or unlicensed inputs result in `no_signal` or an explicit degraded status.

## 6. Risk and safety controls

<risk_controls mode="fail_closed">
  <daily_loss_limit currency="INR">250</daily_loss_limit>
  <daily_loss_action>Block new entries and enter HALTED state. Require explicit human review to request any same-session override; record identity, time, reason, prior state, and renewed risk check. The default remains halted.</daily_loss_action>
  <default_execution_mode>PAPER</default_execution_mode>
  <live_trading_enabled>false</live_trading_enabled>
  <agent_bypass_allowed>false</agent_bypass_allowed>
</risk_controls>

The central risk engine must:

- Check the daily limit before every entry, including pending orders and exposure. Define and document how realized P&L, estimated unrealized P&L, fees, and pending exposure contribute. Use conservative estimates where values are uncertain.
- Enforce position sizing, maximum exposure, stop-loss requirements, risk/reward rules, available capital, margin, slippage, instrument-specific limits, maximum simultaneous positions, maximum session trades, and configured cooldowns.
- Reject trades with missing stop, stale quotes, uncertain contract details, insufficient funds/margin, excessive spread/slippage, or incomplete cost estimates.
- Deduplicate requests and orders. Make state changes idempotent and auditable.
- Provide an emergency kill switch that blocks new orders and clearly reports open simulated positions. It must not falsely claim broker positions were closed.
- Halt safely on risk-service errors, data-feed interruption, clock/session uncertainty, persistence failure, or inconsistent broker/account state.
- Keep a durable audit log of proposals, approvals/rejections, risk decisions, order states, overrides, configuration changes, and faults.
- Prevent Telegram, dashboard, agent, or API controls from bypassing risk gates. Authenticate control actions and protect against replay/duplicate approval.

A manual review does not erase the ₹250 threshold event or risk history. If an override path is implemented, it must be opt-in, visibly labeled, require fresh risk evaluation, have a narrowly scoped duration and limits, and be disabled for live execution by default.

## 7. Trade proposal data contract

Use a versioned, validated schema similar to:

```json
{
  "schema_version": "1.0",
  "proposal_id": "uuid",
  "created_at": "ISO-8601 with timezone",
  "instrument": {"exchange": "", "segment": "", "symbol": "", "instrument_key": "", "expiry": null, "lot_size": null},
  "direction": "LONG | SHORT",
  "strategy": {"name": "", "version": ""},
  "timeframe": "",
  "market_data": {"as_of": "", "source": "", "is_stale": false},
  "entry": {"order_type": "", "reference_price": null, "limit_price": null},
  "stop_loss": null,
  "target": null,
  "quantity": null,
  "estimated_risk_inr": null,
  "estimated_reward_inr": null,
  "estimated_costs_inr": null,
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "agent_statuses": [],
  "risk_decision": "PENDING | APPROVED | REJECTED",
  "human_decision": "PENDING | APPROVED | REJECTED",
  "execution_mode": "PAPER"
}
```

Reject unknown fields where unsafe, invalid units, impossible prices/quantities, invalid enum values, and missing provenance. A proposal is not an order. The paper executor may only accept a proposal after risk approval and the configured human approval workflow.

## 8. Upstox integration

Official documentation entry point: <https://upstox.com/developer/api-documentation/>. Verify current API details at implementation time; do not rely on copied or outdated endpoint assumptions.

Research and implement only supported capabilities needed for the active phase, such as OAuth, instrument master, quotes, historical candles, market WebSocket, option chain, funds/margin, positions, and order endpoints for future isolation. For every endpoint, document account permissions, scopes, rate limits, data limitations, and failure handling.

- Store credentials only in a local secret mechanism/environment configuration that is excluded from version control. Never expose tokens in logs, frontend code, screenshots, or reports.
- Handle token expiry, authorization failure, throttling, network loss, reconnects, malformed messages, stale quotes, and partial data explicitly.
- Validate stream freshness and instrument identity. Never fill missing values with invented market data.
- Make account and order functionality read-only or simulated unless explicitly required for paper mode.
- Do not implement or activate live placement/cancellation in the initial release.

## 9. Strategy and backtesting requirements

Create a versioned, pluggable framework. Each strategy declares compatible instruments/timeframes, inputs, deterministic entry/exit rules, stops, targets, sizing interface, assumptions, and version. Initial research candidates:

- VWAP trend continuation
- EMA crossover with trend confirmation
- RSI momentum
- Opening range breakout
- Supertrend trend following
- Support/resistance breakout
- Volume-confirmed breakout
- Mean reversion

These are hypotheses, not recommendations or claims of profitability. Allow a strategy to return no trade. Do not optimize only for win rate or trade count.

Backtesting must:

- Use chronological train/validation/test partitions and walk-forward evaluation where appropriate.
- Avoid look-ahead bias, survivorship bias where relevant, data leakage, and unrealistic intrabar fills.
- Account for corporate actions, delisted instruments where data permits, derivative expiry/roll, lot sizes, and contract changes.
- Model brokerage, STT, exchange charges, GST, SEBI charges, stamp duty, bid-ask spread, and slippage using dated, documented schedules and assumptions. Do not present fee assumptions as current without verification.
- Report gross and net P&L, cost breakdown, trade count, win rate, expectancy, profit factor, maximum drawdown, Sharpe/Sortino where statistically meaningful, average holding time, and data coverage.
- Label data source, date range, assumptions, and limitations. Never fabricate backtest data/results or imply past results guarantee future outcomes.

## 10. Paper trading

Implement paper trading before any live-execution work. Simulated fills must be clearly labeled and use configurable, documented fill/slippage assumptions. Model order states, rejects, partial fills if supported, timeouts, cancellations, fees, and price gaps. Persist every state transition. Paper positions and P&L must never be confused with broker account positions or real P&L.

Promotion to any future live-trading phase is explicitly out of scope for initial delivery and requires a separate user request and a new review. Keep live capability disabled, absent from ordinary controls, and guarded by independent configuration and code-level checks.

## 11. Dashboard and Telegram

### Local dashboard

Provide responsive pages or equivalent views for:

- **Overview:** session status, data freshness, watchlist/index context, proposals, simulated P&L, available configured capital, system health.
- **Market scanner:** instrument search, supported timeframes, validated indicators, volume/volatility, signal history, data provenance.
- **Options analytics:** option chain, strikes, Greeks, IV, OI/PCR, spread, liquidity, source and timestamp when available.
- **Agent center:** agent health, findings/evidence, disagreements, errors, enable/disable controls where safe.
- **Strategy lab:** configuration, backtests, costs, chronological out-of-sample results, comparisons.
- **Paper trading:** proposal review, approve/reject, simulated orders/positions, history, fees, P&L.
- **Risk:** ₹250 daily cap, current loss calculation, exposure, halt state, limits, kill switch and audit trail.
- **Reports:** daily/weekly and strategy summaries with costs and data limitations.

Show `PAPER` prominently whenever displaying simulated trading. Include last update timestamps and explicit stale/disconnected indicators.

### Telegram

Optional notifications for proposals, paper fills, P&L, risk-limit proximity/halt, faults, and end-of-day summaries. If approval controls are built, restrict to configured authenticated user IDs, bind approvals to proposal IDs and expiry, prevent replay, and re-run every risk check at execution time. Telegram can never override the central risk engine. Keep bot tokens secret.

## 12. Implementation guidance

Preferred starting stack, subject to inspection of the existing environment:

- Backend: Python 3.12+ (or 3.11 on Apple Silicon), FastAPI, Pydantic, asyncio, pandas, NumPy.
- Research: scikit-learn as needed; compare every model to simple baselines. Use maintained indicator libraries or transparent in-house calculations.
- Storage: SQLite and SQLAlchemy initially, with migrations if warranted.
- Frontend: React, TypeScript, and a suitable charting library if there is no compatible existing frontend.
- Local operation on macOS; Docker is optional, not required.

Choose stable, maintained dependencies and explain material choices. Do not assume an LLM provider or incur paid API usage without documenting that dependency and configuration. Make core market data validation, deterministic strategies, backtesting, risk, and paper trading usable without an LLM.

## 13. Phased delivery

Do one phase at a time. At each phase end, summarize changed files, design decisions, commands/checks actually run and their results, known gaps, and the next phase. Never claim a check passed unless it was executed.

