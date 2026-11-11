import React, { useState } from 'react';
import { ArrowUpRight, ArrowDownRight, Square, Layers } from 'lucide-react';
import { PaperPosition } from '../types';

interface PositionsTableProps {
  positions: PaperPosition[];
  onSquareOff: (positionId: string) => Promise<void>;
  onSquareOffAll: () => Promise<void>;
  isLoading: boolean;
}

export const PositionsTable: React.FC<PositionsTableProps> = ({
  positions,
  onSquareOff,
  onSquareOffAll,
  isLoading,
}) => {
  const [closingId, setClosingId] = useState<string | null>(null);
  const [closingAll, setClosingAll] = useState(false);

  const openPositions = positions.filter((p) => p.status === 'OPEN');

  const handleSquareOff = async (id: string) => {
    setClosingId(id);
    try {
      await onSquareOff(id);
    } finally {
      setClosingId(null);
    }
  };

  const handleSquareOffAll = async () => {
    setClosingAll(true);
    try {
      await onSquareOffAll();
    } finally {
      setClosingAll(false);
    }
  };

  return (
    <div className="apple-card-3d relative overflow-hidden backdrop-blur-2xl bg-black/60 border border-white/[0.08] shadow-apple-3d p-6 rounded-3xl">
      {/* Specular top highlight */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-white/[0.05] border border-white/[0.1] shadow-inner flex items-center justify-center">
            <Layers className="w-4 h-4 text-[#30D158]" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-base sm:text-lg font-semibold tracking-tight text-white/95">
                Active Virtual Positions
              </h2>
              <span className="text-[11px] font-mono font-semibold px-2.5 py-0.5 rounded-full bg-[#30D158]/15 text-[#30D158] border border-[#30D158]/30 shadow-apple-glow-green">
                {openPositions.length} Open
              </span>
            </div>
            <p className="text-xs text-[#86868B] mt-0.5">
              Simulated fills with realistic slippage • Strict intraday cut-off at 15:15 IST
            </p>
          </div>
        </div>

        {openPositions.length > 0 && (
          <button
            onClick={handleSquareOffAll}
            disabled={closingAll || isLoading}
            className="apple-btn-3d py-2 px-3.5 text-xs font-semibold rounded-xl bg-[#FF453A]/15 hover:bg-[#FF453A]/25 text-[#FF453A] border border-[#FF453A]/30 shadow-apple-glow-red flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <Square className="w-3.5 h-3.5" />
            <span>{closingAll ? 'Squaring Off All...' : 'Square-Off All Positions'}</span>
          </button>
        )}
      </div>

      {openPositions.length === 0 ? (
        <div className="py-12 text-center rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01]">
          <div className="w-10 h-10 rounded-full bg-white/[0.03] border border-white/[0.08] mx-auto flex items-center justify-center mb-2.5">
            <Layers className="w-4 h-4 text-[#86868B]" />
          </div>
          <div className="text-sm font-medium text-white/80">All Positions Flat</div>
          <p className="text-xs text-[#86868B] mt-1">
            No active open risk in the paper book. Intraday cut-off strictly enforced at 15:15 IST.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-white/[0.06] bg-black/40">
          <table className="w-full text-left text-xs">
            <thead className="bg-white/[0.03] text-[#86868B] uppercase text-[10px] font-mono border-b border-white/[0.08]">
              <tr>
                <th className="py-3 px-4">Instrument</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4">Qty</th>
                <th className="py-3 px-4">Entry</th>
                <th className="py-3 px-4">Current</th>
                <th className="py-3 px-4">SL / Target</th>
                <th className="py-3 px-4">Unrealized MTM</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05] font-mono">
              {openPositions.map((pos) => {
                const isLong = pos.direction === 'LONG';
                const isPnlPositive = pos.unrealized_pnl >= 0;
                const isClosing = closingId === pos.position_id;

                return (
                  <tr
                    key={pos.position_id}
                    className="hover:bg-white/[0.04] transition-colors duration-150"
                  >
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-white font-sans text-sm tracking-tight">
                        {pos.symbol}
                      </div>
                      <div className="text-[10px] text-[#86868B]">{pos.exchange}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-0.5 ${
                          isLong
                            ? 'bg-[#30D158]/15 text-[#30D158] border border-[#30D158]/30 shadow-apple-glow-green'
                            : 'bg-[#FF453A]/15 text-[#FF453A] border border-[#FF453A]/30 shadow-apple-glow-red'
                        }`}
                      >
                        {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {pos.direction}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-white/90 font-medium">{pos.quantity}</td>
                    <td className="py-3.5 px-4 text-[#86868B]">₹{pos.entry_price.toFixed(2)}</td>
                    <td className="py-3.5 px-4 text-white font-bold">₹{pos.current_price.toFixed(2)}</td>
                    <td className="py-3.5 px-4 text-[11px]">
                      <span className="text-[#FF453A]">SL: ₹{pos.stop_loss.toFixed(2)}</span>
                      <span className="text-white/20 mx-1.5">•</span>
                      <span className="text-[#30D158]">Tgt: ₹{pos.target.toFixed(2)}</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-sm font-bold tracking-tight ${
                          isPnlPositive
                            ? 'text-[#30D158] drop-shadow-[0_0_8px_rgba(48,209,88,0.35)]'
                            : 'text-[#FF453A] drop-shadow-[0_0_8px_rgba(255,69,58,0.35)]'
                        }`}
                      >
                        {isPnlPositive ? '+' : ''}₹{pos.unrealized_pnl.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleSquareOff(pos.position_id)}
                        disabled={isClosing || isLoading}
                        className="apple-btn-3d py-1.5 px-3 rounded-lg text-xs font-semibold text-[#FF453A]/90 hover:text-white bg-[#FF453A]/10 hover:bg-[#FF453A]/25 border border-[#FF453A]/30 font-sans transition disabled:opacity-50"
                      >
                        {isClosing ? 'Closing...' : 'Square Off'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
