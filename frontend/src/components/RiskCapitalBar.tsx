import React, { useState } from 'react';
import { AlertOctagon, TrendingDown, TrendingUp, RefreshCw, Shield, Zap } from 'lucide-react';
import { SystemStatus } from '../types';

interface RiskCapitalBarProps {
  status: SystemStatus | null;
  onTriggerKillSwitch: (reason: string) => Promise<void>;
  onResetKillSwitch: (reason: string) => Promise<void>;
}

export const RiskCapitalBar: React.FC<RiskCapitalBarProps> = ({
  status,
  onTriggerKillSwitch,
  onResetKillSwitch,
}) => {
  const [showKillModal, setShowKillModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const cap = status?.capital_summary;
  const startingCapital = cap?.starting_capital_inr ?? 25000;
  const dailyLossLimit = cap?.daily_loss_limit_inr ?? 250;
  const realizedPnl = cap?.realized_pnl_inr ?? 0;
  const unrealizedPnl = cap?.unrealized_pnl_inr ?? 0;
  const totalCharges = cap?.total_charges_inr ?? 0;
  const netPnl = cap?.net_pnl_inr ?? 0;
  const headroom = cap?.loss_limit_headroom_inr ?? 250;

  // Percentage of ₹250 loss ceiling consumed
  const lossConsumedPct = netPnl < 0 ? Math.min(100, Math.max(0, (Math.abs(netPnl) / dailyLossLimit) * 100)) : 0;

  let progressGradient = 'from-apple-green via-emerald-400 to-apple-green';
  let glowColor = 'shadow-apple-glow-green';

  if (lossConsumedPct > 75) {
    progressGradient = 'from-apple-red via-rose-500 to-apple-red animate-pulse';
    glowColor = 'shadow-apple-glow-red';
  } else if (lossConsumedPct > 40) {
    progressGradient = 'from-apple-orange via-amber-400 to-apple-orange';
    glowColor = 'shadow-[0_0_25px_rgba(255,159,10,0.4)]';
  }

  const handleKillSubmit = async () => {
    if (!reason.trim()) return;
    setIsSubmitting(true);
    try {
      await onTriggerKillSwitch(reason);
      setShowKillModal(false);
      setReason('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetSubmit = async () => {
    if (!reason.trim()) return;
    setIsSubmitting(true);
    try {
      await onResetKillSwitch(reason);
      setShowResetModal(false);
      setReason('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="apple-glass rounded-3xl p-6 shadow-apple-3d relative overflow-hidden">
      {/* Subtle ambient spotlight behind card */}
      <div className="absolute top-0 right-1/4 w-96 h-96 bg-apple-blue/10 rounded-full blur-3xl pointer-events-none -z-10" />

      {/* Grid of 3D Metric Cylinders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3.5 items-center">
        {/* Starting Capital */}
        <div className="apple-card-3d p-4 rounded-2xl relative group">
          <div className="text-[11px] font-semibold text-apple-subtext uppercase tracking-wider flex items-center justify-between">
            <span>Capital</span>
            <Shield className="w-3.5 h-3.5 text-apple-blue opacity-70" />
          </div>
          <div className="text-xl font-mono font-extrabold text-white mt-1 tracking-tight">
            ₹{startingCapital.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[10px] text-apple-subtext mt-0.5">Strict ceiling &lt; ₹25,000</div>
        </div>

        {/* Realized P&L */}
        <div className="apple-card-3d p-4 rounded-2xl">
          <div className="text-[11px] font-semibold text-apple-subtext uppercase tracking-wider flex items-center justify-between">
            <span>Realized P&L</span>
            {realizedPnl >= 0 ? (
              <TrendingUp className="w-3.5 h-3.5 text-apple-green" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5 text-apple-red" />
            )}
          </div>
          <div
            className={`text-xl font-mono font-extrabold mt-1 tracking-tight ${
              realizedPnl >= 0 ? 'text-apple-green' : 'text-apple-red'
            }`}
          >
            {realizedPnl >= 0 ? `+₹${realizedPnl.toFixed(2)}` : `-₹${Math.abs(realizedPnl).toFixed(2)}`}
          </div>
          <div className="text-[10px] text-apple-subtext mt-0.5">Settled trades</div>
        </div>

        {/* Unrealized MTM */}
        <div className="apple-card-3d p-4 rounded-2xl">
          <div className="text-[11px] font-semibold text-apple-subtext uppercase tracking-wider flex items-center justify-between">
            <span>Unrealized MTM</span>
            <Zap className="w-3.5 h-3.5 text-apple-blue opacity-70" />
          </div>
          <div
            className={`text-xl font-mono font-extrabold mt-1 tracking-tight ${
              unrealizedPnl >= 0 ? 'text-apple-green' : 'text-apple-red'
            }`}
          >
            {unrealizedPnl >= 0 ? `+₹${unrealizedPnl.toFixed(2)}` : `-₹${Math.abs(unrealizedPnl).toFixed(2)}`}
          </div>
          <div className="text-[10px] text-apple-subtext mt-0.5">Active positions</div>
        </div>

        {/* Statutory Costs */}
        <div className="apple-card-3d p-4 rounded-2xl">
          <div className="text-[11px] font-semibold text-apple-subtext uppercase tracking-wider">
            Statutory Costs
          </div>
          <div className="text-xl font-mono font-extrabold text-apple-orange mt-1 tracking-tight">
            ₹{totalCharges.toFixed(2)}
          </div>
          <div className="text-[10px] text-apple-subtext mt-0.5">Brokerage, STT, GST</div>
        </div>

        {/* Net Session P&L */}
        <div className="apple-card-3d p-4 rounded-2xl border-white/20 bg-gradient-to-b from-white/[0.08] to-white/[0.02]">
          <div className="text-[11px] font-semibold text-apple-subtext uppercase tracking-wider">
            Net Session P&L
          </div>
          <div
            className={`text-2xl font-mono font-black mt-1 tracking-tight ${
              netPnl >= 0 ? 'text-apple-green' : 'text-apple-red'
            }`}
          >
            {netPnl >= 0 ? `+₹${netPnl.toFixed(2)}` : `-₹${Math.abs(netPnl).toFixed(2)}`}
          </div>
          <div className="text-[10px] text-apple-subtext mt-0.5">Net of all charges</div>
        </div>

        {/* Kill Switch Tactile Button */}
        <div className="flex flex-col gap-2">
          {status?.kill_switch_active ? (
            <button
              onClick={() => setShowResetModal(true)}
              className="w-full py-3.5 px-4 rounded-2xl text-xs font-bold bg-gradient-to-b from-apple-orange/30 to-apple-orange/10 hover:from-apple-orange/40 hover:to-apple-orange/20 text-apple-orange border border-apple-orange/40 shadow-lg flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5"
            >
              <RefreshCw className="w-4 h-4 animate-spin" /> Reset Kill Switch
            </button>
          ) : (
            <button
              onClick={() => setShowKillModal(true)}
              className="w-full py-3.5 px-4 rounded-2xl text-xs font-bold bg-gradient-to-b from-red-500 to-red-700 hover:from-red-400 hover:to-red-600 text-white shadow-apple-glow-red border border-white/30 flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <AlertOctagon className="w-4 h-4" /> Emergency Kill Switch
            </button>
          )}
        </div>
      </div>

      {/* Apple 3D Cylindrical Loss Limit Gauge */}
      <div className="mt-6 pt-5 border-t border-white/10">
        <div className="flex items-center justify-between text-xs mb-2">
          <div className="flex items-center gap-2.5">
            <span className="font-bold text-white tracking-tight">₹250 Daily Loss Ceiling (Hard Circuit Breaker)</span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-apple-subtext">
              Limit: ₹{dailyLossLimit.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-apple-subtext text-xs">Remaining Headroom:</span>
            <span className={`font-mono text-sm font-extrabold ${headroom <= 50 ? 'text-apple-red animate-pulse' : 'text-apple-green'}`}>
              ₹{headroom.toFixed(2)}
            </span>
          </div>
        </div>

        {/* 3D Glass Cylindrical Track */}
        <div className="w-full bg-black/60 rounded-full h-3.5 p-0.5 border border-white/10 shadow-inner relative overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r transition-all duration-700 ${progressGradient} ${glowColor}`}
            style={{ width: `${Math.min(100, Math.max(2, lossConsumedPct))}%` }}
          />
        </div>

        <div className="flex justify-between text-[11px] font-mono text-apple-subtext mt-1.5 px-0.5">
          <span>₹0.00 Drawdown</span>
          <span>50% (₹125.00 Warning)</span>
          <span className="text-apple-red font-bold">100% (₹250.00 Hard Stop)</span>
        </div>
      </div>

      {/* Kill Switch Modal */}
      {showKillModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xl p-4">
          <div className="apple-glass rounded-3xl max-w-md w-full p-6 shadow-2xl border border-red-500/40">
            <div className="flex items-center gap-2.5 text-apple-red mb-2 font-bold text-lg">
              <AlertOctagon className="w-6 h-6 animate-pulse" /> Confirm Kill Switch
            </div>
            <p className="text-xs text-slate-300 mb-4 leading-relaxed">
              This will transition Central Risk Engine to <b>KILL_SWITCH_ACTIVE</b>,
              cancel all open pending orders, and trigger market square-off for all active positions.
            </p>
            <div className="mb-5">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Operator Audit Justification:
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Unusual spread widening / feed dropped"
                className="apple-input-3d w-full p-3 text-xs rounded-xl text-white placeholder-slate-500"
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2.5">
              <button
                onClick={() => setShowKillModal(false)}
                className="apple-btn-3d px-4 py-2 text-xs font-semibold rounded-xl text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleKillSubmit}
                disabled={!reason.trim() || isSubmitting}
                className="px-5 py-2 text-xs font-bold bg-apple-red hover:bg-red-600 text-white rounded-xl shadow-apple-glow-red disabled:opacity-50 transition"
              >
                {isSubmitting ? 'Triggering...' : 'Activate Kill Switch'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Modal */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xl p-4">
          <div className="apple-glass rounded-3xl max-w-md w-full p-6 shadow-2xl border border-apple-orange/40">
            <div className="flex items-center gap-2.5 text-apple-orange mb-2 font-bold text-lg">
              <RefreshCw className="w-6 h-6" /> Reset Kill Switch
            </div>
            <p className="text-xs text-slate-300 mb-4 leading-relaxed">
              Resetting requires operator justification. The Central Risk Engine will re-audit current
              session limits before accepting any new trade proposals.
            </p>
            <div className="mb-5">
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Audit Reason:
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Feed restored, operator verified risk parameters"
                className="apple-input-3d w-full p-3 text-xs rounded-xl text-white placeholder-slate-500"
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2.5">
              <button
                onClick={() => setShowResetModal(false)}
                className="apple-btn-3d px-4 py-2 text-xs font-semibold rounded-xl text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleResetSubmit}
                disabled={!reason.trim() || isSubmitting}
                className="px-5 py-2 text-xs font-bold bg-apple-orange hover:bg-amber-600 text-black rounded-xl shadow-lg disabled:opacity-50 transition"
              >
                {isSubmitting ? 'Resetting...' : 'Confirm Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
