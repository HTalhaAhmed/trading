from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from trading_bot.features import compute_features
from trading_bot.grader import GradeResult, grade_symbol


def test_grade_returns_grade_result(sample_bars, default_config):
    features = compute_features("XAUUSD", sample_bars, ask=2001.0, bid=2000.9)
    caps_state = {
        "symbol_capped": False,
        "symbol_count": 0,
        "symbol_cap": 5,
        "in_cooldown": False,
        "cooldown_remaining_min": 0,
        "session_capped": False,
        "session_count": 0,
        "session_cap": 2,
        "has_open_position": False,
        "total_positions_maxed": False,
        "total_positions": 0,
        "total_cap": 2,
    }
    result = grade_symbol("XAUUSD", features, spread=0.1, config=default_config, caps_state=caps_state)
    assert isinstance(result, GradeResult)
    assert result.grade in ("A+", "A", "B", "C", "NO_TRADE")
    assert 0.0 <= result.score <= 1.0
    assert result.direction in ("LONG", "SHORT", "NO_TRADE")


def test_grade_blocked_when_symbol_capped(sample_bars, default_config):
    features = compute_features("XAUUSD", sample_bars, ask=2001.0, bid=2000.9)
    caps_state = {
        "symbol_capped": True,
        "symbol_count": 5,
        "symbol_cap": 5,
        "in_cooldown": False,
        "cooldown_remaining_min": 0,
        "session_capped": False,
        "session_count": 0,
        "session_cap": 2,
        "has_open_position": False,
        "total_positions_maxed": False,
        "total_positions": 0,
        "total_cap": 2,
    }
    result = grade_symbol("XAUUSD", features, spread=0.1, config=default_config, caps_state=caps_state)
    assert result.surfaced is False
    assert any("cap" in blocker.lower() for blocker in result.blockers)


def test_grade_blocked_when_in_cooldown(sample_bars, default_config):
    features = compute_features("XAUUSD", sample_bars, ask=2001.0, bid=2000.9)
    caps_state = {
        "symbol_capped": False,
        "symbol_count": 1,
        "symbol_cap": 5,
        "in_cooldown": True,
        "cooldown_remaining_min": 15.0,
        "session_capped": False,
        "session_count": 0,
        "session_cap": 2,
        "has_open_position": False,
        "total_positions_maxed": False,
        "total_positions": 0,
        "total_cap": 2,
    }
    result = grade_symbol("XAUUSD", features, spread=0.1, config=default_config, caps_state=caps_state)
    assert result.surfaced is False
    assert any("cooldown" in blocker.lower() for blocker in result.blockers)


def test_grade_no_trade_when_not_trending():
    """Flat/random price should score lower."""
    np.random.seed(123)
    n = 500
    times = [datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]
    price = 2000.0 + np.random.normal(0, 0.1, n)
    closes = np.cumsum(np.zeros(n)) + price
    df = pd.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes + 0.1,
            "low": closes - 0.1,
            "close": closes,
            "volume": np.ones(n) * 100,
        }
    )
    from trading_bot.config import load_config

    config = load_config()
    features = compute_features("EURUSD", df, ask=2000.1, bid=2000.0)
    caps_state = {
        "symbol_capped": False,
        "symbol_count": 0,
        "symbol_cap": 5,
        "in_cooldown": False,
        "cooldown_remaining_min": 0,
        "session_capped": False,
        "session_count": 0,
        "session_cap": 2,
        "has_open_position": False,
        "total_positions_maxed": False,
        "total_positions": 0,
        "total_cap": 2,
    }
    result = grade_symbol("EURUSD", features, spread=0.0001, config=config, caps_state=caps_state)
    assert result.surfaced is False or result.grade not in ("A+",)
