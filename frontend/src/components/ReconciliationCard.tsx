import React from 'react';
import { CheckCircle2, AlertTriangle, Database, RefreshCw } from 'lucide-react';
import { ReconciliationReport } from '../types';

interface ReconciliationCardProps {
  reconciliation: ReconciliationReport | null;
  onRunAudit: () => void;
  isLoading: boolean;
}

export const ReconciliationCard: React.FC<ReconciliationCardProps> = ({
  reconciliation,
  onRunAudit,
  isLoading,
}) => {
  const isClean = reconciliation?.is_clean ?? true;

  return (
    <div className="apple-card-3d relative overflow-hidden backdrop-blur-2xl bg-black/60 border border-white/[0.08] shadow-apple-3d p-6 rounded-3xl h-full flex flex-col justify-between">
      {/* Top specular highlight */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-2xl bg-white/[0.05] border border-white/[0.1] shadow-inner flex items-center justify-center">
              <Database className="w-4 h-4 text-[#64D2FF]" />
            </div>
            <div>
              <h3 className="text-base font-semibold tracking-tight text-white/95">
                Data Provenance
              </h3>
              <p className="text-xs text-[#86868B]">In-memory & WAL sync</p>
            </div>
          </div>
          <button
            onClick={onRunAudit}
            disabled={isLoading}
            className="apple-btn-3d py-1.5 px-3 rounded-xl text-xs font-semibold text-white/80 hover:text-white flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{isLoading ? 'Auditing...' : 'Run Audit'}</span>
          </button>
        </div>

        {/* Sync Status Banner */}
        <div className="mb-5 p-3 rounded-2xl bg-white/[0.03] border border-white/[0.08] backdrop-blur-md">
          {isClean ? (
            <div className="flex items-center gap-2.5 text-xs text-[#30D158] font-medium">
              <div className="w-5 h-5 rounded-full bg-[#30D158]/15 border border-[#30D158]/30 flex items-center justify-center shadow-apple-glow-green">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#30D158]" />
              </div>
              <span>Memory, SQLite WAL & Risk Engine 100% reconciled.</span>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 text-xs text-[#FF453A] font-medium">
              <div className="w-5 h-5 rounded-full bg-[#FF453A]/15 border border-[#FF453A]/30 flex items-center justify-center shadow-apple-glow-red">
                <AlertTriangle className="w-3.5 h-3.5 text-[#FF453A]" />
              </div>
              <span>Discrepancies detected ({reconciliation?.discrepancy_count})</span>
            </div>
          )}
        </div>

        {/* Metric stats grid */}
        <div className="grid grid-cols-2 gap-2.5 text-xs font-mono">
          <div className="p-3 rounded-2xl bg-black/40 border border-white/[0.06] shadow-inner">
            <span className="text-[#86868B] block text-[10px] uppercase">Memory Positions</span>
            <span className="text-white text-base font-bold mt-0.5 block">
              {reconciliation?.stats.in_memory_open_positions ?? 0}
            </span>
          </div>
          <div className="p-3 rounded-2xl bg-black/40 border border-white/[0.06] shadow-inner">
            <span className="text-[#86868B] block text-[10px] uppercase">DB Positions</span>
            <span className="text-white text-base font-bold mt-0.5 block">
              {reconciliation?.stats.db_open_positions ?? 0}
            </span>
          </div>
          <div className="p-3 rounded-2xl bg-black/40 border border-white/[0.06] shadow-inner">
            <span className="text-[#86868B] block text-[10px] uppercase">Portfolio Net P&L</span>
            <span className="text-white text-base font-bold mt-0.5 block">
              ₹{(reconciliation?.stats.portfolio_net_pnl_inr ?? 0).toFixed(2)}
            </span>
          </div>
          <div className="p-3 rounded-2xl bg-black/40 border border-white/[0.06] shadow-inner">
            <span className="text-[#86868B] block text-[10px] uppercase">Risk Engine P&L</span>
            <span className="text-white text-base font-bold mt-0.5 block">
              ₹{(reconciliation?.stats.risk_engine_net_pnl_inr ?? 0).toFixed(2)}
            </span>
          </div>
        </div>

        {reconciliation && reconciliation.discrepancies.length > 0 && (
          <div className="mt-4 p-3 bg-[#FF453A]/10 border border-[#FF453A]/30 rounded-2xl text-xs text-[#FF453A]">
            <div className="font-semibold mb-1">Discrepancy Details:</div>
            <ul className="list-disc list-inside space-y-1 text-[11px] text-white/80">
              {reconciliation.discrepancies.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
