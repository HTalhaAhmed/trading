from __future__ import annotations

import argparse
import json
import logging

from .backtest_runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="XAUUSD intraday research bot — backtest, paper, or MT5 mode"
    )
    parser.add_argument(
        "--data",
        default="data/sample_xauusd_1m.csv",
        help="Path to 1m OHLCV CSV (used in backtest and paper modes)",
    )
    parser.add_argument(
        "--settings",
        default="config/settings.yaml",
        help="Path to settings YAML",
    )
    parser.add_argument(
        "--news",
        default="config/news_calendar.yaml",
        help="Path to news calendar YAML",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to export trades/equity CSV (backtest mode only)",
    )
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper", "mt5"],
        default=None,
        help=(
            "Execution mode: backtest (default) | paper (CSV replay, simulated fills) "
            "| mt5 (live connection to MetaTrader 5 terminal). "
            "Overrides broker.mode in settings."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    return parser


def _resolve_mode(args: argparse.Namespace, settings: dict) -> str:
    if args.mode:
        return args.mode
    return settings.get("broker", {}).get("mode", "backtest")


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    from .config_loader import load_settings

    settings = load_settings(args.settings)
    mode = _resolve_mode(args, settings)

    if mode == "backtest":
        report = run(args.data, args.settings, args.news, args.output_dir)
        print(json.dumps(report, indent=2))

    elif mode == "paper":
        _run_paper(args, settings)

    elif mode == "mt5":
        _run_mt5(args, settings)

    else:
        raise ValueError(f"Unknown mode: {mode!r}")


def _run_paper(args: argparse.Namespace, settings: dict) -> None:
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _logger.info("Mode: paper replay from %s", args.data)

    from .broker.paper_broker import PaperBroker
    from .data_loader import load_ohlcv_csv
    from .live_runner import LiveRunner
    from .news_calendar import load_news_calendar

    df = load_ohlcv_csv(args.data)
    news_df = load_news_calendar(args.news)
    broker = PaperBroker(
        df,
        default_spread=float(settings["execution"]["spread_points"]),
    )

    if not broker.initialize():
        _logger.error("PaperBroker failed to initialize. Aborting.")
        return

    runner = LiveRunner(settings, broker, news_df)
    runner.run_paper_replay(broker)


def _run_mt5(args: argparse.Namespace, settings: dict) -> None:
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _logger.info("Mode: MT5 live connection")

    try:
        from .broker.mt5_adapter import MT5Adapter
    except Exception as exc:
        _logger.error("Cannot import MT5Adapter: %s", exc)
        return

    from .live_runner import LiveRunner
    from .news_calendar import load_news_calendar

    news_df = load_news_calendar(args.news)
    broker = MT5Adapter()

    if not broker.initialize():
        _logger.error("KILL-SWITCH: MT5 initialization failed. Aborting.")
        return

    runner = LiveRunner(settings, broker, news_df)
    runner.run_mt5_loop()


if __name__ == "__main__":
    main()
