from __future__ import annotations

from .brokers.mt5 import MT5Broker
from .brokers.paper import PaperBroker
from .config import TradingConfig
from .models import ExecutionResult, GateStatus, OrderRequest, PerformanceMetrics, SignalContext
from .performance_gating import evaluate_performance_gates
from .signal_quality import assess_signal


class TradeEngine:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.kill_switch = False

    def evaluate(self, signal: SignalContext, metrics: PerformanceMetrics) -> tuple[bool, list[str], GateStatus]:
        if self.kill_switch:
            return False, ["kill_switch_active"], evaluate_performance_gates(metrics, self.config.gates)

        gate_status = evaluate_performance_gates(metrics, self.config.gates)
        reasons: list[str] = []

        if not self.config.mode.trade_enabled:
            reasons.append("trade_disabled")

        if self.config.mode.mode == "mt5":
            if not self.config.mode.mt5_explicit_opt_in:
                reasons.append("mt5_opt_in_required")
            if not gate_status.eligible_for_live:
                reasons.extend(gate_status.reasons)

        quality = assess_signal(
            signal,
            self.config.quality,
            self.config.filters,
            self.config.weights,
            self.config.mode.mode,
        )
        reasons.extend(quality.blocked_reasons)

        return not reasons, reasons, gate_status

    def execute(self, order: OrderRequest) -> ExecutionResult:
        mode = self.config.mode.mode
        if mode == "backtest":
            return ExecutionResult(True, "backtest_virtual_fill", "backtest-1")
        if mode == "paper":
            return PaperBroker().submit_order(order)
        if mode == "mt5":
            broker = MT5Broker()
            broker.connect()
            try:
                return broker.submit_order(order)
            finally:
                broker.shutdown()
        return ExecutionResult(False, f"unsupported_mode_{mode}")
