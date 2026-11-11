import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  MinusCircle,
  Clock,
  Info,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
} from 'lucide-react';
import { TradePlanResponse } from '../types';
import { api } from '../services/api';

export const LiveTradeAdvisor: React.FC = () => {
  const [symbol, setSymbol] = useState('');
  const [userPrice, setUserPrice] = useState<string>('');
  const [exchange, setExchange] = useState('NSE');
  const [timeframe, setTimeframe] = useState('5m');
  const [tradeStyle, setTradeStyle] = useState('INTRADAY');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [planResponse, setPlanResponse] = useState<TradePlanResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showAllStrategies, setShowAllStrategies] = useState(false);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim()) return;

    setIsAnalyzing(true);
    setErrorMsg(null);
    try {
      const parsedPrice = userPrice.trim() ? parseFloat(userPrice.trim()) : undefined;
      const res = await api.analyzeStock({
        stock_symbol: symbol.trim(),
        current_price: parsedPrice && !isNaN(parsedPrice) ? parsedPrice : null,
        exchange,
        timeframe,
        trade_style: tradeStyle,
      });
      setPlanResponse(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to analyze stock');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'BUY':
        return (
          <div className="relative group">
            <div className="absolute -inset-1 bg-apple-green rounded-full blur-md opacity-50 group-hover:opacity-80 transition duration-500" />
            <span className="relative px-4 py-1.5 rounded-full text-xs font-black tracking-wider bg-black/80 text-apple-green border border-apple-green/50 flex items-center gap-1.5 shadow-2xl uppercase">
              <ArrowUpRight className="w-4 h-4 stroke-[2.5]" /> CONSIDER BUY
            </span>
          </div>
        );
      case 'SELL':
        return (
          <div className="relative group">
            <div className="absolute -inset-1 bg-apple-red rounded-full blur-md opacity-50 group-hover:opacity-80 transition duration-500" />
            <span className="relative px-4 py-1.5 rounded-full text-xs font-black tracking-wider bg-black/80 text-apple-red border border-apple-red/50 flex items-center gap-1.5 shadow-2xl uppercase">
              <ArrowDownRight className="w-4 h-4 stroke-[2.5]" /> CONSIDER SELL
            </span>
          </div>
        );
      case 'HOLD':
        return (
          <div className="relative group">
            <div className="absolute -inset-1 bg-apple-orange rounded-full blur-md opacity-40 group-hover:opacity-75 transition duration-500" />
            <span className="relative px-4 py-1.5 rounded-full text-xs font-black tracking-wider bg-black/80 text-apple-orange border border-apple-orange/50 flex items-center gap-1.5 shadow-2xl uppercase">
              <MinusCircle className="w-4 h-4" /> HOLD / WAIT
            </span>
          </div>
        );
      default:
        return (
          <span className="px-4 py-1.5 rounded-full text-xs font-bold tracking-wider bg-white/10 text-apple-subtext border border-white/10 flex items-center gap-1.5 uppercase font-mono">
            <MinusCircle className="w-4 h-4" /> NO TRADE
          </span>
        );
    }
  };

  const getPriceTypeBadge = (type: string) => {
    switch (type) {
      case 'LIVE':
        return (
          <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-apple-green/15 text-apple-green border border-apple-green/30 shadow-sm">
            LIVE QUOTE
          </span>
        );
      case 'DELAYED':
        return (
          <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-apple-orange/15 text-apple-orange border border-apple-orange/30 shadow-sm">
            DELAYED (~15M)
          </span>
        );
      case 'USER_PROVIDED':
        return (
          <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-apple-purple/15 text-apple-purple border border-apple-purple/30 shadow-sm">
            USER PROVIDED
          </span>
        );
      case 'SIMULATED':
        return (
          <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-apple-blue/15 text-apple-blue border border-apple-blue/30 shadow-sm">
            SIMULATED
          </span>
        );
      default:
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-apple-subtext">UNAVAILABLE</span>;
    }
  };

  return (
    <div className="apple-glass rounded-3xl p-6 shadow-apple-3d relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/2 left-1/3 w-80 h-80 bg-apple-purple/10 rounded-full blur-3xl pointer-events-none -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="apple-btn-3d p-2.5 rounded-2xl text-apple-blue border-apple-blue/30">
            <Sparkles className="w-5 h-5 text-apple-blue" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">Live Trade Advisor</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-slate-300">
                PRO ENGINE
              </span>
            </div>
            <p className="text-xs text-apple-subtext">
              Multi-strategy quantitative evaluator for Indian stocks (NSE/BSE).
            </p>
          </div>
        </div>
        <div className="text-[11px] font-mono text-apple-subtext flex items-center gap-1.5 apple-btn-3d px-3 py-1.5 rounded-full">
          <Info className="w-3.5 h-3.5 text-apple-blue" /> Advisory only • Guaranteed profits prohibited
        </div>
      </div>

      {/* 3D Stock Input Form */}
      <form onSubmit={handleAnalyze} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-7 gap-3 mb-6">
        <div className="md:col-span-2">
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Stock Symbol / Name <span className="text-apple-red">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. RELIANCE, TCS, INFY"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="apple-input-3d w-full px-3.5 py-2.5 text-xs text-white placeholder-slate-500 rounded-xl font-mono uppercase tracking-wider"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">
            Price (Optional)
          </label>
          <input
            type="number"
            step="0.05"
            placeholder="e.g. 2450.50"
            value={userPrice}
            onChange={(e) => setUserPrice(e.target.value)}
            className="apple-input-3d w-full px-3.5 py-2.5 text-xs text-white placeholder-slate-500 rounded-xl font-mono"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">Exchange</label>
          <select
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
            className="apple-input-3d w-full px-3 py-2.5 text-xs text-white rounded-xl"
          >
            <option value="NSE">NSE</option>
            <option value="BSE">BSE</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">Timeframe</label>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="apple-input-3d w-full px-3 py-2.5 text-xs text-white rounded-xl"
          >
            <option value="5m">5 Min</option>
            <option value="15m">15 Min</option>
            <option value="60m">1 Hour</option>
            <option value="1d">Daily</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">Style</label>
          <select
            value={tradeStyle}
            onChange={(e) => setTradeStyle(e.target.value)}
            className="apple-input-3d w-full px-3 py-2.5 text-xs text-white rounded-xl"
          >
            <option value="INTRADAY">Intraday</option>
            <option value="DELIVERY">Delivery</option>
          </select>
        </div>

        <div className="flex items-end">
          <button
            type="submit"
            disabled={isAnalyzing || !symbol.trim()}
            className="apple-btn-primary w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5 disabled:opacity-40"
          >
            <Search className="w-4 h-4" />
            {isAnalyzing ? 'Evaluating...' : 'Analyze'}
          </button>
        </div>
      </form>

      {/* Error Message */}
      {errorMsg && (
        <div className="mb-4 p-3.5 bg-red-950/40 border border-apple-red/40 rounded-2xl text-xs text-red-200 flex items-center gap-2.5 shadow-lg">
          <AlertTriangle className="w-4 h-4 text-apple-red flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Trade Plan Output Section */}
      {planResponse && (
        <div className="apple-card-3d rounded-2xl p-5 space-y-5 border border-white/15">
          {/* Top Bar: Resolved Instrument, Reference Price & 3D Decision */}
          <div className="flex items-center justify-between flex-wrap gap-4 pb-4 border-b border-white/10">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-2xl font-black text-white font-mono tracking-tight">
                  {planResponse.instrument.symbol}
                </span>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-white/10 text-slate-300 font-mono">
                  {planResponse.instrument.exchange}:{planResponse.instrument.segment}
                </span>
                {getPriceTypeBadge(planResponse.market_data.price_type)}
              </div>
              <div className="flex items-center gap-3 text-xs text-apple-subtext mt-1.5 font-mono">
                <span>
                  Ref Price:{' '}
                  <b className="text-white text-sm">
                    {planResponse.market_data.price ? `₹${planResponse.market_data.price.toFixed(2)}` : 'N/A'}
                  </b>
                </span>
                <span>•</span>
                <span>Source: {planResponse.market_data.provider}</span>
                <span>•</span>
                <span className="flex items-center gap-1 text-slate-400">
                  <Clock className="w-3 h-3 text-apple-blue" />
                  {new Date(planResponse.market_data.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
                </span>
              </div>
            </div>

            <div>{getDecisionBadge(planResponse.decision)}</div>
          </div>

          {/* Suggested Trade Plan Levels */}
          {planResponse.decision !== 'NO TRADE' && planResponse.plan.entry_range ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 bg-black/40 p-4 rounded-2xl border border-white/10 shadow-inner">
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                <span className="text-[10px] text-apple-subtext uppercase font-bold tracking-wider block">
                  Entry Range
                </span>
                <span className="text-base font-mono font-bold text-white mt-0.5 block">
                  {planResponse.plan.entry_range}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-apple-red/5 border border-apple-red/20">
                <span className="text-[10px] text-apple-red uppercase font-bold tracking-wider block">
                  Stop Loss
                </span>
                <span className="text-base font-mono font-bold text-apple-red mt-0.5 block">
                  ₹{planResponse.plan.stop_loss ? planResponse.plan.stop_loss.toFixed(2) : 'N/A'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-apple-green/5 border border-apple-green/20">
                <span className="text-[10px] text-apple-green uppercase font-bold tracking-wider block">
                  Target Exit
                </span>
                <span className="text-base font-mono font-bold text-apple-green mt-0.5 block">
                  ₹{planResponse.plan.exit_target ? planResponse.plan.exit_target.toFixed(2) : 'N/A'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-apple-orange/5 border border-apple-orange/20">
                <span className="text-[10px] text-apple-orange uppercase font-bold tracking-wider block">
                  Risk / Reward
                </span>
                <span className="text-base font-mono font-bold text-apple-orange mt-0.5 block">
                  {planResponse.plan.risk_reward_ratio ? `1 : ${planResponse.plan.risk_reward_ratio}` : 'N/A'}
                </span>
              </div>
              <div className="md:col-span-4 text-xs text-apple-subtext pt-2.5 border-t border-white/10">
                <span className="font-semibold text-slate-200">Execution Rule:</span> {planResponse.plan.exit_rule}
              </div>
            </div>
          ) : (
            <div className="p-4 bg-white/[0.02] border border-white/10 rounded-2xl text-xs text-apple-subtext leading-relaxed">
              <span className="font-bold text-slate-200">No Actionable Alignment:</span> Price levels remain unset because no enabled strategy signaled high-probability alignment. Preserving capital is prioritized.
            </div>
          )}

          {/* Strategy Consensus Breakdown */}
          <div>
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-2.5">
              <span>Strategy Agreement Breakdown ({planResponse.strategy_summary.total_strategies} Registered)</span>
              <span className="font-mono text-apple-subtext">{planResponse.strategy_summary.agreement_summary}</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center text-xs font-mono">
              <div className="apple-card-3d p-3 rounded-xl border-apple-green/30">
                <span className="block text-[10px] text-apple-green font-bold tracking-wider">BULLISH</span>
                <span className="text-xl font-bold text-apple-green mt-0.5">{planResponse.strategy_summary.bullish_count}</span>
              </div>
              <div className="apple-card-3d p-3 rounded-xl border-apple-red/30">
                <span className="block text-[10px] text-apple-red font-bold tracking-wider">BEARISH</span>
                <span className="text-xl font-bold text-apple-red mt-0.5">{planResponse.strategy_summary.bearish_count}</span>
              </div>
              <div className="apple-card-3d p-3 rounded-xl border-apple-orange/30">
                <span className="block text-[10px] text-apple-orange font-bold tracking-wider">NEUTRAL</span>
                <span className="text-xl font-bold text-apple-orange mt-0.5">{planResponse.strategy_summary.neutral_count}</span>
              </div>
              <div className="apple-card-3d p-3 rounded-xl">
                <span className="block text-[10px] text-apple-subtext font-bold tracking-wider">NO SIGNAL</span>
                <span className="text-xl font-bold text-slate-300 mt-0.5">{planResponse.strategy_summary.non_signaling_count}</span>
              </div>
            </div>
          </div>

          {/* Rationale & Reasoning */}
          <div className="p-4 bg-white/[0.02] border border-white/10 rounded-2xl text-xs space-y-1.5">
            <div className="font-bold text-white flex items-center gap-2">
              <Info className="w-4 h-4 text-apple-blue" /> Evidence & Rationale
            </div>
            <p className="text-slate-300 leading-relaxed font-sans">{planResponse.reasoning}</p>
          </div>

          {/* Collapsible Strategy-by-Strategy Results */}
          <div>
            <button
              onClick={() => setShowAllStrategies(!showAllStrategies)}
              className="apple-btn-3d w-full flex items-center justify-between py-2.5 px-4 text-xs font-semibold rounded-xl text-slate-200"
            >
              <span className="flex items-center gap-2">
                <SlidersHorizontal className="w-3.5 h-3.5 text-apple-blue" />
                View Detailed Strategy Outputs ({planResponse.strategy_results.length})
              </span>
              {showAllStrategies ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showAllStrategies && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 mt-3 pt-3 border-t border-white/10">
                {planResponse.strategy_results.map((item, idx) => (
                  <div
                    key={idx}
                    className="apple-card-3d p-3.5 rounded-xl text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between font-mono">
                      <span className="font-bold text-white">{item.strategy_name}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          item.signal === 'BUY'
                            ? 'bg-apple-green/20 text-apple-green border border-apple-green/30'
                            : item.signal === 'SELL'
                            ? 'bg-apple-red/20 text-apple-red border border-apple-red/30'
                            : 'bg-white/10 text-apple-subtext'
                        }`}
                      >
                        {item.signal}
                      </span>
                    </div>
                    {item.entry_price_or_range && (
                      <div className="text-[11px] text-apple-subtext font-mono">
                        Entry: {item.entry_price_or_range} | SL: ₹{item.stop_loss} | Tgt: {item.exit_target_or_rule}
                      </div>
                    )}
                    {item.supporting_evidence.length > 0 && (
                      <div className="text-[10px] text-apple-green/90">
                        Evidence: {item.supporting_evidence.join(', ')}
                      </div>
                    )}
                    {item.contradicting_evidence.length > 0 && (
                      <div className="text-[10px] text-apple-subtext">
                        Condition: {item.contradicting_evidence.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Safety & Limitations Disclaimers */}
          <div className="text-[11px] text-apple-subtext bg-white/[0.015] p-3.5 rounded-xl border border-white/5 space-y-1">
            <p><b>Limitations:</b> {planResponse.limitations}</p>
            <p className="text-apple-orange/90"><b>Safety:</b> {planResponse.safety_notice}</p>
          </div>
        </div>
      )}
    </div>
  );
};
