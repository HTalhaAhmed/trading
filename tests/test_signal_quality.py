import unittest

from trading.config import FilterConfig, QualityConfig, WeightConfig
from trading.models import SignalContext
from trading.signal_quality import assess_signal


class SignalQualityTests(unittest.TestCase):
    def test_a_plus_only_blocks_non_a_plus(self):
        ctx = SignalContext(
            direction="buy",
            htf_direction="buy",
            session="london",
            atr_normalized=1.1,
            spread_points=20,
            room_to_target_atr=1.5,
            trigger_candle_atr_ratio=2.0,
        )
        quality_cfg = QualityConfig(only_a_plus=True, min_score=0.4, live_min_score=0.4)
        result = assess_signal(ctx, quality_cfg, FilterConfig(), WeightConfig(), mode="backtest")

        self.assertFalse(result.allowed)
        self.assertIn("not_a_plus", result.blocked_reasons)

    def test_filter_blocks_high_spread(self):
        ctx = SignalContext(
            direction="buy",
            htf_direction="buy",
            session="london",
            atr_normalized=1.1,
            spread_points=100,
            room_to_target_atr=1.5,
            trigger_candle_atr_ratio=1.0,
        )
        result = assess_signal(ctx, QualityConfig(), FilterConfig(), WeightConfig(), mode="backtest")
        self.assertFalse(result.allowed)
        self.assertIn("spread", result.blocked_reasons)


if __name__ == "__main__":
    unittest.main()
