from __future__ import annotations

import argparse
import json

from .config import TradingConfig
from .models import PerformanceMetrics, SignalContext
from .engine import TradeEngine
from .reporting import summarize_gate_status, summarize_signal_quality
from .signal_quality import assess_signal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Selective XAUUSD trading research CLI")
    parser.add_argument("--config", default=None, help="Path to JSON config")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one signal evaluation")
    run.add_argument("--mode", choices=["backtest", "paper", "mt5"], default=None)
    run.add_argument("--trade-enabled", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = TradingConfig.load(args.config)

    if args.command == "run":
        if args.mode:
            cfg.mode.mode = args.mode
        if args.trade_enabled:
            cfg.mode.trade_enabled = True

        engine = TradeEngine(cfg)
        signal = SignalContext(
            direction="buy",
            htf_direction="buy",
            session="london",
            atr_normalized=1.1,
            spread_points=20,
            room_to_target_atr=1.5,
            trigger_candle_atr_ratio=1.0,
        )
        metrics = PerformanceMetrics(
            forward_trades=40,
            max_drawdown=0.08,
            profit_factor=1.3,
            expectancy_r=0.12,
            recent_underperformance=False,
        )
        can_trade, reasons, gate_status = engine.evaluate(signal, metrics)
        quality = assess_signal(signal, cfg.quality, cfg.filters, cfg.weights, cfg.mode.mode)
        output = {
            "mode": cfg.mode.mode,
            "trade_enabled": cfg.mode.trade_enabled,
            "can_trade": can_trade,
            "blocked_reasons": reasons,
            "quality": summarize_signal_quality([quality]),
            "gates": summarize_gate_status(gate_status),
            "warning": "No profitability is promised; use defensive risk and demo validation first.",
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
