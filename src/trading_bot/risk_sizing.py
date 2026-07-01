from __future__ import annotations


def position_size_from_risk(
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    contract_value_per_point: float = 1.0,
    min_size: float = 0.01,
    max_size: float | None = None,
) -> float:
    risk_amount = equity * risk_pct
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return 0.0

    raw_size = risk_amount / (stop_distance * contract_value_per_point)
    size = max(raw_size, min_size)
    if max_size is not None:
        size = min(size, max_size)
    return round(size, 2)
