from __future__ import annotations

from trading_bot.scanner import Grade, ScanResult, TradeScanner


class StubReviewer:
    def __init__(self, score: float, blockers=None):
        self.score = score
        self.blockers = blockers or []

    def review(self, features, direction):
        return type('Review', (), {
            'score': self.score,
            'reasons': ['stub'],
            'cautions': [],
            'blockers': list(self.blockers),
        })()


def bullish_features() -> dict:
    return {
        'ema_9': 10,
        'ema_21': 9,
        'ema_50': 8,
        'ema_200': 7,
        'adx': 30,
        'atr': 1.0,
        'atr_mean_20': 0.8,
        'rsi': 60,
        'macd': 1.0,
        'macd_signal': 0.8,
        'macd_hist': 0.2,
        'bb_upper': 12,
        'bb_lower': 8,
        'bb_width': 0.02,
        'spread': 0.05,
        'close': 10.5,
        'open': 10.2,
        'high': 10.6,
        'low': 10.0,
        'bar_range': 0.6,
        'body_pct': 0.5,
        'close_location': 0.83,
    }


def test_scan_result_has_expected_fields(sample_config):
    scanner = TradeScanner(sample_config)
    result = scanner.scan('XAUUSD', bullish_features())
    assert isinstance(result, ScanResult)
    assert result.symbol == 'XAUUSD'
    assert hasattr(result, 'direction')
    assert hasattr(result, 'grade')
    assert hasattr(result, 'score')
    assert hasattr(result, 'timestamp')


def test_grade_assignment_thresholds(sample_config):
    scanner = TradeScanner(sample_config)
    scanner.reviewers = [(StubReviewer(0.86), 1.0)]
    assert scanner.scan('XAUUSD', bullish_features(), direction_override='LONG').grade is Grade.APLUS
    scanner.reviewers = [(StubReviewer(0.71), 1.0)]
    assert scanner.scan('XAUUSD', bullish_features(), direction_override='LONG').grade is Grade.A
    scanner.reviewers = [(StubReviewer(0.56), 1.0)]
    assert scanner.scan('XAUUSD', bullish_features(), direction_override='LONG').grade is Grade.B
    scanner.reviewers = [(StubReviewer(0.41), 1.0)]
    assert scanner.scan('XAUUSD', bullish_features(), direction_override='LONG').grade is Grade.C


def test_only_a_plus_mode_suppresses_lower_grades(sample_config):
    scanner = TradeScanner(sample_config)
    scanner.reviewers = [(StubReviewer(0.56), 1.0)]
    result = scanner.scan('XAUUSD', bullish_features(), direction_override='LONG')
    assert result.grade is Grade.B
    assert scanner.is_tradable(result) is False


def test_blockers_force_rejected(sample_config):
    scanner = TradeScanner(sample_config)
    scanner.reviewers = [(StubReviewer(0.99, blockers=['hard blocker']), 1.0)]
    result = scanner.scan('XAUUSD', bullish_features(), direction_override='LONG')
    assert result.grade is Grade.REJECTED
    assert result.direction == 'NO TRADE'


def test_direction_determination(sample_config):
    scanner = TradeScanner(sample_config)
    long_result = scanner.scan('XAUUSD', bullish_features())
    assert long_result.direction == 'LONG'
    short_features = bullish_features() | {'ema_9': 7, 'ema_21': 8, 'ema_50': 9, 'ema_200': 10, 'rsi': 40, 'macd': -1, 'macd_signal': -0.8, 'macd_hist': -0.2}
    short_result = scanner.scan('EURUSD', short_features)
    assert short_result.direction in {'SHORT', 'NO TRADE'}
    neutral_result = scanner.scan('GBPUSD', bullish_features() | {'rsi': 50, 'ema_21': 10})
    assert neutral_result.direction == 'NO TRADE'


def test_is_tradable_true_for_a_plus(sample_config):
    scanner = TradeScanner(sample_config)
    scanner.reviewers = [(StubReviewer(0.90), 1.0)]
    result = scanner.scan('XAUUSD', bullish_features(), direction_override='LONG')
    assert scanner.is_tradable(result) is True
    blocked = scanner.scan('XAUUSD', bullish_features(), direction_override='NO TRADE')
    assert scanner.is_tradable(blocked) is False
