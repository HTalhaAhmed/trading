from __future__ import annotations

import argparse
import json
import logging

from .backtest_runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="XAUUSD intraday research bot — backtest, paper, MT5, or scan mode"
    )
    parser.add_argument(
        "--data",
        default="data/sample_xauusd_1m.csv",
        help="Path to 1m OHLCV CSV (used in backtest, paper, and scan modes)",
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
        choices=["backtest", "paper", "mt5", "scan"],
        default=None,
        help=(
            "Execution mode: backtest (default) | paper (CSV replay, simulated fills) "
            "| mt5 (live connection to MetaTrader 5 terminal) "
            "| scan (grade the latest setup from the CSV and print the report). "
            "Overrides broker.mode in settings."
        ),
    )
    parser.add_argument(
        "--only-a-plus",
        action="store_true",
        default=None,
        help="Override scanner.only_a_plus: surface only A+ setups",
    )
    parser.add_argument(
        "--scan-json",
        action="store_true",
        help="In scan mode, output the result as JSON instead of the formatted report",
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

    # Apply CLI overrides to scanner config
    if args.only_a_plus:
        settings.setdefault("scanner", {})["only_a_plus"] = True

    mode = _resolve_mode(args, settings)

    if mode == "backtest":
        report = run(args.data, args.settings, args.news, args.output_dir)
        print(json.dumps(report, indent=2))

    elif mode == "scan":
        _run_scan(args, settings)

    elif mode == "paper":
        _run_paper(args, settings)

    elif mode == "mt5":
        _run_mt5(args, settings)

    else:
        raise ValueError(f"Unknown mode: {mode!r}")


def _run_scan(args: argparse.Namespace, settings: dict) -> None:
    """Grade the latest setup from the CSV and print the scan report."""
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _logger.info("Mode: scan — grading latest setup from %s", args.data)

    from .config_loader import load_settings
    from .data_loader import load_ohlcv_csv
    from .features import add_features
    from .news_calendar import is_in_news_blackout, load_news_calendar
    from .regime import classify_regime
    from .resampling import resample_ohlcv
    from .scanner import build_scan_context, grade_setup
    from .strategy_router import route_signal

    df = load_ohlcv_csv(args.data)
    news_df = load_news_calendar(args.news)
    scfg = settings.get("scanner", {})

    f1 = add_features(df)
    f5 = add_features(resample_ohlcv(df, "5min"))
    f15 = add_features(resample_ohlcv(df, "15min"))

    # Use the last row as the "current" bar
    ts = f1.index[-1]
    row_dict = f1.iloc[-1].to_dict()
    row5 = f5.loc[:ts].tail(1)
    row15 = f15.loc[:ts].tail(1)
    if not row5.empty:
        row_dict.update({f"5m_{k}": v for k, v in row5.iloc[0].to_dict().items()})
    if not row15.empty:
        row_dict.update({f"15m_{k}": v for k, v in row15.iloc[0].to_dict().items()})

    is_news_bk = False
    if settings["news"]["enabled"]:
        impacts = set(settings["news"].get("impacts", []))
        is_news_bk = is_in_news_blackout(
            ts,
            news_df,
            int(settings["news"]["blackout_pre_minutes"]),
            int(settings["news"]["blackout_post_minutes"]),
            impacts,
        )

    regime = classify_regime(row_dict, settings)
    signal = route_signal(regime, row_dict, settings)

    only_a_plus = bool(scfg.get("only_a_plus", False))
    scan_ctx = build_scan_context(
        row_dict,
        regime,
        signal,
        session="london" if 7 <= ts.hour < 12 else "new_york" if 12 <= ts.hour < 16 else "off",
        hour_utc=ts.hour,
        spread_points=float(settings["execution"]["spread_points"]),
        is_news_blackout=is_news_bk,
    )
    result = grade_setup(scan_ctx, only_a_plus=only_a_plus)

    if args.scan_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.report())


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
