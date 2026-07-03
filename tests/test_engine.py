import unittest

from trading.config import TradingConfig
from trading.engine import TradeEngine
from trading.models import PerformanceMetrics, SignalContext


class EngineTests(unittest.TestCase):
    def test_mt5_requires_explicit_opt_in_and_gate(self):
        cfg = TradingConfig()
        cfg.mode.mode = "mt5"
        cfg.mode.trade_enabled = True
        engine = TradeEngine(cfg)

        can_trade, reasons, _ = engine.evaluate(
            SignalContext(
                direction="buy",
                htf_direction="buy",
                session="london",
                atr_normalized=1.1,
                spread_points=20,
                room_to_target_atr=1.5,
                trigger_candle_atr_ratio=1.0,
            ),
            PerformanceMetrics(
                forward_trades=40,
                max_drawdown=0.08,
                profit_factor=1.3,
                expectancy_r=0.1,
                recent_underperformance=False,
            ),
        )

        self.assertFalse(can_trade)
        self.assertIn("mt5_opt_in_required", reasons)


if __name__ == "__main__":
    unittest.main()
