"""
CLI entry-point for the XAUUSD trading bot.

Usage examples::

    # Run a scan with default human report
    PYTHONPATH=src python -m trading_bot --mode scan

    # Only show A+ setups in compact format
    PYTHONPATH=src python -m trading_bot --mode scan --only-a-plus --format compact

    # Telegram-style alert output
    PYTHONPATH=src python -m trading_bot --mode scan --format telegram

    # Machine-readable JSON (stable schema)
    PYTHONPATH=src python -m trading_bot --mode scan --format json

    # Run backtest
    PYTHONPATH=src python -m trading_bot --mode backtest \\
        --data path/to/xauusd.csv \\
        --settings path/to/settings.json \\
        --news path/to/news.csv

Output format options
---------------------
  report    Full human-readable report with reviewer breakdown (default)
  compact   Single-line card summary for dashboard/logs
  telegram  Concise plain-text alert for Telegram bots
  json      Machine-readable JSON (stable schema v1)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np

from .config import ScannerConfig, GradeThresholds, ReviewerConfig
from .scanner import Scanner, ScanResult
from .formatters import format_report, format_compact, format_telegram, format_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trading_bot",
        description="XAUUSD intraday trading scanner / grader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    p.add_argument(
        "--mode",
        choices=["scan", "backtest", "paper", "mt5"],
        default="scan",
        help="Operating mode (default: scan)",
    )

    # Output formatting
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["report", "compact", "telegram", "json"],
        default="report",
        help="Output style (default: report)",
    )

    # A+ filter
    p.add_argument(
        "--only-a-plus",
        action="store_true",
        default=False,
        help="Suppress any result that is not A+ grade",
    )

    # Data / settings
    p.add_argument("--data",     default="", help="Path to OHLCV CSV for backtest")
    p.add_argument("--settings", default="", help="Path to settings JSON")
    p.add_argument("--news",     default="", help="Path to news events CSV")

    # Symbol
    p.add_argument("--symbol", default="XAUUSD", help="Broker symbol name")

    # Verbosity
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    return p


# ---------------------------------------------------------------------------
# Output dispatch
# ---------------------------------------------------------------------------

def _render(result: ScanResult, fmt: str) -> str:
    if fmt == "compact":
        return format_compact(result)
    if fmt == "telegram":
        return format_telegram(result)
    if fmt == "json":
        return format_json(result)
    return format_report(result)


# ---------------------------------------------------------------------------
# Synthetic demo data for --mode scan without live MT5
# ---------------------------------------------------------------------------

_DEMO_BASE_PRICE = 2000.0
_DEMO_DRIFT = 0.3        # pts per bar — slight upward trend
_DEMO_VOLATILITY = 3.0   # std-dev of per-bar moves


def _make_demo_data(n_bars: int = 1500, seed: int = 42):
    """
    Generate synthetic trending OHLCV data for offline scanning.

    This is *only* for demonstration purposes when no real data source is
    connected. In MT5/paper mode the real bar data is supplied externally.
    """
    rng = np.random.default_rng(seed)
    closes = _DEMO_BASE_PRICE + np.cumsum(rng.normal(_DEMO_DRIFT, _DEMO_VOLATILITY, n_bars))
    opens  = closes - rng.normal(0, 1.5, n_bars)
    highs  = np.maximum(opens, closes) + rng.uniform(0.5, 3.0, n_bars)
    lows   = np.minimum(opens, closes) - rng.uniform(0.5, 3.0, n_bars)
    volumes = rng.uniform(100, 1000, n_bars)

    idx = pd.date_range(
        end=datetime.now(tz=timezone.utc).replace(second=0, microsecond=0),
        periods=n_bars,
        freq="1min",
        tz="UTC",
    )

    m1 = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=idx,
    )

    # Resample to M5
    m5 = m1.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    # Resample to M15
    m15 = m1.resample("15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    return m1, m5, m15


# ---------------------------------------------------------------------------
# Scan mode
# ---------------------------------------------------------------------------

def _run_scan(args: argparse.Namespace) -> None:
    config = ScannerConfig(
        symbol=args.symbol,
        only_a_plus=args.only_a_plus,
        output_format=args.output_format,
        mode="scan",
    )

    scanner = Scanner(config)
    m1, m5, m15 = _make_demo_data()

    extra = {
        "utc_hour": datetime.now(tz=timezone.utc).hour,
        "minutes_to_news": 999,
        "spread": 1.5,
    }

    result = scanner.scan(m1, m5, m15, extra=extra)

    if result is None:
        print("No qualifying setup found (A+ only mode active — result suppressed).")
        return

    print(_render(result, args.output_format))


# ---------------------------------------------------------------------------
# Backtest mode (stub — extend with real CSV loader)
# ---------------------------------------------------------------------------

def _run_backtest(args: argparse.Namespace) -> None:
    if not args.data:
        print("ERROR: --data is required for backtest mode", file=sys.stderr)
        sys.exit(1)

    config = ScannerConfig(
        symbol=args.symbol,
        only_a_plus=args.only_a_plus,
        output_format=args.output_format,
        mode="backtest",
        data_file=args.data,
        settings_file=args.settings,
        news_file=args.news,
    )

    print(f"Backtest mode: loading {args.data}")
    print("Backtest engine not yet connected — extend _run_backtest() with your loader.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.mode == "scan":
        _run_scan(args)
    elif args.mode == "backtest":
        _run_backtest(args)
    elif args.mode in ("paper", "mt5"):
        print(f"{args.mode.upper()} mode: connect MT5/paper broker adapter and call scanner.scan().")
    else:
        print(f"Unknown mode: {args.mode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
