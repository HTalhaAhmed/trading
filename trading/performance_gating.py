from __future__ import annotations

from .config import GateConfig
from .models import GateStatus, PerformanceMetrics


def evaluate_performance_gates(metrics: PerformanceMetrics, cfg: GateConfig) -> GateStatus:
    reasons: list[str] = []

    if metrics.forward_trades < cfg.min_forward_trades:
        reasons.append("insufficient_forward_trades")
    if metrics.max_drawdown > cfg.max_drawdown:
        reasons.append("drawdown_limit_breached")
    if metrics.profit_factor < cfg.min_profit_factor:
        reasons.append("profit_factor_below_threshold")
    if metrics.expectancy_r < cfg.min_expectancy:
        reasons.append("expectancy_below_threshold")
    if cfg.disable_after_recent_underperformance and metrics.recent_underperformance:
        reasons.append("recent_underperformance")

    eligible = not reasons
    return GateStatus(eligible_for_scaling=eligible, eligible_for_live=eligible, reasons=reasons)
