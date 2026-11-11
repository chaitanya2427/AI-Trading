import React, { useState } from 'react';
import { CheckCircle2, XCircle, ArrowUpRight, ArrowDownRight, Sparkles, Shield } from 'lucide-react';
import { TradeProposal } from '../types';

interface ProposalDeckProps {
  proposals: TradeProposal[];
  onApprove: (proposalId: string) => Promise<void>;
  onReject: (proposalId: string, reason: string) => Promise<void>;
  onScanStrategies?: () => Promise<void>;
  isLoading: boolean;
}

export const ProposalDeck: React.FC<ProposalDeckProps> = ({
  proposals,
  onApprove,
  onReject,
  onScanStrategies,
  isLoading,
}) => {
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [processingId, setProcessingId] = useState<string | null>(null);

  const pendingProposals = proposals.filter((p) => p.human_decision === 'PENDING');

  const handleApprove = async (id: string) => {
    setProcessingId(id);
    try {
      await onApprove(id);
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (id: string) => {
    if (!rejectReason.trim()) return;
    setProcessingId(id);
    try {
      await onReject(id, rejectReason);
      setRejectingId(null);
      setRejectReason('');
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="apple-card-3d relative overflow-hidden backdrop-blur-2xl bg-black/60 border border-white/[0.08] shadow-apple-3d p-6 rounded-3xl">
      {/* Specular top sheen */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-white/[0.05] border border-white/[0.1] shadow-inner flex items-center justify-center">
            <Shield className="w-4 h-4 text-[#0A84FF]" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-base sm:text-lg font-semibold tracking-tight text-white/95">
                Trade Proposals
              </h2>
              <span className="text-[11px] font-mono font-semibold px-2.5 py-0.5 rounded-full bg-[#0A84FF]/15 text-[#64D2FF] border border-[#0A84FF]/30 shadow-apple-glow-blue">
                {pendingProposals.length} Pending Approval
              </span>
            </div>
            <p className="text-xs text-[#86868B] mt-0.5">
              Deterministic gate • Dual-operator approval required before execution
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {onScanStrategies && (
            <button
              onClick={onScanStrategies}
              disabled={isLoading}
              className="apple-btn-primary py-2 px-4 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-apple-glow-blue transition-all disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isLoading ? 'Scanning...' : 'Scan Strategies'}</span>
            </button>
          )}
        </div>
      </div>

      {pendingProposals.length === 0 ? (
        <div className="py-14 text-center rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01]">
          <div className="w-12 h-12 rounded-full bg-white/[0.03] border border-white/[0.08] mx-auto flex items-center justify-center mb-3">
            <Shield className="w-5 h-5 text-[#86868B]" />
          </div>
          <div className="text-sm font-medium text-white/80">No Pending Proposals</div>
          <p className="text-xs text-[#86868B] max-w-md mx-auto mt-1">
            Autonomous multi-agent scanners are monitoring the tape. When market conditions trigger deterministic criteria, actionable proposals will appear here for human authorization.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {pendingProposals.map((p) => {
            const isLong = p.direction === 'LONG';
            const isCurrentProcessing = processingId === p.proposal_id;

            return (
              <div
                key={p.proposal_id}
                className="apple-card-3d group relative bg-white/[0.03] hover:bg-white/[0.055] border border-white/[0.1] hover:border-white/[0.2] rounded-2xl p-5 shadow-apple-3d flex flex-col justify-between transition-all duration-300"
              >
                {/* Subtle top edge specular highlight */}
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent pointer-events-none" />

                <div>
                  {/* Strategy Badge & Direction */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] font-mono font-medium px-2.5 py-0.5 rounded-full bg-white/[0.06] text-white/80 border border-white/[0.08]">
                      {p.strategy_name}
                    </span>
                    <span
                      className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1 ${
                        isLong
                          ? 'bg-[#30D158]/15 text-[#30D158] border border-[#30D158]/30 shadow-apple-glow-green'
                          : 'bg-[#FF453A]/15 text-[#FF453A] border border-[#FF453A]/30 shadow-apple-glow-red'
                      }`}
                    >
                      {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {p.direction}
                    </span>
                  </div>

                  {/* Instrument & Reference Price */}
                  <div className="flex items-baseline justify-between mb-4">
                    <div>
                      <div className="text-xl font-bold tracking-tight text-white">{p.symbol}</div>
                      <div className="text-[11px] text-[#86868B] font-mono mt-0.5">
                        {p.exchange}:{p.segment} • Qty: <span className="text-white/90 font-semibold">{p.quantity}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-mono font-semibold tracking-tight text-white/95">
                        ₹{p.entry_price.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-[#86868B]">Entry Reference</div>
                    </div>
                  </div>

                  {/* 3D Inset Glass Levels Grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs mb-4 bg-black/40 border border-white/[0.07] p-3 rounded-xl shadow-inner">
                    <div className="space-y-0.5">
                      <span className="text-[#86868B] block text-[10px] uppercase font-mono">Stop Loss</span>
                      <span className="font-mono font-semibold text-[#FF453A]">
                        ₹{p.stop_loss.toFixed(2)}
                      </span>
                    </div>
                    <div className="space-y-0.5">
                      <span className="text-[#86868B] block text-[10px] uppercase font-mono">Target</span>
                      <span className="font-mono font-semibold text-[#30D158]">
                        ₹{p.target.toFixed(2)}
                      </span>
                    </div>
                    <div className="space-y-0.5 pt-1.5 border-t border-white/[0.05]">
                      <span className="text-[#86868B] block text-[10px] uppercase font-mono">Max Risk</span>
                      <span className="font-mono font-semibold text-white/90">
                        ₹{p.estimated_risk_inr.toFixed(2)}
                      </span>
                    </div>
                    <div className="space-y-0.5 pt-1.5 border-t border-white/[0.05]">
                      <span className="text-[#86868B] block text-[10px] uppercase font-mono">Est. Reward</span>
                      <span className="font-mono font-semibold text-white/90">
                        ₹{p.estimated_reward_inr.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  {/* Estimated Costs */}
                  <div className="flex items-center justify-between text-[11px] text-[#86868B] mb-4 px-1">
                    <span>Est. Statutory Charges:</span>
                    <span className="font-mono text-[#FF9F0A] font-medium">₹{p.estimated_costs_inr.toFixed(2)}</span>
                  </div>
                </div>

                {/* Reject Input Form or Action Buttons */}
                {rejectingId === p.proposal_id ? (
                  <div className="mt-2 pt-3 border-t border-white/[0.08] animate-fade-in">
                    <input
                      type="text"
                      placeholder="Reason for rejection..."
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="apple-input-3d w-full text-xs p-2.5 rounded-xl bg-black/50 border border-white/[0.12] text-white mb-2.5 focus:outline-none focus:border-[#FF453A]/60"
                      autoFocus
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => {
                          setRejectingId(null);
                          setRejectReason('');
                        }}
                        className="apple-btn-3d text-xs text-[#86868B] hover:text-white px-3 py-1.5 rounded-lg"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleReject(p.proposal_id)}
                        disabled={!rejectReason.trim() || isCurrentProcessing}
                        className="apple-btn-3d text-xs font-semibold bg-[#FF453A]/20 hover:bg-[#FF453A]/30 text-[#FF453A] border border-[#FF453A]/40 px-3.5 py-1.5 rounded-lg disabled:opacity-50"
                      >
                        Confirm Reject
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2.5 mt-2 pt-3 border-t border-white/[0.08]">
                    <button
                      onClick={() => setRejectingId(p.proposal_id)}
                      disabled={isCurrentProcessing || isLoading}
                      className="apple-btn-3d py-2 px-3 rounded-xl text-xs font-medium text-white/70 hover:text-white hover:bg-white/[0.08] flex items-center justify-center gap-1.5 transition disabled:opacity-50"
                    >
                      <XCircle className="w-3.5 h-3.5 text-[#FF453A]" /> Reject
                    </button>
                    <button
                      onClick={() => handleApprove(p.proposal_id)}
                      disabled={isCurrentProcessing || isLoading}
                      className="apple-btn-primary py-2 px-3 rounded-xl text-xs font-semibold shadow-apple-glow-blue flex items-center justify-center gap-1.5 transition disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {isCurrentProcessing ? 'Approving...' : 'Approve & Fill'}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
