from datetime import datetime, timezone

import pytest

from trading_bot.caps import CapsManager
from trading_bot.config import load_config


@pytest.fixture
def caps():
    config = load_config()
    return CapsManager(config)


def test_no_caps_initially(caps):
    state = caps.check("XAUUSD", "London", [], 0)
    assert state["symbol_capped"] is False
    assert state["in_cooldown"] is False
    assert state["session_capped"] is False
    assert state["has_open_position"] is False
    assert state["total_positions_maxed"] is False


def test_symbol_capped_after_max_alerts(caps):
    for _ in range(5):
        caps.record_alert("XAUUSD", "London")
    state = caps.check("XAUUSD", "London", [], 0)
    assert state["symbol_capped"] is True
    assert state["symbol_count"] == 5


def test_cooldown_after_alert(caps):
    caps.record_alert("XAUUSD", "London")
    state = caps.check("XAUUSD", "London", [], 0)
    assert state["in_cooldown"] is True
    assert state["cooldown_remaining_min"] > 0


def test_session_cap(caps):
    caps.record_alert("XAUUSD", "London")
    caps.record_alert("GBPUSD", "London")
    state = caps.check("EURUSD", "London", [], 0)
    assert state["session_capped"] is True


def test_open_position_detected(caps):
    positions = [{"symbol": "XAUUSD", "type": "buy", "volume": 0.1}]
    state = caps.check("XAUUSD", "London", positions, 1)
    assert state["has_open_position"] is True


def test_total_positions_maxed(caps):
    positions = [
        {"symbol": "XAUUSD", "type": "buy", "volume": 0.1},
        {"symbol": "EURUSD", "type": "sell", "volume": 0.1},
    ]
    state = caps.check("GBPUSD", "London", positions, 2)
    assert state["total_positions_maxed"] is True


def test_get_session_london():
    caps = CapsManager(load_config())
    dt = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
    session = caps.get_session(dt)
    assert session == "London"


def test_get_session_overlap():
    caps = CapsManager(load_config())
    dt = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)
    session = caps.get_session(dt)
    assert session == "Overlap"


def test_get_session_newyork():
    caps = CapsManager(load_config())
    dt = datetime(2024, 1, 15, 17, 0, tzinfo=timezone.utc)
    session = caps.get_session(dt)
    assert session == "NewYork"
