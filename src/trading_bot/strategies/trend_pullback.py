from __future__ import annotations

from typing import Any


def generate_trend_signal(row: dict[str, float], settings: dict[str, Any]) -> dict[str, Any] | None:
    cfg = settings["strategy"]["trend"]

    ema_fast = row.get("ema_20")
    ema_slow = row.get("ema_50")
    close = row.get("close")
    vwap = row.get("session_vwap")

    if None in (ema_fast, ema_slow, close, vwap):
        return None

    long_condition = close > ema_fast > ema_slow and close >= vwap
    short_condition = close < ema_fast < ema_slow and close <= vwap

    if long_condition:
        return {"side": "long", "stop_atr_mult": cfg["stop_atr_mult"], "take_profit_r": cfg["take_profit_r"]}
    if short_condition:
        return {"side": "short", "stop_atr_mult": cfg["stop_atr_mult"], "take_profit_r": cfg["take_profit_r"]}
    return None
