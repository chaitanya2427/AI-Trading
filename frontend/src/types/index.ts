export interface SystemStatus {
  environment: string;
  execution_mode: string;
  live_trading_enabled: boolean;
  current_time_ist: string;
  session_phase: string;
  is_trading_day: boolean;
  is_market_open: boolean;
  is_intraday_entry_allowed: boolean;
  risk_status: string;
  kill_switch_active: boolean;
  capital_summary: {
    starting_capital_inr: number;
    daily_loss_limit_inr: number;
    realized_pnl_inr: number;
    unrealized_pnl_inr: number;
    total_charges_inr: number;
    net_pnl_inr: number;
    loss_limit_headroom_inr: number;
  };
}

export interface TradeProposal {
  proposal_id: string;
  created_at: string;
  symbol: string;
  exchange: string;
  segment: string;
  direction: 'LONG' | 'SHORT';
  strategy_name: string;
  entry_price: number;
  stop_loss: number;
  target: number;
  quantity: number;
  estimated_risk_inr: number;
  estimated_reward_inr: number;
  estimated_costs_inr: number;
  risk_decision: 'PENDING' | 'APPROVED' | 'REJECTED';
  risk_reason?: string;
  human_decision: 'PENDING' | 'APPROVED' | 'REJECTED';
  human_reason?: string;
  execution_mode: string;
}

export interface PaperPosition {
  position_id: string;
  order_id?: string;
  proposal_id?: string;
  symbol: string;
  exchange: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  entry_price: number;
  current_price: number;
  stop_loss: number;
  target: number;
  entry_time: string;
  unrealized_pnl: number;
  realized_pnl: number;
  total_charges: number;
  status: 'OPEN' | 'CLOSED';
  exit_price?: number;
  exit_time?: string;
  exit_reason?: string;
  execution_mode: string;
  provenance: string;
}

export interface PaperOrder {
  order_id: string;
  proposal_id?: string;
  created_at: string;
  symbol: string;
  exchange: string;
  direction: 'LONG' | 'SHORT';
  quantity: number;
  order_type: string;
  reference_price: number;
  limit_price?: number;
  status: 'NEW' | 'SUBMITTED' | 'FILLED' | 'REJECTED' | 'CANCELLED';
  filled_price?: number;
  filled_at?: string;
  slippage_inr: number;
  charges_inr: number;
  reject_reason?: string;
  execution_mode: string;
  provenance: string;
}

export interface AuditLogItem {
  id: number;
  timestamp: string;
  event_type: string;
  actor: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  details?: Record<string, any>;
}

export interface ReconciliationReport {
  timestamp: string;
  is_clean: boolean;
  discrepancy_count: number;
  discrepancies: string[];
  stats: {
    in_memory_open_positions: number;
    db_open_positions: number;
    portfolio_net_pnl_inr: number;
    risk_engine_net_pnl_inr: number;
    realized_pnl_inr: number;
    unrealized_pnl_inr: number;
    total_charges_inr: number;
  };
  execution_mode: string;
  provenance: string;
}



// ------------------------------------------------------------------------------
// Live Trade Advisor Types
// ------------------------------------------------------------------------------

export interface StrategyResultItem {
  strategy_name: string;
  signal: 'BUY' | 'SELL' | 'HOLD' | 'NO_SIGNAL';
  entry_price_or_range?: string | null;
  stop_loss?: number | null;
  exit_target_or_rule?: string | null;
  risk_reward_ratio?: number | null;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  data_timestamp: string;
}

export interface StrategySummary {
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  non_signaling_count: number;
  total_strategies: number;
  agreement_summary: string;
}

export interface MarketDataMeta {
  provider: string;
  price?: number | null;
  price_type: 'LIVE' | 'DELAYED' | 'USER_PROVIDED' | 'UNAVAILABLE' | 'SIMULATED';
  timestamp: string;
  freshness: 'FRESH' | 'STALE' | 'UNKNOWN';
}

export interface TradePlanLevels {
  entry_range?: string | null;
  stop_loss?: number | null;
  exit_target?: number | null;
  exit_rule?: string | null;
  risk_reward_ratio?: number | null;
}

export interface TradePlanResponse {
  decision: 'BUY' | 'SELL' | 'HOLD' | 'NO TRADE';
  instrument: {
    symbol: string;
    exchange: string;
    instrument_key: string;
    segment: string;
  };
  market_data: MarketDataMeta;
  plan: TradePlanLevels;
  strategy_summary: StrategySummary;
  strategy_results: StrategyResultItem[];
  reasoning: string;
  limitations: string;
  safety_notice: string;
}

export interface StockAnalysisRequest {
  stock_symbol: string;
  current_price?: number | null;
  exchange?: string;
  timeframe?: string;
  trade_style?: string;
}
