"""
Backtesting Performance Analytics & Tear-Sheet Reporting
Calculates institutional-grade quantitative metrics net-of-all statutory Indian taxes and costs.
"""

import math
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class BacktestMetricsCalculator:
    """Computes comprehensive performance statistics for backtested trade series."""

    @staticmethod
    def compute_tear_sheet(
        trades: List[Dict],
        initial_capital: float = 25000.0,
        risk_free_rate: float = 0.065,  # 6.5% standard Indian RBI repo/treasury proxy
        data_source_label: str = "SYNTHETIC_FIXTURE",
    ) -> Dict:
        """
        Calculates tear-sheet metrics from completed trades.
        Each trade dict must contain:
        ['gross_pnl', 'net_pnl', 'total_costs', 'entry_time', 'exit_time', 'costs_breakdown']
        """
        empty_sheet = {
            "metadata": {
                "data_source": data_source_label,
                "initial_capital_inr": initial_capital,
                "simulated": True,
                "disclaimer": "Simulated Backtest Results. Net of all statutory costs and slippage. Past performance is no guarantee of future returns.",
            },
            "summary": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "net_profit_factor": 0.0,
                "expectancy_inr": 0.0,
            },
            "pnl": {
                "gross_pnl_inr": 0.0,
                "total_costs_inr": 0.0,
                "net_pnl_inr": 0.0,
                "final_equity_inr": initial_capital,
                "return_on_capital_pct": 0.0,
                "avg_win_inr": 0.0,
                "avg_loss_inr": 0.0,
                "win_loss_ratio": 0.0,
            },
            "risk_metrics": {
                "max_drawdown_inr": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
            },
            "execution_metrics": {
                "avg_holding_time_minutes": 0.0,
            },
            "cost_breakdown_inr": {
                "brokerage": 0.0,
                "stt": 0.0,
                "exchange_turnover": 0.0,
                "gst": 0.0,
                "sebi_charges": 0.0,
                "stamp_duty": 0.0,
            },
        }

        if not trades:
            return empty_sheet

        df_trades = pd.DataFrame(trades)
        net_pnls = df_trades["net_pnl"].to_numpy()
        gross_pnls = df_trades["gross_pnl"].to_numpy()
        total_costs = df_trades["total_costs"].to_numpy()

        trade_count = len(trades)
        net_wins = net_pnls[net_pnls > 0]
        net_losses = net_pnls[net_pnls < 0]
        breakeven_trades = net_pnls[net_pnls == 0]

        gross_wins = gross_pnls[gross_pnls > 0]
        gross_losses = gross_pnls[gross_pnls < 0]

        win_count = len(net_wins)
        loss_count = len(net_losses)
        win_rate_pct = round((win_count / trade_count) * 100.0, 2)

        total_gross_pnl = round(float(np.sum(gross_pnls)), 2)
        total_costs_inr = round(float(np.sum(total_costs)), 2)
        total_net_pnl = round(float(np.sum(net_pnls)), 2)

        total_gross_win = float(np.sum(gross_wins)) if len(gross_wins) > 0 else 0.0
        total_gross_loss = abs(float(np.sum(gross_losses))) if len(gross_losses) > 0 else 0.0

        gross_profit_factor = (
            round(total_gross_win / total_gross_loss, 2)
            if total_gross_loss > 0
            else (999.0 if total_gross_win > 0 else 0.0)
        )

        total_net_win = float(np.sum(net_wins)) if len(net_wins) > 0 else 0.0
        total_net_loss = abs(float(np.sum(net_losses))) if len(net_losses) > 0 else 0.0
        net_profit_factor = (
            round(total_net_win / total_net_loss, 2)
            if total_net_loss > 0
            else (999.0 if total_net_win > 0 else 0.0)
        )

        avg_trade_inr = round(float(np.mean(net_pnls)), 2)
        avg_win_inr = round(float(np.mean(net_wins)), 2) if len(net_wins) > 0 else 0.0
        avg_loss_inr = round(float(np.mean(net_losses)), 2) if len(net_losses) > 0 else 0.0

        # Equity Curve and Drawdown
        equity_curve = np.zeros(trade_count + 1)
        equity_curve[0] = initial_capital
        for i in range(trade_count):
            equity_curve[i + 1] = equity_curve[i] + net_pnls[i]

        peak = np.maximum.accumulate(equity_curve)
        drawdown = peak - equity_curve
        max_drawdown_inr = round(float(np.max(drawdown)), 2)
        max_drawdown_pct = round(float(np.max(drawdown / peak) * 100.0), 2)

        # Holding Time Analysis
        holding_durations_minutes = []
        for t in trades:
            e_time = t.get("entry_time")
            x_time = t.get("exit_time")
            if e_time and x_time:
                if isinstance(e_time, str):
                    e_time = pd.to_datetime(e_time)
                if isinstance(x_time, str):
                    x_time = pd.to_datetime(x_time)
                dur = (x_time - e_time).total_seconds() / 60.0
                holding_durations_minutes.append(dur)

        avg_holding_time_mins = (
            round(float(np.mean(holding_durations_minutes)), 1) if holding_durations_minutes else 0.0
        )

        # Annualized Sharpe and Sortino
        trade_returns = net_pnls / initial_capital
        mean_ret = float(np.mean(trade_returns))
        std_ret = float(np.std(trade_returns)) if len(trade_returns) > 1 else 1e-6

        annualization_factor = math.sqrt(750)
        daily_rf = risk_free_rate / 750.0

        excess_ret = mean_ret - daily_rf
        sharpe_ratio = round((excess_ret / std_ret) * annualization_factor, 2) if std_ret > 0 else 0.0

        downside_returns = trade_returns[trade_returns < 0]
        downside_std = float(np.std(downside_returns)) if len(downside_returns) > 1 else 1e-6
        sortino_ratio = round((excess_ret / downside_std) * annualization_factor, 2) if downside_std > 0 else 0.0

        # Aggregate Cost Breakdown
        cost_breakdown = {
            "brokerage": 0.0,
            "stt": 0.0,
            "exchange_turnover": 0.0,
            "gst": 0.0,
            "sebi_charges": 0.0,
            "stamp_duty": 0.0,
        }
        for t in trades:
            cb = t.get("costs_breakdown", {})
            for k in cost_breakdown:
                cost_breakdown[k] += cb.get(k, 0.0)
        cost_breakdown = {k: round(v, 2) for k, v in cost_breakdown.items()}

        return {
            "metadata": {
                "data_source": data_source_label,
                "initial_capital_inr": initial_capital,
                "simulated": True,
                "disclaimer": "Simulated Backtest Results. Net of all statutory costs and slippage. Past performance is no guarantee of future returns.",
            },
            "summary": {
                "total_trades": trade_count,
                "winning_trades": win_count,
                "losing_trades": loss_count,
                "breakeven_trades": len(breakeven_trades),
                "win_rate_pct": win_rate_pct,
                "profit_factor": gross_profit_factor,
                "net_profit_factor": net_profit_factor,
                "expectancy_inr": avg_trade_inr,
            },
            "pnl": {
                "gross_pnl_inr": total_gross_pnl,
                "total_costs_inr": total_costs_inr,
                "net_pnl_inr": total_net_pnl,
                "final_equity_inr": round(initial_capital + total_net_pnl, 2),
                "return_on_capital_pct": round((total_net_pnl / initial_capital) * 100.0, 2),
                "avg_win_inr": avg_win_inr,
                "avg_loss_inr": avg_loss_inr,
                "win_loss_ratio": round(abs(avg_win_inr / avg_loss_inr), 2) if avg_loss_inr != 0 else 0.0,
            },
            "risk_metrics": {
                "max_drawdown_inr": max_drawdown_inr,
                "max_drawdown_pct": max_drawdown_pct,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sortino_ratio,
            },
            "execution_metrics": {
                "avg_holding_time_minutes": avg_holding_time_mins,
            },
            "cost_breakdown_inr": cost_breakdown,
        }
