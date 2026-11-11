# Broker & Market Data API Integration Specification

## 1. Overview
The platform connects to **Upstox** via its official, current API endpoints while maintaining an isolated, mathematically consistent synthetic test environment for offline research and simulation.

---

## 2. Upstox API Specification & Protocols

### 2.1 Upstox WebSocket Feed V3 Protocol
- **Architecture:** WebSocket Feed V2 is deprecated. The system utilizes Upstox WebSocket Feed V3.
- **Serialization:** Binary Protocol Buffers (Google Protobuf). Frames are decoded using native compiled Python bindings (`backend/app/adapters/proto/MarketDataFeed_pb2.py`).
- **Connection Handshake:**
  - Authenticated via HTTP GET request to `https://api.upstox.com/v3/feed/market-data-feed/authorize`.
  - Upstox returns an authorized WebSocket URI with temporary connection token.
  - Client establishes secure WebSocket connection with binary payload handling.
- **Modes Supported:**
  - `LTPC`: Last Traded Price & Close (minimal bandwidth).
  - `FULL`: Complete 5-depth order book, open interest, VWAP, and volume.

### 2.2 Upstox REST Endpoints
- **Base URL:** `https://api.upstox.com/v2`
- **Rate Limit:** 50 requests per second for quote endpoints.
- **Key Routes:**
  - `GET /v2/market-quote/quotes`: Snapshot quotes for equity and F&O.
  - `GET /v2/market-quote/ohlc`: Intraday completed candle bars.
  - `GET /v2/option/contract`: Real-time option chains with Greeks, strikes, and OI.
  - `GET /v2/user/profile`: Profile and segment authorization check.
- **Token Lifecycle:** Upstox access tokens expire daily at 03:30 AM IST. Daily re-authentication is handled cleanly via OAuth2 redirect flow.

---

## 3. Synthetic Market Data Feed (`backend/app/adapters/synthetic_feed.py`)

For deterministic offline backtesting and test environments where broker credentials or market hours are inactive:
- **Mathematical Foundation:** Merton Jump Diffusion model:
  $$dS_t = \mu S_t dt + \sigma S_t dW_t + J_t S_t dN_t$$
  where $W_t$ is standard Brownian motion, $N_t$ is a Poisson jump process ($\lambda_j$), and $J_t$ is log-normal jump size distribution.
- **Properties:**
  - Enforces realistic candle invariants: $\text{Low} \le \min(\text{Open}, \text{Close}) \le \max(\text{Open}, \text{Close}) \le \text{High}$.
  - Simulates 5-depth Level-2 order books with realistic spreads and depth.
  - Explicit provenance tagging: `source: "SYNTHETIC_FIXTURE"`, `provenance: "SIMULATED"`.
  - Zero synthetic data is ever represented as live broker data.

---

## 4. Reconnection & Resilience Protocols

1. **Exponential Backoff:** If the WebSocket connection drops, reconnection is attempted at intervals: 1s, 2s, 4s, 8s, up to 30s maximum.
2. **Heartbeat Monitoring:** Pings sent every 30s. Missing 2 consecutive pongs flags the connection dead and initiates reconnection.
3. **Fail-Closed Fallback:** While disconnected, quote age exceeds 5.0 seconds; the Central Risk Engine automatically refuses all new proposals until live data resumes.
