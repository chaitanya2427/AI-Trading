"""
Event-Driven Chronological Backtesting Engine
Enforces strict look-ahead bias elimination, realistic next-bar execution,
slippage/spread crossing, mandatory intraday square-off (15:15 IST), and the hard ₹250 daily loss ceiling.
"""

from datetime import datetime, time
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from backend.app.adapters.validator import validator
from backend.app.core.clock import clock
from backend.app.core.config import settings
from backend.app.models.domain import DirectionEnum, Instrument
from backtesting.metrics import BacktestMetricsCalculator
from execution.costs import cost_calculator, position_sizer
from strategies.base import BaseStrategy


class BacktestEngine:
    """
    Event-driven simulation of intraday trading strategies.
    Strictly prevents look-ahead bias by evaluating at candle $t$ close and executing at $t+1$ open.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        instrument: Instrument,
        initial_capital: float = settings.STARTING_CAPITAL_INR,
        slippage_pct: float = 0.0003,  # 0.03% (approx 1 tick on 2500 equity)
        spread_ticks: int = 1,
        timeframe: str = "5m",
    ):
        self.strategy = strategy
        self.instrument = instrument
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.spread_ticks = spread_ticks
        self.timeframe = timeframe

    def run(
        self,
        candles_df: pd.DataFrame,
        data_source_label: str = "SYNTHETIC_FIXTURE",
    ) -> Dict:
        """
        Executes backtest over historical candles DataFrame.
        """
        df = validator.sanitize_dataframe(candles_df)
        if len(df) < self.strategy.min_candles_required + 2:
            return BacktestMetricsCalculator.compute_tear_sheet(
                [], initial_capital=self.initial_capital, data_source_label=data_source_label
            )

        trades: List[Dict] = []
        open_position: Optional[Dict] = None
        pending_order: Optional[Dict] = None

        # Track daily loss for the ₹250 halt ceiling
        current_date = None
        daily_pnl = 0.0
        daily_halted = False

        n_bars = len(df)

        for i in range(self.strategy.min_candles_required, n_bars):
            current_bar = df.iloc[i]
            prev_bar = df.iloc[i - 1]

            bar_time = current_bar["timestamp"]
            bar_date = bar_time.date() if hasattr(bar_time, "date") else pd.to_datetime(bar_time).date()
            bar_clock_time = bar_time.time() if hasattr(bar_time, "time") else pd.to_datetime(bar_time).time()

            # New Trading Day Session Reset
            if bar_date != current_date:
                current_date = bar_date
                daily_pnl = 0.0
                daily_halted = False

            # ------------------------------------------------------------------
            # 1. Execute Pending Order at Current Bar Open (Next-Bar Execution)
            # ------------------------------------------------------------------
            if pending_order is not None and open_position is None and not daily_halted:
                # Apply slippage and half-spread crossing
                open_p = float(current_bar["open"])
                half_spread = (self.instrument.tick_size * self.spread_ticks) / 2.0

                if pending_order["direction"] == DirectionEnum.LONG:
                    fill_price = round(open_p * (1.0 + self.slippage_pct) + half_spread, 2)
                    # Verify stop loss is still below fill price
                    if pending_order["stop_loss"] < fill_price:
                        # Re-calculate quantity based on exact fill price
                        qty, risk_inr = position_sizer.calculate_quantity(
                            instrument=self.instrument,
                            entry_price=fill_price,
                            stop_loss=pending_order["stop_loss"],
                            available_capital=self.initial_capital + daily_pnl,
                            max_risk_inr=settings.MAX_RISK_PER_TRADE_INR,
                        )
                        if qty > 0:
                            open_position = {
                                "entry_time": bar_time,
                                "direction": DirectionEnum.LONG,
                                "entry_price": fill_price,
                                "stop_loss": pending_order["stop_loss"],
                                "target": pending_order["target"],
                                "quantity": qty,
                                "strategy": self.strategy.name,
                            }
                else:  # SHORT
                    fill_price = round(open_p * (1.0 - self.slippage_pct) - half_spread, 2)
                    if pending_order["stop_loss"] > fill_price:
                        qty, risk_inr = position_sizer.calculate_quantity(
                            instrument=self.instrument,
                            entry_price=fill_price,
                            stop_loss=pending_order["stop_loss"],
                            available_capital=self.initial_capital + daily_pnl,
                            max_risk_inr=settings.MAX_RISK_PER_TRADE_INR,
                        )
                        if qty > 0:
                            open_position = {
                                "entry_time": bar_time,
                                "direction": DirectionEnum.SHORT,
                                "entry_price": fill_price,
                                "stop_loss": pending_order["stop_loss"],
                                "target": pending_order["target"],
                                "quantity": qty,
                                "strategy": self.strategy.name,
                            }

                pending_order = None  # Consume order

            # ------------------------------------------------------------------
            # 2. Check Intrabar Exits for Open Position
            # ------------------------------------------------------------------
            if open_position is not None:
                high_p = float(current_bar["high"])
                low_p = float(current_bar["low"])
                open_p = float(current_bar["open"])
                close_p = float(current_bar["close"])

                exit_price = None
                exit_reason = None

                # Mandatory Intraday Square-off at or after 15:15 IST
                if bar_clock_time >= time(15, 15):
                    exit_price = close_p
                    exit_reason = "INTRADAY_SQUARE_OFF"

                elif open_position["direction"] == DirectionEnum.LONG:
                    hit_stop = low_p <= open_position["stop_loss"]
                    hit_target = high_p >= open_position["target"]

                    if hit_stop and hit_target:
                        # Conservative assumption: Stop Loss hit first
                        exit_price = min(open_p, open_position["stop_loss"])
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_price = min(open_p, open_position["stop_loss"])
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_price = open_position["target"]
                        exit_reason = "TARGET"

                elif open_position["direction"] == DirectionEnum.SHORT:
                    hit_stop = high_p >= open_position["stop_loss"]
                    hit_target = low_p <= open_position["target"]

                    if hit_stop and hit_target:
                        # Conservative assumption: Stop Loss hit first
                        exit_price = max(open_p, open_position["stop_loss"])
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_price = max(open_p, open_position["stop_loss"])
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_price = open_position["target"]
                        exit_reason = "TARGET"

                # If position exited
                if exit_price is not None:
                    # Apply slippage on exit
                    if open_position["direction"] == DirectionEnum.LONG:
                        fill_exit = round(exit_price * (1.0 - self.slippage_pct), 2)
                        gross_pnl = round((fill_exit - open_position["entry_price"]) * open_position["quantity"], 2)
                    else:
                        fill_exit = round(exit_price * (1.0 + self.slippage_pct), 2)
                        gross_pnl = round((open_position["entry_price"] - fill_exit) * open_position["quantity"], 2)

                    # Deduct full statutory Indian taxes and costs
                    costs = cost_calculator.calculate_round_trip_costs(
                        instrument=self.instrument,
                        entry_price=open_position["entry_price"],
                        exit_price=fill_exit,
                        quantity=open_position["quantity"],
                    )

                    net_pnl = round(gross_pnl - costs["total_costs"], 2)
                    daily_pnl += net_pnl

                    trade_record = {
                        "entry_time": open_position["entry_time"],
                        "exit_time": bar_time,
                        "symbol": self.instrument.symbol,
                        "direction": open_position["direction"].value,
                        "entry_price": open_position["entry_price"],
                        "exit_price": fill_exit,
                        "quantity": open_position["quantity"],
                        "gross_pnl": gross_pnl,
                        "total_costs": costs["total_costs"],
                        "net_pnl": net_pnl,
                        "exit_reason": exit_reason,
                        "costs_breakdown": costs,
                    }
                    trades.append(trade_record)
                    open_position = None

                    # Check hard daily loss limit halt
                    if daily_pnl <= -settings.DAILY_LOSS_LIMIT_INR:
                        daily_halted = True

            # ------------------------------------------------------------------
            # 3. Strategy Signal Generation at Bar Close (t) for Execution at (t+1)
            # ------------------------------------------------------------------
            if open_position is None and pending_order is None and not daily_halted:
                # Disallow new entries after 15:00 IST cutoff
                if bar_clock_time < time(15, 0):
                    # Slice history strictly up to current bar to eliminate look-ahead bias
                    history_slice = df.iloc[: i + 1]
                    signal = self.strategy.evaluate(
                        candles=history_slice,
                        instrument=self.instrument,
                        timeframe=self.timeframe,
                    )
                    if signal is not None:
                        # Queue order for execution at next bar open
                        pending_order = {
                            "direction": signal.direction,
                            "stop_loss": signal.stop_loss,
                            "target": signal.target,
                        }

        # ----------------------------------------------------------------------
        # 4. Close any open position remaining at the end of the simulation
        # ----------------------------------------------------------------------
        if open_position is not None:
            last_bar = df.iloc[-1]
            last_close = float(last_bar["close"])
            bar_time = last_bar["timestamp"]

            if open_position["direction"] == DirectionEnum.LONG:
                fill_exit = round(last_close * (1.0 - self.slippage_pct), 2)
                gross_pnl = round((fill_exit - open_position["entry_price"]) * open_position["quantity"], 2)
            else:
                fill_exit = round(last_close * (1.0 + self.slippage_pct), 2)
                gross_pnl = round((open_position["entry_price"] - fill_exit) * open_position["quantity"], 2)

            costs = cost_calculator.calculate_round_trip_costs(
                instrument=self.instrument,
                entry_price=open_position["entry_price"],
                exit_price=fill_exit,
                quantity=open_position["quantity"],
            )
            net_pnl = round(gross_pnl - costs["total_costs"], 2)

            trades.append(
                {
                    "entry_time": open_position["entry_time"],
                    "exit_time": bar_time,
                    "symbol": self.instrument.symbol,
                    "direction": open_position["direction"].value,
                    "entry_price": open_position["entry_price"],
                    "exit_price": fill_exit,
                    "quantity": open_position["quantity"],
                    "gross_pnl": gross_pnl,
                    "total_costs": costs["total_costs"],
                    "net_pnl": net_pnl,
                    "exit_reason": "END_OF_DATA",
                    "costs_breakdown": costs,
                }
            )

        return BacktestMetricsCalculator.compute_tear_sheet(
            trades=trades,
            initial_capital=self.initial_capital,
            data_source_label=data_source_label,
        )
