import React from 'react';
import { ShieldAlert, ShieldCheck, Activity, RefreshCw, Lock, Sparkles } from 'lucide-react';
import { SystemStatus } from '../types';

interface HeaderProps {
  status: SystemStatus | null;
  onRefresh: () => void;
  onOpenAudit: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  onRefresh,
  onOpenAudit,
  isRefreshing,
}) => {
  const isHalted = status?.risk_status === 'HALTED';
  const isKillSwitch = status?.kill_switch_active;
  const isHealthy = !isHalted && !isKillSwitch;

  return (
    <header className="sticky top-3 z-50 px-4 max-w-7xl mx-auto w-full">
      <div className="apple-glass rounded-2xl px-5 py-3 flex flex-wrap items-center justify-between gap-4">
        {/* Left: Brand & Product Identity */}
        <div className="flex items-center gap-3.5">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-apple-blue via-apple-purple to-apple-blue rounded-xl blur-sm opacity-40 group-hover:opacity-75 transition duration-500" />
            <div className="relative bg-black/80 p-2.5 rounded-xl border border-white/20 text-white shadow-2xl flex items-center justify-center">
              <Activity className="w-5 h-5 text-apple-blue animate-pulse" />
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                <span>AI Multi-Agent Trading</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-slate-200 border border-white/15 shadow-sm">
                  PRO
                </span>
              </h1>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-apple-orange/15 text-apple-orange border border-apple-orange/30 shadow-sm">
                PAPER
              </span>
              <span className="text-[10px] font-mono flex items-center gap-1 px-2 py-0.5 rounded-full bg-apple-green/15 text-apple-green border border-apple-green/30 shadow-sm">
                <Lock className="w-2.5 h-2.5" /> LIVE DISABLED
              </span>
            </div>
            <p className="text-[11px] text-apple-subtext font-normal tracking-normal">
              Indian Financial Markets (NSE/BSE) • Intraday Conservative Quantitative System
            </p>
          </div>
        </div>

        {/* Right: Floating Glass Status Pills */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Dynamic Island Session Clock */}
          <div className="apple-btn-3d px-3.5 py-1.5 rounded-full flex items-center gap-2 text-xs font-mono">
            <div className="w-2 h-2 rounded-full bg-apple-blue animate-ping" />
            <span className="text-slate-200 font-semibold">
              {status ? new Date(status.current_time_ist).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) : '--:--:--'} IST
            </span>
            <span className="text-white/20">•</span>
            <span className={`font-bold tracking-wider uppercase text-[11px] ${status?.is_market_open ? 'text-apple-green' : 'text-apple-subtext'}`}>
              {status?.session_phase || 'UNKNOWN'}
            </span>
          </div>

          {/* System Risk Status Pill */}
          <div
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border shadow-lg transition-all ${
              isHealthy
                ? 'bg-apple-green/10 text-apple-green border-apple-green/30 shadow-apple-glow-green'
                : 'bg-apple-red/15 text-apple-red border-apple-red/40 shadow-apple-glow-red animate-pulse'
            }`}
          >
            {isHealthy ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
            <span>
              {isKillSwitch ? 'KILL SWITCH ACTIVE' : isHalted ? 'HALTED (₹250 CEILING)' : 'ACTIVE & PROTECTED'}
            </span>
          </div>

          {/* Audit Logs Pill */}
          <button
            onClick={onOpenAudit}
            className="apple-btn-3d px-3.5 py-1.5 text-xs font-medium rounded-full text-slate-200 flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5 text-apple-purple" />
            <span>Audit Trail</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="apple-btn-3d p-2 rounded-full text-slate-300 disabled:opacity-40"
            title="Refresh Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-apple-blue' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
