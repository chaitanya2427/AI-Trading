import {
  AuditLogItem,
  PaperOrder,
  PaperPosition,
  ReconciliationReport,
  SystemStatus,
  TradePlanResponse,
  TradeProposal,
} from '../types';

const API_BASE = '/api/v1';

export const api = {
  async getStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error('Failed to fetch status');
    return res.json();
  },

  async getProposals(status?: string): Promise<TradeProposal[]> {
    const url = status
      ? `${API_BASE}/execution/proposals?status=${status}`
      : `${API_BASE}/execution/proposals`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch proposals');
    const data = await res.json();
    return data.proposals || [];
  },

  async scanStrategies(symbols?: string[]) {
    const res = await fetch(`${API_BASE}/strategies/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols, generate_demo_if_empty: true }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to scan strategies');
    return data;
  },

  async approveProposal(proposalId: string, operator: string = 'WEB_OPERATOR') {
    const res = await fetch(`${API_BASE}/execution/proposals/${proposalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to approve proposal');
    return data;
  },

  async rejectProposal(proposalId: string, reason: string, operator: string = 'WEB_OPERATOR') {
    const res = await fetch(`${API_BASE}/execution/proposals/${proposalId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator, reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to reject proposal');
    return data;
  },

  async getPositions(status: string = 'OPEN'): Promise<PaperPosition[]> {
    const res = await fetch(`${API_BASE}/execution/positions?status=${status}`);
    if (!res.ok) throw new Error('Failed to fetch positions');
    const data = await res.json();
    return data.positions || [];
  },

  async squareOffPosition(positionId: string, reason: string = 'MANUAL_WEB_SQUARE_OFF') {
    const res = await fetch(`${API_BASE}/execution/positions/${positionId}/square-off`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to square off position');
    return data;
  },

  async squareOffAll() {
    const res = await fetch(`${API_BASE}/execution/square-off-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to square off all positions');
    return data;
  },

  async getOrders(limit: number = 20): Promise<PaperOrder[]> {
    const res = await fetch(`${API_BASE}/execution/orders?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch orders');
    const data = await res.json();
    return data.orders || [];
  },

  async triggerKillSwitch(reason: string) {
    const res = await fetch(`${API_BASE}/risk/kill-switch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to activate kill switch');
    return data;
  },

  async resetKillSwitch(reason: string) {
    const res = await fetch(`${API_BASE}/risk/kill-switch/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to reset kill switch');
    return data;
  },

  async getAuditLogs(limit: number = 30): Promise<AuditLogItem[]> {
    const res = await fetch(`${API_BASE}/audit/logs?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    return res.json();
  },

  async getReconciliation(): Promise<ReconciliationReport> {
    const res = await fetch(`${API_BASE}/execution/reconciliation`);
    if (!res.ok) throw new Error('Failed to fetch reconciliation');
    return res.json();
  },

  async updateMarketPrice(symbol: string, price: number) {
    const res = await fetch(`${API_BASE}/execution/market-update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, price }),
    });
    return res.json();
  },

  async analyzeStock(request: {
    stock_symbol: string;
    current_price?: number | null;
    exchange?: string;
    timeframe?: string;
    trade_style?: string;
  }): Promise<TradePlanResponse> {
    const res = await fetch(`${API_BASE}/advisor/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to analyze stock');
    return data;
  },
};

