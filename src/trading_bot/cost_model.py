from __future__ import annotations


def apply_execution_costs(entry: float, exit_price: float, side: str, spread: float, slippage: float) -> tuple[float, float]:
    half_spread = spread / 2
    if side == "long":
        effective_entry = entry + half_spread + slippage
        effective_exit = exit_price - half_spread - slippage
    else:
        effective_entry = entry - half_spread - slippage
        effective_exit = exit_price + half_spread + slippage
    return effective_entry, effective_exit
