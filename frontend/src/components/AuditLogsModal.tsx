import React from 'react';
import { X, ShieldAlert, AlertCircle, Info, Database } from 'lucide-react';
import { AuditLogItem } from '../types';

interface AuditLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  logs: AuditLogItem[];
  isLoading: boolean;
}

export const AuditLogsModal: React.FC<AuditLogsModalProps> = ({
  isOpen,
  onClose,
  logs,
  isLoading,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xl p-4 sm:p-6 animate-fade-in">
      <div className="apple-card-3d relative max-w-3xl w-full h-[82vh] flex flex-col bg-[#0A0A0C]/90 border border-white/[0.12] shadow-2xl rounded-3xl overflow-hidden">
        {/* Specular top highlight */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent pointer-events-none" />

        {/* Modal Header */}
        <div className="p-5 border-b border-white/[0.08] flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-white/[0.05] border border-white/[0.1] shadow-inner flex items-center justify-center">
              <Database className="w-4 h-4 text-[#64D2FF]" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-base font-semibold tracking-tight text-white/95">
                  Immutable Audit Trail
                </h2>
                <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-white/[0.06] text-[#86868B] font-mono border border-white/[0.08]">
                  SQLite WAL Persisted
                </span>
              </div>
              <p className="text-xs text-[#86868B] mt-0.5">
                Cryptographically tracked state transitions and risk actions
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] text-white/70 hover:text-white flex items-center justify-center transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 flex-1 overflow-y-auto space-y-3 font-mono text-xs">
          {isLoading ? (
            <div className="text-center py-16 text-[#86868B]">Loading audit trail...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-16 text-[#86868B]">No audit records logged yet.</div>
          ) : (
            logs.map((log) => {
              const isCritical = log.severity === 'CRITICAL';
              const isWarning = log.severity === 'WARNING';

              return (
                <div
                  key={log.id}
                  className={`p-3.5 rounded-2xl border transition-all ${
                    isCritical
                      ? 'bg-[#FF453A]/10 border-[#FF453A]/30 text-[#FF453A] shadow-apple-glow-red'
                      : isWarning
                      ? 'bg-[#FF9F0A]/10 border-[#FF9F0A]/30 text-[#FF9F0A]'
                      : 'bg-white/[0.02] border-white/[0.06] text-white/80 hover:bg-white/[0.04]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5 text-[11px]">
                    <div className="flex items-center gap-2">
                      {isCritical ? (
                        <ShieldAlert className="w-4 h-4 text-[#FF453A]" />
                      ) : isWarning ? (
                        <AlertCircle className="w-4 h-4 text-[#FF9F0A]" />
                      ) : (
                        <Info className="w-4 h-4 text-[#0A84FF]" />
                      )}
                      <span className="font-semibold uppercase tracking-wider">{log.event_type}</span>
                      <span className="text-white/20">•</span>
                      <span className="text-[#86868B] font-medium">{log.actor}</span>
                    </div>
                    <span className="text-[#86868B] text-[10px]">
                      {new Date(log.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
                    </span>
                  </div>
                  <div className="font-sans text-xs mt-1 text-white/95 leading-relaxed">{log.message}</div>
                  {log.details && (
                    <div className="mt-2 text-[10px] text-[#86868B] bg-black/60 border border-white/[0.05] p-2.5 rounded-xl overflow-x-auto">
                      {JSON.stringify(log.details)}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
