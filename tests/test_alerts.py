from __future__ import annotations

from datetime import datetime

from trading_bot.alerts import format_blocked_alert, format_scan_board, format_scan_result
from trading_bot.mt5_scanner import SymbolScanResult
from trading_bot.trade_controls import ControlCheckResult


def make_result(symbol: str, **kwargs) -> SymbolScanResult:
    base = dict(
        symbol=symbol,
        direction='LONG',
        grade='A+',
        score=0.93,
        reasons=['aligned'],
        cautions=[],
        blockers=[],
        is_tradable=True,
        control_result=ControlCheckResult(True, None, symbol, 'london'),
        regime='TRENDING',
        timestamp=datetime(2026, 7, 8, 8, 0),
    )
    base.update(kwargs)
    return SymbolScanResult(**base)


def test_format_scan_result_for_tradable_a_plus_long():
    text = format_scan_result(make_result('XAUUSD'))
    assert text == '✅ A+ LONG  — XAUUSD  — Score 0.93'


def test_format_scan_result_for_daily_cap_block():
    result = make_result('EURUSD', is_tradable=False, control_result=ControlCheckResult(False, 'NO TRADE — daily symbol cap reached (5/5)', 'EURUSD', 'london'))
    text = format_scan_result(result)
    assert 'NO TRADE — daily symbol cap reached (5/5)' in text


def test_format_scan_result_for_cooldown_block():
    result = make_result('GBPUSD', is_tradable=False, control_result=ControlCheckResult(False, 'NO TRADE — cooldown active (12m remaining)', 'GBPUSD', 'london'))
    text = format_scan_result(result)
    assert 'NO TRADE — cooldown active (12m remaining)' in text


def test_format_scan_result_for_session_cap_block():
    result = make_result('USDJPY', is_tradable=False, control_result=ControlCheckResult(False, 'NO TRADE — session cap reached (2/2 in london)', 'USDJPY', 'london'))
    text = format_scan_result(result)
    assert 'NO TRADE — session cap reached (2/2 in london)' in text


def test_format_scan_board_includes_all_symbols():
    board = format_scan_board([make_result('XAUUSD'), make_result('EURUSD', is_tradable=False, control_result=ControlCheckResult(False, 'NO TRADE — cooldown active (12m remaining)', 'EURUSD', 'london'))])
    assert 'XAUUSD' in board
    assert 'EURUSD' in board


def test_blocked_symbols_appear_with_clear_reason():
    alert = format_blocked_alert('XAUUSD', 'NO TRADE — daily symbol cap reached (5/5)')
    assert alert == '🚫 NO TRADE — daily symbol cap reached (5/5) — XAUUSD'
