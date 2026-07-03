import unittest

from trading.config import GateConfig
from trading.models import PerformanceMetrics
from trading.performance_gating import evaluate_performance_gates


class PerformanceGateTests(unittest.TestCase):
    def test_gate_requires_minimums(self):
        status = evaluate_performance_gates(
            PerformanceMetrics(
                forward_trades=10,
                max_drawdown=0.2,
                profit_factor=1.0,
                expectancy_r=0.01,
                recent_underperformance=True,
            ),
            GateConfig(),
        )
        self.assertFalse(status.eligible_for_scaling)
        self.assertIn("insufficient_forward_trades", status.reasons)
        self.assertIn("drawdown_limit_breached", status.reasons)


if __name__ == "__main__":
    unittest.main()
