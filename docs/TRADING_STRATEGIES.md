# Trading Strategies & Indicator Specifications

## 1. Overview
The platform features **8 deterministic quantitative intraday strategies** designed for Indian equities and derivatives (NSE/BSE). Every strategy operates strictly on completed candle bars, computes signals without look-ahead bias, and sizes positions such that the per-trade risk is bounded to $\le ₹250.00$.

---

## 2. The 8 Candidate Strategies

### 2.1 VWAP Continuation (`strategies/candidates/vwap_continuation.py`)
- **Premise:** Intraday institutional benchmark continuation. In a trending market, pullbacks to the Volume-Weighted Average Price (VWAP) offer high-probability continuation entries.
- **Entry Logic:**
  - **LONG:** Close $> \text{VWAP}$, current candle Low pulls back within $0.15\%$ of VWAP, candle closes green with Volume $> 1.2 \times \text{Volume SMA(20)}$.
  - **SHORT:** Close $< \text{VWAP}$, current candle High pulls back within $0.15\%$ of VWAP, candle closes red with Volume $> 1.2 \times \text{Volume SMA(20)}$.
- **Stop Loss:** Lowest low of previous 3 bars (Long) or Highest high of previous 3 bars (Short).
- **Target:** $1.5 \times \text{Risk Distance}$ (Minimum 1:1.5 Risk/Reward).
- **Timeframe:** 5-minute.

### 2.2 EMA Crossover (`strategies/candidates/ema_crossover.py`)
- **Premise:** Trend-following momentum using fast (9-period) and slow (21-period) exponential moving averages.
- **Entry Logic:**
  - **LONG:** EMA(9) crosses above EMA(21); Close $> \text{EMA}(9)$.
  - **SHORT:** EMA(9) crosses below EMA(21); Close $< \text{EMA}(9)$.
- **Stop Loss:** At the EMA(21) level minus $1 \times \text{ATR}(14)$.
- **Target:** $2.0 \times \text{Risk Distance}$.
- **Timeframe:** 15-minute.

### 2.3 RSI Momentum (`strategies/candidates/rsi_momentum.py`)
- **Premise:** 14-period Relative Strength Index trend continuation. Pullback into the 40–50 zone during uptrends or 50–60 zone during downtrends.
- **Entry Logic:**
  - **LONG:** RSI(14) was below 50, now crosses above 55; Price $> \text{EMA}(50)$.
  - **SHORT:** RSI(14) was above 50, now crosses below 45; Price $< \text{EMA}(50)$.
- **Stop Loss:** $1.5 \times \text{ATR}(14)$ from entry.
- **Target:** $2.0 \times \text{Risk Distance}$.
- **Timeframe:** 5-minute / 15-minute.

### 2.4 Opening Range Breakout (ORB) (`strategies/candidates/orb.py`)
- **Premise:** The price range established during the first 15 minutes of the Indian market session (09:15 to 09:30 IST) establishes the daily directional bias.
- **Entry Logic:**
  - High and Low of 09:15–09:30 candle are marked ($H_{\text{ORB}}$, $L_{\text{ORB}}$).
  - **LONG:** First candle closing $> H_{\text{ORB}}$ before 11:30 IST with volume expansion.
  - **SHORT:** First candle closing $< L_{\text{ORB}}$ before 11:30 IST with volume expansion.
- **Stop Loss:** Midpoint of Opening Range: $\frac{H_{\text{ORB}} + L_{\text{ORB}}}{2}$.
- **Target:** $1.5 \times \text{Range Size}$.
- **Timeframe:** 5-minute / 15-minute.

### 2.5 Supertrend Trend Following (`strategies/candidates/supertrend_trend.py`)
- **Premise:** Volatility-based trend trailing indicator utilizing ATR(10) with multiplier 3.0.
- **Entry Logic:**
  - **LONG:** Supertrend flips from Bearish (-1) to Bullish (+1); Close $> \text{EMA}(50)$.
  - **SHORT:** Supertrend flips from Bullish (+1) to Bearish (-1); Close $< \text{EMA}(50)$.
- **Stop Loss:** At the Supertrend band level.
- **Target:** $2.0 \times \text{Risk Distance}$.
- **Timeframe:** 5-minute / 15-minute.

### 2.6 Support & Resistance Breakout (`strategies/candidates/sr_breakout.py`)
- **Premise:** Horizontal consolidation breakout after minimum 4 touches across a 20-bar lookback window.
- **Entry Logic:**
  - **LONG:** Close $> \text{Resistance Level}$ with Volume $> 1.5 \times \text{Average Volume}$.
  - **SHORT:** Close $< \text{Support Level}$ with Volume $> 1.5 \times \text{Average Volume}$.
- **Stop Loss:** Previous swing low or consolidation support level.
- **Target:** $2.0 \times \text{Consolidation Range Height}$.
- **Timeframe:** 15-minute.

### 2.7 Volume Breakout (`strategies/candidates/volume_breakout.py`)
- **Premise:** Explosive volume accumulation indicating institutional participation.
- **Entry Logic:**
  - Volume $> 2.5 \times \text{Volume SMA(20)}$ and Candle Body $> 1.5 \times \text{ATR}(14)$.
  - **LONG:** Bullish closing candle.
  - **SHORT:** Bearish closing candle.
- **Stop Loss:** Low of the breakout bar (Long) or High of the breakout bar (Short).
- **Target:** $1.5 \times \text{Risk Distance}$.
- **Timeframe:** 5-minute.

### 2.8 Mean Reversion (`strategies/candidates/mean_reversion.py`)
- **Premise:** Price extended beyond 2 standard deviations of 20-period Bollinger Bands tends to revert towards the 20-period moving average.
- **Entry Logic:**
  - **LONG:** Low touches or pierces Lower Bollinger Band, followed by a reversal candle closing back inside the bands with RSI $< 35$.
  - **SHORT:** High touches or pierces Upper Bollinger Band, followed by a reversal candle closing back inside the bands with RSI $> 65$.
- **Stop Loss:** Extreme wick of the piercing candle $+ 0.5 \times \text{ATR}(14)$.
- **Target:** Middle Bollinger Band (SMA 20).
- **Timeframe:** 5-minute.

---

## 3. Position Sizing & Risk Ceiling

Every trade proposal generated by any strategy passes through `PositionSizer.calculate_quantity()`:
1. Calculates stop loss distance: $\Delta = |\text{Entry} - \text{Stop Loss}|$.
2. Calculates maximum shares allowable by risk ceiling:
   $$\text{Qty}_{\text{risk}} = \left\lfloor \frac{₹250.00}{\Delta} \right\rfloor$$
3. Calculates maximum shares allowable by capital constraint:
   $$\text{Qty}_{\text{capital}} = \left\lfloor \frac{\text{Available Capital}}{\text{Entry Price}} \right\rfloor$$
4. Takes $\min(\text{Qty}_{\text{risk}}, \text{Qty}_{\text{capital}})$.
5. For F&O contracts, rounds down to the nearest lot size multiple ($N \times \text{lot\_size}$). If $< 1 \text{ lot}$, proposal is rejected.
6. Guarantees that maximum potential loss never exceeds ₹250.00.
