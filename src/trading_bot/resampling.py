from __future__ import annotations

import pandas as pd


RESAMPLE_RULES = {
    "5min": "5min",
    "15min": "15min",
}


def resample_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe not in RESAMPLE_RULES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    rule = RESAMPLE_RULES[timeframe]
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    if "spread" in df.columns:
        agg["spread"] = "mean"

    out = df.resample(rule).agg(agg)
    return out.dropna(subset=["open", "high", "low", "close"])
