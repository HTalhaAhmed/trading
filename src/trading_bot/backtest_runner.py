from __future__ import annotations

from pathlib import Path
from typing import Any

from .backtest_engine import run_backtest
from .config_loader import load_settings
from .data_loader import load_ohlcv_csv
from .news_calendar import load_news_calendar
from .report import build_performance_report, export_backtest_outputs


def run(
    data_path: str | Path,
    settings_path: str | Path,
    news_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    settings = load_settings(settings_path)
    df = load_ohlcv_csv(data_path)
    news_df = load_news_calendar(news_path)

    portfolio = run_backtest(df, settings, news_df)
    report = build_performance_report(portfolio)

    if output_dir:
        trades_path, equity_path = export_backtest_outputs(portfolio, output_dir)
        report["trades_csv"] = str(trades_path)
        report["equity_csv"] = str(equity_path)

    return report
