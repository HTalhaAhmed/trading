from __future__ import annotations

import pandas as pd

from .indicators import adx, atr, ema, rsi


def session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    session = df.index.floor("D")
    pv = typical * df["volume"]
    cum_pv = pv.groupby(session).cumsum()
    cum_vol = df["volume"].groupby(session).cumsum().replace(0, pd.NA)
    return (cum_pv / cum_vol).astype(float)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema_20"] = ema(out["close"], 20)
    out["ema_50"] = ema(out["close"], 50)
    out["atr_14"] = atr(out, 14)
    out["adx_14"] = adx(out, 14)
    out["rsi_14"] = rsi(out["close"], 14)
    out["session_vwap"] = session_vwap(out)
    out["ret_1"] = out["close"].pct_change().fillna(0)
    return out
