from __future__ import annotations

import argparse
import json
import sys

from trading_bot.alerts import format_board, format_compact, trade_idea_to_dict
from trading_bot.caps import CapsManager
from trading_bot.config import load_config
from trading_bot.logger import ScanLogger
from trading_bot.mt5_client import MT5Client
from trading_bot.scanner import MT5Scanner


def main():
    parser = argparse.ArgumentParser(description="MT5 alert-only decision-support trading bot")
    parser.add_argument("--mode", default="mt5_alert", choices=["mt5_alert", "scan", "backtest"])
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--symbol")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--format", default="report", choices=["report", "compact", "json"])
    parser.add_argument("--only-a-plus", action="store_true")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--data")
    args = parser.parse_args()

    config = load_config(args.config)

    if config["broker"]["trade_enabled"]:
        print("WARNING: trade_enabled is True. Auto-execution is NOT supported in this version.")
        print("Setting trade_enabled = False for safety.")
        config["broker"]["trade_enabled"] = False

    if args.only_a_plus:
        config["scanner"]["only_a_plus"] = True

    if args.mode in {"mt5_alert", "scan"}:
        if args.symbol:
            config["broker"]["watchlist"] = [args.symbol]

        mt5_client = MT5Client(mock=args.mock)
        if not mt5_client.connect():
            print("ERROR: Could not connect to MT5.")
            if not args.mock:
                print("Hint: use --mock for testing without MT5.")
            sys.exit(1)

        caps = CapsManager(config)
        logger = ScanLogger(config["logging"]["log_dir"])
        scanner = MT5Scanner(config, mt5_client, caps, logger)

        if args.once:
            result = scanner.scan_all()
            if args.format == "json":
                print(
                    json.dumps(
                        {
                            "cycle_id": result.cycle_id,
                            "timestamp": result.timestamp,
                            "session": result.session,
                            "surfaced": [trade_idea_to_dict(item) for item in result.surfaced],
                            "suppressed": [
                                {
                                    "symbol": item.get("symbol"),
                                    "grade": getattr(item.get("grade_result"), "grade", None),
                                    "score": getattr(item.get("grade_result"), "score", None),
                                    "blockers": getattr(item.get("grade_result"), "blockers", []),
                                }
                                for item in result.suppressed
                            ],
                            "errors": result.errors,
                        },
                        default=str,
                    )
                )
            elif args.format == "compact":
                if result.surfaced:
                    print("\n".join(format_compact(item) for item in result.surfaced))
                else:
                    print(format_board(result.surfaced, result.suppressed))
            else:
                print(format_board(result.surfaced, result.suppressed))
            logger.close()
            mt5_client.disconnect()
        else:
            scanner.run_continuous()

    elif args.mode == "backtest":
        print("Backtest mode: not yet implemented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
