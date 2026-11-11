import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { RiskCapitalBar } from './components/RiskCapitalBar';
import { LiveTradeAdvisor } from './components/LiveTradeAdvisor';
import { ProposalDeck } from './components/ProposalDeck';
import { PositionsTable } from './components/PositionsTable';
import { OrdersHistory } from './components/OrdersHistory';
import { ReconciliationCard } from './components/ReconciliationCard';
import { AuditLogsModal } from './components/AuditLogsModal';
import { Sparkles, ShieldCheck } from 'lucide-react';
import { api } from './services/api';
import {
  AuditLogItem,
  PaperOrder,
  PaperPosition,
  ReconciliationReport,
  SystemStatus,
  TradeProposal,
} from './types';

export const App: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [proposals, setProposals] = useState<TradeProposal[]>([]);
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [reconciliation, setReconciliation] = useState<ReconciliationReport | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadData = useCallback(async () => {
    try {
      const [st, prop, pos, ord, rec] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getProposals().catch(() => []),
        api.getPositions().catch(() => []),
        api.getOrders().catch(() => []),
        api.getReconciliation().catch(() => null),
      ]);
      if (st) setStatus(st);
      setProposals(prop);
      setPositions(pos);
      setOrders(ord);
      if (rec) setReconciliation(rec);
    } catch (e) {
      console.error('Error fetching dashboard data:', e);
    }
  }, []);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await loadData();
    setIsRefreshing(false);
    showToast('Dashboard synchronized with live telemetry.');
  };

  const handleOpenAudit = async () => {
    setShowAuditModal(true);
    try {
      const logs = await api.getAuditLogs(50);
      setAuditLogs(logs);
    } catch (e) {
      console.error('Failed to load audit logs:', e);
    }
  };

  const handleApproveProposal = async (proposalId: string) => {
    try {
      const res = await api.approveProposal(proposalId);
      if (res.status === 'EXECUTED') {
        showToast(`Trade Executed: Order ${res.order_id} filled @ ₹${res.filled_price}`);
      } else {
        showToast(`Execution Blocked: ${res.risk_reason || res.reason || 'Risk Gate Violation'}`);
      }
      await loadData();
    } catch (e: any) {
      showToast(`Error approving: ${e.message}`);
    }
  };

  const handleRejectProposal = async (proposalId: string, reason: string) => {
    try {
      await api.rejectProposal(proposalId, reason);
      showToast('Proposal rejected and archived.');
      await loadData();
    } catch (e: any) {
      showToast(`Error rejecting: ${e.message}`);
    }
  };

  const handleSquareOffPosition = async (positionId: string) => {
    try {
      await api.squareOffPosition(positionId);
      showToast('Position squared off.');
      await loadData();
    } catch (e: any) {
      showToast(`Error squaring off: ${e.message}`);
    }
  };

  const handleSquareOffAll = async () => {
    try {
      const res = await api.squareOffAll();
      showToast(`Squared off all ${res.count_squared_off} active positions.`);
      await loadData();
    } catch (e: any) {
      showToast(`Error squaring off all: ${e.message}`);
    }
  };

  const handleTriggerKillSwitch = async (reason: string) => {
    try {
      await api.triggerKillSwitch(reason);
      showToast('Emergency Kill Switch Engaged. Trading Halted.');
      await loadData();
    } catch (e: any) {
      showToast(`Error triggering kill switch: ${e.message}`);
    }
  };

  const handleResetKillSwitch = async (reason: string) => {
    try {
      await api.resetKillSwitch(reason);
      showToast('Kill Switch Reset. Trading Resumed.');
      await loadData();
    } catch (e: any) {
      showToast(`Error resetting kill switch: ${e.message}`);
    }
  };

  const handleRunReconciliation = async () => {
    try {
      const report = await api.getReconciliation();
      setReconciliation(report);
      showToast(report.is_clean ? 'Reconciliation clean!' : `${report.discrepancy_count} discrepancies found!`);
    } catch (e: any) {
      showToast(`Reconciliation error: ${e.message}`);
    }
  };

  const handleScanStrategies = async () => {
    try {
      setIsRefreshing(true);
      const res = await api.scanStrategies();
      showToast(`Strategy Scan Complete: ${res.proposals_generated} trade proposal(s) generated!`);
      await loadData();
    } catch (e: any) {
      showToast(`Scan error: ${e.message}`);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    // Auto refresh every 3 seconds for active monitoring
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [loadData]);

  return (
    <div className="min-h-screen flex flex-col bg-[#000000] text-white selection:bg-[#0A84FF]/30 selection:text-white font-sans relative overflow-x-hidden apple-spatial-bg">
      {/* 3D Ambient Spotlights */}
      <div className="pointer-events-none fixed top-0 left-1/4 -translate-x-1/2 w-[600px] h-[600px] bg-[#0A84FF]/[0.07] rounded-full blur-[140px] -z-10" />
      <div className="pointer-events-none fixed top-1/3 right-10 w-[500px] h-[500px] bg-[#BF5AF2]/[0.05] rounded-full blur-[150px] -z-10" />
      <div className="pointer-events-none fixed bottom-10 left-10 w-[550px] h-[550px] bg-[#30D158]/[0.04] rounded-full blur-[160px] -z-10" />

      {/* Navigation Header */}
      <Header
        status={status}
        onRefresh={handleManualRefresh}
        onOpenAudit={handleOpenAudit}
        isRefreshing={isRefreshing}
      />

      {/* Floating Dynamic Island Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 bg-[#1C1C1E]/90 backdrop-blur-2xl border border-white/[0.15] shadow-apple-3d text-white text-xs px-5 py-3 rounded-full flex items-center gap-2.5 animate-fade-in font-medium max-w-lg">
          <div className="w-5 h-5 rounded-full bg-[#0A84FF]/20 border border-[#0A84FF]/40 flex items-center justify-center shrink-0">
            <Sparkles className="w-3 h-3 text-[#64D2FF]" />
          </div>
          <span className="truncate">{toastMessage}</span>
        </div>
      )}

      {/* Main Content Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Risk & Capital Bar */}
        <RiskCapitalBar
          status={status}
          onTriggerKillSwitch={handleTriggerKillSwitch}
          onResetKillSwitch={handleResetKillSwitch}
        />

        {/* Live Trade Advisor */}
        <LiveTradeAdvisor />

        {/* Proposals Awaiting Approval */}
        <ProposalDeck
          proposals={proposals}
          onApprove={handleApproveProposal}
          onReject={handleRejectProposal}
          onScanStrategies={handleScanStrategies}
          isLoading={isRefreshing}
        />

        {/* Active Positions */}
        <PositionsTable
          positions={positions}
          onSquareOff={handleSquareOffPosition}
          onSquareOffAll={handleSquareOffAll}
          isLoading={isRefreshing}
        />

        {/* Orders & Reconciliation Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <OrdersHistory orders={orders} />
          </div>
          <div>
            <ReconciliationCard
              reconciliation={reconciliation}
              onRunAudit={handleRunReconciliation}
              isLoading={isRefreshing}
            />
          </div>
        </div>
      </main>

      {/* System Audit Modal */}
      <AuditLogsModal
        isOpen={showAuditModal}
        onClose={() => setShowAuditModal(false)}
        logs={auditLogs}
        isLoading={false}
      />

      {/* Apple Minimalist Footer */}
      <footer className="mt-12 border-t border-white/[0.08] bg-black/40 backdrop-blur-xl py-6 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#86868B]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#30D158]" />
            <span className="text-white/80 font-medium">Autonomous Intelligence System</span>
            <span>•</span>
            <span>Deterministic Hard Ceiling ₹250.00</span>
          </div>
          <div className="flex items-center gap-4 text-[11px] font-mono">
            <span>EXECUTION: PAPER</span>
            <span>DATA: UPSTOX FEED</span>
            <span>CUT-OFF: 15:15 IST</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
