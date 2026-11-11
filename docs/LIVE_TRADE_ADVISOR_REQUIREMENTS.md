# Live Trade Advisor Requirements

## Purpose

Build an advisory feature for Indian stock market trading. A user enters a stock name or symbol and, optionally, a current price. The system evaluates every enabled trading strategy against current market data and presents a clear, evidence-based trade plan: whether to consider a trade, a potential entry, an exit plan, and a stop loss.

The system must not promise maximum profit or guaranteed returns. It provides analysis to support the user's decision and must not place real-money trades.

## User Story

As a trader, I want to enter an Indian stock symbol and optionally its current price, have the system evaluate all enabled strategies using current market data, and receive a clear potential entry, exit, and stop-loss plan so I can make an informed decision.

## Scope

### Included

- Indian exchange-listed stocks supported by the configured market-data integration.
- User-entered stock name or symbol and optional user-entered price.
- Instrument lookup and exchange identification.
- Evaluation of every enabled strategy registered in the project.
- Strategy-by-strategy results and an overall summary of agreement or disagreement.
- Suggested entry range, stop loss, exit target or exit rule, and risk/reward estimate when supported by strategy results.
- Market-data provider, price type, timestamp, and freshness status.
- A clear `NO TRADE` decision when data or evidence is insufficient.

### Excluded

- Guaranteed profit claims or claims of achieving maximum profit.
- Automatic placement of real-money orders.
- Representing a user-entered price as a verified live quote.
- Presenting synthetic or simulated prices as live market data.
- Generating a trade plan from stale, missing, or invalid data.

## User Inputs

```xml
<inputs>
  <stock_symbol required="true" type="string">
    Indian stock symbol or supported instrument name, for example RELIANCE or TCS.
  </stock_symbol>
  <current_price required="false" type="decimal">
    Optional price entered by the user. Label it USER_PROVIDED; do not represent it as a live quote.
  </current_price>
  <exchange required="false" type="enum">
    NSE or BSE. If omitted, resolve the instrument and display the selected exchange.
  </exchange>
  <timeframe required="false" type="string">
    Strategy timeframe. Use the configured project default when omitted.
  </timeframe>
  <trade_style required="false" type="enum">
    Intraday or delivery, if supported by the project's strategies.
  </trade_style>
</inputs>
```

## Market Data Requirements

```xml
<market_data>
  <requested_provider>TradingView</requested_provider>
  <requirements>
    <item>Use a supported and permitted TradingView data integration.</item>
    <item>Resolve the entered symbol to the correct Indian exchange instrument.</item>
    <item>Retrieve the latest supported quote and the candle history needed by strategies.</item>
    <item>Record provider, exchange, instrument, timestamp, and data mode.</item>
    <item>Label prices as LIVE, DELAYED, USER_PROVIDED, or UNAVAILABLE.</item>
    <item>Validate data freshness before generating trade guidance.</item>
    <item>Never silently substitute synthetic data for live data.</item>
  </requirements>
  <failure_behavior>
    If live data is missing, stale, invalid, or unavailable, return NO TRADE and explain why.
    Historical or simulated data may be used only in an explicitly labeled research or backtesting mode.
  </failure_behavior>
</market_data>
```

Before implementation, verify TradingView's supported access methods and data-use terms. Do not assume unofficial scraping is permitted or reliable. If no supported TradingView integration is available, explain the limitation and ask the user to choose an available, supported market-data provider. Do not silently change providers.

## Strategy Evaluation

```xml
<strategy_evaluation>
  <coverage>Evaluate every enabled strategy registered in the project.</coverage>
  <consistency>
    Strategies in one analysis should use the same resolved instrument, timeframe, and market-data snapshot where possible.
  </consistency>
  <per_strategy_result>
    <field name="strategy_name" />
    <field name="signal">BUY, SELL, HOLD, or NO_SIGNAL</field>
    <field name="entry_price_or_range" />
    <field name="stop_loss" />
    <field name="exit_target_or_rule" />
    <field name="risk_reward_ratio" />
    <field name="supporting_evidence" />
    <field name="contradicting_evidence" />
    <field name="data_timestamp" />
  </per_strategy_result>
  <aggregation>
    Show bullish, bearish, neutral, and non-signaling strategy counts.
    Summarize agreement and disagreement without hiding individual strategy results.
    Do not create a recommendation merely to force a consensus.
  </aggregation>
</strategy_evaluation>
```

