from __future__ import annotations

from typing import Any

from .strategies.range_reversion import generate_range_signal
from .strategies.trend_pullback import generate_trend_signal


def route_signal(regime: str, row: dict[str, float], settings: dict[str, Any]) -> dict[str, Any] | None:
    if regime == "trending":
        return generate_trend_signal(row, settings)
    if regime == "ranging":
        return generate_range_signal(row, settings)
    return None
