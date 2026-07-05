from __future__ import annotations

from typing import Any


def generate_range_signal(row: dict[str, float], settings: dict[str, Any]) -> dict[str, Any] | None:
    cfg = settings["strategy"]["range"]
    rsi = row.get("rsi_14")
    close = row.get("close")
    vwap = row.get("session_vwap")

    if None in (rsi, close, vwap):
        return None

    if rsi <= cfg["rsi_oversold"] and close < vwap:
        return {"side": "long", "stop_atr_mult": cfg["stop_atr_mult"], "take_profit_r": cfg["take_profit_r"]}
    if rsi >= cfg["rsi_overbought"] and close > vwap:
        return {"side": "short", "stop_atr_mult": cfg["stop_atr_mult"], "take_profit_r": cfg["take_profit_r"]}
    return None
