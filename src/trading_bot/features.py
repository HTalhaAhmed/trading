from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd


@dataclass
class FeatureSet:
    symbol: str
    timestamp: datetime
    price: float
    ask: float = 0.0
    bid: float = 0.0
    ema5: float = 0.0
    ema20: float = 0.0
    ema50: float = 0.0
    ema200: float = 0.0
    atr14: float = 0.0
    adx14: float = 0.0
    vwap: float = 0.0
    ema20_5m: float = 0.0
    ema50_5m: float = 0.0
    atr14_5m: float = 0.0
    ema20_15m: float = 0.0
    ema50_15m: float = 0.0
    trend_direction: str = "neutral"
    trend_strength: float = 0.0
    htf_aligned: bool = False
    adx_trending: bool = False
    recent_high: float = 0.0
    recent_low: float = 0.0
    bars_available: int = 0


def _latest_value(series: pd.Series | None) -> float:
    if series is None or len(series) == 0:
        return 0.0
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return 0.0
    return float(cleaned.iloc[-1])


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.ewm(span=period, adjust=False, min_periods=1).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or df.empty or len(df) < 2:
        return 0.0
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return _latest_value(atr)


def compute_adx(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or df.empty or len(df) < period + 1:
        return 0.0

    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_dm_smoothed = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    minus_dm_smoothed = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * (plus_dm_smoothed / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm_smoothed / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return _latest_value(adx)


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    working = df.copy()
    working["time"] = pd.to_datetime(working["time"], utc=True)
    working = working.sort_values("time")
    typical = (working["high"] + working["low"] + working["close"]) / 3.0
    volume = pd.to_numeric(working["volume"], errors="coerce").fillna(0.0)
    dates = working["time"].dt.floor("D")
    cumulative_tpv = (typical * volume).groupby(dates).cumsum()
    cumulative_volume = volume.groupby(dates).cumsum().replace(0, np.nan)
    return cumulative_tpv / cumulative_volume


def resample_ohlcv(df_1m: pd.DataFrame, freq: str) -> pd.DataFrame:
    if df_1m is None or df_1m.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    working = df_1m.copy()
    working["time"] = pd.to_datetime(working["time"], utc=True)
    working = working.set_index("time").sort_index()
    resampled = (
        working.resample(freq)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    return resampled


def compute_features(symbol: str, bars_1m: pd.DataFrame, ask: float = 0.0, bid: float = 0.0) -> FeatureSet:
    if bars_1m is None or bars_1m.empty:
        return FeatureSet(symbol=symbol, timestamp=datetime.now(timezone.utc), price=0.0, ask=ask, bid=bid)

    df = bars_1m.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    close = pd.to_numeric(df["close"], errors="coerce")

    ema5 = compute_ema(close, 5)
    ema20 = compute_ema(close, 20)
    ema50 = compute_ema(close, 50)
    ema200 = compute_ema(close, 200)
    atr14 = compute_atr(df, 14)
    adx14 = compute_adx(df, 14)
    vwap_series = compute_vwap(df)

    df_5m = resample_ohlcv(df, "5min")
    df_15m = resample_ohlcv(df, "15min")

    ema20_5m = _latest_value(compute_ema(df_5m["close"], 20)) if not df_5m.empty else 0.0
    ema50_5m = _latest_value(compute_ema(df_5m["close"], 50)) if not df_5m.empty else 0.0
    atr14_5m = compute_atr(df_5m, 14) if not df_5m.empty else 0.0
    ema20_15m = _latest_value(compute_ema(df_15m["close"], 20)) if not df_15m.empty else 0.0
    ema50_15m = _latest_value(compute_ema(df_15m["close"], 50)) if not df_15m.empty else 0.0

    price = _latest_value(close)
    latest_ema20 = _latest_value(ema20)
    latest_ema50 = _latest_value(ema50)
    latest_ema200 = _latest_value(ema200)

    trend_direction = "neutral"
    if latest_ema20 > latest_ema50 > latest_ema200 and price > latest_ema20:
        trend_direction = "long"
    elif latest_ema20 < latest_ema50 < latest_ema200 and price < latest_ema20:
        trend_direction = "short"

    htf_long = ema20_5m > ema50_5m and ema20_15m > ema50_15m
    htf_short = ema20_5m < ema50_5m and ema20_15m < ema50_15m
    htf_aligned = (trend_direction == "long" and htf_long) or (trend_direction == "short" and htf_short)

    atr_base = atr14 if atr14 > 0 else 1.0
    ema_separation = abs(latest_ema20 - latest_ema50) + abs(latest_ema50 - latest_ema200)
    trend_strength = max(0.0, min(1.0, (ema_separation / atr_base) / 10.0))

    recent_window = df.tail(20) if len(df) >= 20 else df
    recent_high = float(pd.to_numeric(recent_window["high"], errors="coerce").max()) if not recent_window.empty else 0.0
    recent_low = float(pd.to_numeric(recent_window["low"], errors="coerce").min()) if not recent_window.empty else 0.0

    return FeatureSet(
        symbol=symbol,
        timestamp=df["time"].iloc[-1].to_pydatetime(),
        price=price,
        ask=ask,
        bid=bid,
        ema5=_latest_value(ema5),
        ema20=latest_ema20,
        ema50=latest_ema50,
        ema200=latest_ema200,
        atr14=atr14,
        adx14=adx14,
        vwap=_latest_value(vwap_series),
        ema20_5m=ema20_5m,
        ema50_5m=ema50_5m,
        atr14_5m=atr14_5m,
        ema20_15m=ema20_15m,
        ema50_15m=ema50_15m,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        htf_aligned=htf_aligned,
        adx_trending=adx14 > 20,
        recent_high=recent_high,
        recent_low=recent_low,
        bars_available=len(df),
    )
