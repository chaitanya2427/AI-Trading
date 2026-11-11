import React from 'react';
import { History, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { PaperOrder } from '../types';

interface OrdersHistoryProps {
  orders: PaperOrder[];
}

export const OrdersHistory: React.FC<OrdersHistoryProps> = ({ orders }) => {
  return (
    <div className="apple-card-3d relative overflow-hidden backdrop-blur-2xl bg-black/60 border border-white/[0.08] shadow-apple-3d p-6 rounded-3xl h-full flex flex-col justify-between">
      {/* Top specular highlight */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none" />

      <div>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-2xl bg-white/[0.05] border border-white/[0.1] shadow-inner flex items-center justify-center">
              <History className="w-4 h-4 text-[#BF5AF2]" />
            </div>
            <div>
              <h2 className="text-base font-semibold tracking-tight text-white/95">
                Paper Execution Ledger
              </h2>
              <p className="text-xs text-[#86868B]">Order lifecycle with slippage and statutory costs</p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-[#86868B] px-2.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08]">
            Simulated Fills
          </span>
        </div>

        {orders.length === 0 ? (
          <div className="py-10 text-center rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01]">
            <div className="text-xs text-[#86868B]">No executed orders in current trading session.</div>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/[0.06] bg-black/40">
            <table className="w-full text-left text-xs">
              <thead className="bg-white/[0.03] text-[#86868B] uppercase text-[10px] font-mono border-b border-white/[0.08]">
                <tr>
                  <th className="py-3 px-3.5">Time</th>
                  <th className="py-3 px-3.5">Symbol</th>
                  <th className="py-3 px-3.5">Type</th>
                  <th className="py-3 px-3.5">Side</th>
                  <th className="py-3 px-3.5">Qty</th>
                  <th className="py-3 px-3.5">Price</th>
                  <th className="py-3 px-3.5">Slippage</th>
                  <th className="py-3 px-3.5">Charges</th>
                  <th className="py-3 px-3.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05] font-mono">
                {orders.slice(0, 10).map((o) => {
                  const isFilled = o.status === 'FILLED';
                  const isCancelled = o.status === 'CANCELLED';
                  const isLong = o.direction === 'LONG';

                  return (
                    <tr key={o.order_id} className="hover:bg-white/[0.04] transition-colors duration-150">
                      <td className="py-2.5 px-3.5 text-[#86868B] text-[11px]">
                        {new Date(o.created_at).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
                      </td>
                      <td className="py-2.5 px-3.5 font-bold text-white font-sans">{o.symbol}</td>
                      <td className="py-2.5 px-3.5 text-[#86868B] text-[11px]">{o.order_type}</td>
                      <td className="py-2.5 px-3.5">
                        <span
                          className={`text-[10px] font-bold inline-flex items-center gap-0.5 ${
                            isLong ? 'text-[#30D158]' : 'text-[#FF453A]'
                          }`}
                        >
                          {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          {o.direction}
                        </span>
                      </td>
                      <td className="py-2.5 px-3.5 text-white/90">{o.quantity}</td>
                      <td className="py-2.5 px-3.5 text-white font-semibold">
                        ₹{o.filled_price ? o.filled_price.toFixed(2) : o.reference_price.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3.5 text-[#86868B]">₹{o.slippage_inr.toFixed(2)}</td>
                      <td className="py-2.5 px-3.5 text-[#FF9F0A] font-medium">₹{o.charges_inr.toFixed(2)}</td>
                      <td className="py-2.5 px-3.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            isFilled
                              ? 'bg-[#30D158]/15 text-[#30D158] border border-[#30D158]/30 shadow-apple-glow-green'
                              : isCancelled
                              ? 'bg-white/[0.06] text-[#86868B] border border-white/[0.08]'
                              : 'bg-[#FF453A]/15 text-[#FF453A] border border-[#FF453A]/30'
                          }`}
                        >
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
