from __future__ import annotations

import argparse
import json

from .backtest_runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run XAUUSD intraday research backtest")
    parser.add_argument("--data", default="data/sample_xauusd_1m.csv", help="Path to 1m OHLCV CSV")
    parser.add_argument("--settings", default="config/settings.yaml", help="Path to settings YAML")
    parser.add_argument("--news", default="config/news_calendar.yaml", help="Path to news calendar YAML")
    parser.add_argument("--output-dir", default=None, help="Optional directory to export trades/equity CSV")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run(args.data, args.settings, args.news, args.output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
