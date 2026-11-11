"""
Technical Indicators Engine
Vectorized, mathematically verified indicator computations using pandas and numpy.
Supports intraday session-aware metrics (e.g. VWAP resetting each calendar day).
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (Wilder's RSI).
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100.0 - (100.0 / (1.0 + rs))
    rsi_series = rsi_series.where(avg_loss != 0, 100.0)
    rsi_series = rsi_series.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return rsi_series.fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (Wilder's ATR).
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price (VWAP).
    Resets at the start of each intraday session.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    tp_vol = typical_price * df["volume"]

    # Extract date for session reset
    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        dates = df["timestamp"].dt.date
    else:
        dates = pd.to_datetime(df["timestamp"]).dt.date

    # Grouped cumulative sums
    cum_tp_vol = tp_vol.groupby(dates).cumsum()
    cum_vol = df["volume"].groupby(dates).cumsum()

    vwap_series = cum_tp_vol / cum_vol.replace(0, np.nan)
    return vwap_series.ffill().bfill()


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands: returns (upper_band, middle_band, lower_band).
    """
    mid = sma(series, period)
    rolling_std = series.rolling(window=period, min_periods=period).std()
    upper = mid + num_std * rolling_std
    lower = mid - num_std * rolling_std
    return upper, mid, lower


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Moving Average Convergence Divergence.
    Returns (macd_line, signal_line, histogram).
    """
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[pd.Series, pd.Series]:
    """
    Supertrend Volatility Indicator.
    Returns (supertrend_value, trend_direction) where direction is +1 (Bullish) or -1 (Bearish).
    """
    atr_val = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2.0

    basic_upper = hl2 + multiplier * atr_val
    basic_lower = hl2 - multiplier * atr_val

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend_vals = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    n = len(df)
    if n == 0:
        return supertrend_vals, direction

    direction.iloc[0] = 1 if df["close"].iloc[0] >= hl2.iloc[0] else -1
    supertrend_vals.iloc[0] = final_lower.iloc[0] if direction.iloc[0] == 1 else final_upper.iloc[0]

    for i in range(1, n):
        # Final Upper Band
        if basic_upper.iloc[i] < final_upper.iloc[i - 1] or df["close"].iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        # Final Lower Band
        if basic_lower.iloc[i] > final_lower.iloc[i - 1] or df["close"].iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        prev_dir = direction.iloc[i - 1]
        if prev_dir == 1 and df["close"].iloc[i] < final_lower.iloc[i]:
            direction.iloc[i] = -1
        elif prev_dir == -1 and df["close"].iloc[i] > final_upper.iloc[i]:
            direction.iloc[i] = 1
        else:
            direction.iloc[i] = prev_dir

        supertrend_vals.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]

    return supertrend_vals, direction


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriches candle DataFrame with all core technical indicators.
    """
    res = df.copy()
    res["rsi"] = rsi(res["close"])
    res["vwap"] = vwap(res)
    res["atr"] = atr(res)

    res["ema_9"] = ema(res["close"], 9)
    res["ema_21"] = ema(res["close"], 21)
    res["ema_50"] = ema(res["close"], 50)

    upper, mid, lower = bollinger_bands(res["close"])
    res["bb_upper"] = upper
    res["bb_mid"] = mid
    res["bb_lower"] = lower

    macd_line, sig_line, hist = macd(res["close"])
    res["macd_line"] = macd_line
    res["macd_signal"] = sig_line
    res["macd_hist"] = hist

    st_val, st_dir = supertrend(res)
    res["supertrend"] = st_val
    res["supertrend_dir"] = st_dir

    return res
