from __future__ import annotations

from datetime import datetime, timedelta

from trading_bot.mt5_scanner import MT5MultiSymbolScanner
from trading_bot.trade_controls import TradeControlManager


def test_scan_symbol_works_with_injected_dataframe(sample_config, sample_bars):
    scanner = MT5MultiSymbolScanner(sample_config, trade_controls=TradeControlManager(sample_config))
    result = scanner.scan_symbol('XAUUSD', bars=sample_bars)
    assert result.symbol == 'XAUUSD'
    assert result.grade in {'A+', 'A', 'B', 'C', 'REJECTED'}


def test_scan_watchlist_returns_all_symbols(sample_config, sample_bars, monkeypatch):
    scanner = MT5MultiSymbolScanner(sample_config, trade_controls=TradeControlManager(sample_config))
    monkeypatch.setattr(scanner, 'fetch_bars', lambda symbol, n_bars=200: sample_bars)
    results = scanner.scan_watchlist()
    assert [result.symbol for result in results] == ['XAUUSD', 'EURUSD', 'GBPUSD'] or len(results) == 3


def test_ranked_opportunities_suppress_capped_symbols(sample_config, sample_bars):
    controls = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for step in range(5):
        controls.record_trade('XAUUSD', now + timedelta(minutes=step * 25))
    scanner = MT5MultiSymbolScanner(sample_config, trade_controls=controls)
    results = [scanner.scan_symbol('XAUUSD', bars=sample_bars), scanner.scan_symbol('EURUSD', bars=sample_bars)]
    ranked = scanner.get_ranked_opportunities(results)
    assert all(result.symbol != 'XAUUSD' for result in ranked)


def test_format_scan_board_includes_blocked_symbols_in_diagnostics(sample_config, sample_bars):
    controls = TradeControlManager(sample_config)
    now = datetime(2026, 7, 8, 8, 0)
    for step in range(5):
        controls.record_trade('XAUUSD', now + timedelta(minutes=step * 25))
    scanner = MT5MultiSymbolScanner(sample_config, trade_controls=controls)
    results = [scanner.scan_symbol('XAUUSD', bars=sample_bars), scanner.scan_symbol('EURUSD', bars=sample_bars)]
    board = scanner.format_scan_board(results)
    assert 'Diagnostic / Blocked:' in board
    assert 'XAUUSD' in board