## Trade Plan Output

```xml
<trade_plan>
  <decision>BUY, SELL, HOLD, or NO TRADE</decision>
  <instrument>
    <symbol />
    <exchange />
    <instrument_key />
  </instrument>
  <market_data>
    <provider />
    <price />
    <price_type>LIVE, DELAYED, USER_PROVIDED, or UNAVAILABLE</price_type>
    <timestamp />
    <freshness>FRESH, STALE, or UNKNOWN</freshness>
  </market_data>
  <plan>
    <entry_range />
    <stop_loss />
    <exit_target />
    <exit_rule />
    <risk_reward_ratio />
  </plan>
  <strategy_summary>
    <bullish_count />
    <bearish_count />
    <neutral_count />
    <agreement_summary />
  </strategy_summary>
  <reasoning>
    Explain the main evidence, risks, and strategy disagreements in plain language.
  </reasoning>
  <limitations>
    State when results are uncertain or data is incomplete. Do not promise returns.
  </limitations>
</trade_plan>
```

If evidence does not support a reliable plan, return `NO TRADE`, leave unsupported price levels unset, and explain what is missing. Never invent entry, stop-loss, or target prices.

## Safety and Trading Controls

```xml
<safety>
  <real_money_execution enabled="false" />
  <human_approval_required>true</human_approval_required>
  <existing_risk_engine_required>true</existing_risk_engine_required>
  <synthetic_data_may_be_labeled_live>false</synthetic_data_may_be_labeled_live>
  <guaranteed_profit_claims>false</guaranteed_profit_claims>
</safety>
```

The feature must preserve existing paper-trading defaults, risk controls, and human approval. A displayed plan is informational and must not place an order or bypass a risk gate.

## User Interface Requirements

Provide a stock-analysis form with:

- Stock symbol/name input.
- Optional user-entered current price.
- Exchange selection or resolved exchange display.
- Analyze button.
- Live-data connection and freshness indicator.

Display:

- Overall decision (`BUY`, `SELL`, `HOLD`, or `NO TRADE`).
- Entry range, stop loss, and exit plan when supported by the analysis.
- Risk/reward estimate when calculable.
- Individual strategy signals, evidence, and disagreements.
- Data provider, price type, and timestamp.
- Clear explanations for errors, stale data, missing data, and `NO TRADE` results.

## Acceptance Criteria

1. A user can enter a supported Indian stock symbol and request analysis.
2. The system resolves the symbol to a specific exchange instrument or explains that it could not.
3. Every enabled strategy is evaluated and its individual result is available to the user.
4. The overall summary shows agreement and conflicts without concealing strategy results.
5. Entry, stop loss, and exit guidance are shown only when supported by strategy output.
6. User-entered prices are labeled `USER_PROVIDED` and are never described as verified live quotes.
7. Live prices show their provider and timestamp.
8. Stale, missing, or invalid live data results in `NO TRADE`.
9. Synthetic data is never presented as live data.
10. The feature cannot place real-money orders or bypass existing risk controls or human approval.
11. The interface states that results are uncertain and profits are not guaranteed.

## Implementation Instructions for an AI Coding Agent

```xml
<implementation_instructions>
  <instruction>Inspect the repository and preserve its architecture and existing safety controls.</instruction>
  <instruction>Reuse the instrument master, strategy registry, market-data validation, and proposal workflow where suitable.</instruction>
  <instruction>Verify TradingView's supported integration options and data-use constraints before implementing its adapter.</instruction>
  <instruction>If TradingView access is unavailable through a supported integration, report the limitation and request provider selection; do not silently switch providers.</instruction>
  <instruction>Keep provider-specific code behind a market-data adapter so an approved provider can be added later.</instruction>
  <instruction>Load credentials from local configuration and never request credentials in chat or commit secrets.</instruction>
  <instruction>Keep the feature advisory and paper-trading-only.</instruction>
  <instruction>Document setup, provider limitations, data labels, and how users should interpret recommendations.</instruction>
</implementation_instructions>
```

