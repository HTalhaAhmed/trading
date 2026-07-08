from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .alerts import format_scan_board
from .backtest import BacktestRunner
from .config import load_config
from .mt5_scanner import MT5MultiSymbolScanner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='python -m trading_bot')
    parser.add_argument('--mode', choices=['scan', 'backtest', 'paper', 'mt5'], default='scan')
    parser.add_argument('--config', default='config/default_settings.yaml')
    parser.add_argument('--data', help='CSV path for backtest mode')
    parser.add_argument('--symbol', help='Single symbol scan')
    parser.add_argument('--only-a-plus', action='store_true')
    parser.add_argument('--format', choices=['report', 'compact', 'telegram', 'json'], default='report')
    parser.add_argument('--scan-json', action='store_true')
    parser.add_argument('--watchlist', nargs='*', help='Override configured watchlist')
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    config.setdefault('broker', {})['mode'] = args.mode
    if args.watchlist:
        config['broker']['watchlist'] = args.watchlist
    if args.only_a_plus:
        config.setdefault('scanner', {})['only_a_plus'] = True

    if args.mode == 'backtest':
        if not args.data:
            raise SystemExit('--data is required for backtest mode')
        runner = BacktestRunner(config)
        report = runner.run(args.data, symbol=args.symbol or 'BACKTEST')
        payload = {
            'symbol': report.symbol,
            'total_bars': report.total_bars,
            'signals': report.signals,
            'executed_trades': report.executed_trades,
            'blocked_trades': report.blocked_trades,
        }
        print(json.dumps(payload, default=str) if args.format == 'json' or args.scan_json else payload)
        return

    scanner = MT5MultiSymbolScanner(config)
    if args.symbol:
        results = [scanner.scan_symbol(args.symbol)]
    else:
        results = scanner.scan_watchlist()

    if args.format == 'json' or args.scan_json:
        print(json.dumps([asdict(result) for result in results], default=str))
    elif args.format == 'compact':
        for result in results:
            print(f'{result.symbol}: {result.grade} {result.direction} {result.score:.2f}')
    else:
        print(format_scan_board(results))


if __name__ == '__main__':
    main()
