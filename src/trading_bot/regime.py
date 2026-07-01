from __future__ import annotations

from typing import Any


def classify_regime(row: dict[str, float], settings: dict[str, Any]) -> str:
    cfg = settings["regime"]
    adx_value = float(row.get("adx_14", 0.0))
    atr_value = float(row.get("atr_14", 0.0))

    if adx_value >= cfg["trend_adx_threshold"]:
        return "trending"
    if adx_value <= cfg["range_adx_threshold"]:
        return "ranging"
    if atr_value >= cfg["high_vol_atr_threshold"]:
        return "high_vol"
    return "neutral"
