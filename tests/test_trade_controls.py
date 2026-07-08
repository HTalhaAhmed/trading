from __future__ import annotations

from datetime import datetime, timedelta

from trading_bot.trade_controls import CooldownTracker, SessionCapTracker, TradeControlManager, TradeCounter


def test_trade_counter_starts_at_zero():
    counter = TradeCounter()
    assert counter.get_count_for_symbol_today('XAUUSD') == 0


def test_trade_counter_caps_after_five_trades():
    counter = TradeCounter(max_per_symbol_per_day=5)
    now = datetime(2026, 7, 8, 8, 0)
    for minute in range(5):
        counter.record_trade('XAUUSD', now + timedelta(minutes=minute), 'london')
    assert counter.is_symbol_capped('XAUUSD', today=now.date()) is True


def test_manager_blocks_on_daily_symbol_cap(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for minute in range(5):
        manager.record_trade('XAUUSD', now + timedelta(minutes=minute * 25))
    result = manager.check('XAUUSD', now=now + timedelta(hours=3))
    assert result.allowed is False
    assert result.blocker_reason == 'NO TRADE — daily symbol cap reached (5/5)'


def test_different_symbol_is_not_capped(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for minute in range(5):
        manager.record_trade('XAUUSD', now + timedelta(minutes=minute * 25))
    assert manager.check('EURUSD', now=now + timedelta(hours=3)).allowed is True


def test_cooldown_tracker_blocks_immediately():
    tracker = CooldownTracker(min_minutes_between_trades=20)
    now = datetime(2026, 7, 8, 8, 0)
    tracker.record_trade('XAUUSD', now)
    assert tracker.is_in_cooldown('XAUUSD', now + timedelta(minutes=1)) is True


def test_cooldown_tracker_expires_after_window():
    tracker = CooldownTracker(min_minutes_between_trades=20)
    now = datetime(2026, 7, 8, 8, 0)
    tracker.record_trade('XAUUSD', now)
    assert tracker.is_in_cooldown('XAUUSD', now + timedelta(minutes=21)) is False


def test_cooldown_remaining_minutes_is_exact():
    tracker = CooldownTracker(min_minutes_between_trades=20)
    now = datetime(2026, 7, 8, 8, 0)
    tracker.record_trade('XAUUSD', now)
    assert tracker.cooldown_remaining_minutes('XAUUSD', now + timedelta(minutes=8)) == 12


def test_session_cap_tracker_caps_after_two_trades():
    tracker = SessionCapTracker(max_per_session=2)
    now = datetime(2026, 7, 8, 8, 0)
    tracker.record_trade('XAUUSD', 'london', now)
    tracker.record_trade('XAUUSD', 'london', now + timedelta(minutes=25))
    assert tracker.is_session_capped('XAUUSD', 'london', today=now.date()) is True


def test_execution_guard_blocks_trade_six(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for minute in range(5):
        manager.record_trade('XAUUSD', now + timedelta(minutes=minute * 25))
    result = manager.execution_guard('XAUUSD', now=now + timedelta(hours=3))
    assert result.allowed is False
    assert result.blocker_reason == 'NO TRADE — daily symbol cap reached (5/5)'


def test_record_trade_updates_all_trackers(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    manager.record_trade('XAUUSD', now=now)
    session = manager.session_cap_tracker._get_current_session(now)
    assert manager.trade_counter.get_count_for_symbol_today('XAUUSD', today=now.date()) == 1
    assert manager.cooldown_tracker.is_in_cooldown('XAUUSD', now + timedelta(minutes=1)) is True
    assert manager.session_cap_tracker.get_count_for_symbol_session('XAUUSD', session, today=now.date()) == 1


def test_daily_cap_message_is_exact(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for minute in range(5):
        manager.record_trade('XAUUSD', now + timedelta(minutes=minute * 25))
    assert manager.check('XAUUSD', now=now + timedelta(hours=3)).blocker_reason == 'NO TRADE — daily symbol cap reached (5/5)'


def test_cooldown_message_format(sample_config):
    manager = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    manager.record_trade('XAUUSD', now=now)
    reason = manager.check('XAUUSD', now=now + timedelta(minutes=8)).blocker_reason
    assert reason == 'NO TRADE — cooldown active (12m remaining)'
