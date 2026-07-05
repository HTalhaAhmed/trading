from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .portfolio import PortfolioState


def _max_drawdown(equity_series: pd.Series) -> float:
    running_max = equity_series.cummax()
    drawdown = equity_series - running_max
    return float(drawdown.min()) if not drawdown.empty else 0.0


def build_performance_report(portfolio: PortfolioState) -> dict[str, Any]:
    trades_df = pd.DataFrame([t.__dict__ for t in portfolio.trades])
    equity_df = pd.DataFrame(portfolio.equity_curve)

    total_trades = len(trades_df)
    wins = trades_df[trades_df["pnl"] > 0] if total_trades else pd.DataFrame(columns=["pnl"])
    losses = trades_df[trades_df["pnl"] < 0] if total_trades else pd.DataFrame(columns=["pnl"])

    gross_profit = float(wins["pnl"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["pnl"].sum())) if not losses.empty else 0.0

    return {
        "total_trades": total_trades,
        "win_rate": float(len(wins) / total_trades) if total_trades else 0.0,
        "net_pnl": float(trades_df["pnl"].sum()) if total_trades else 0.0,
        "ending_equity": float(portfolio.equity),
        "max_drawdown": _max_drawdown(equity_df["equity"]) if not equity_df.empty else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else 0.0,
        "average_win": float(wins["pnl"].mean()) if not wins.empty else 0.0,
        "average_loss": float(losses["pnl"].mean()) if not losses.empty else 0.0,
    }


def export_backtest_outputs(portfolio: PortfolioState, output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades_path = out / "trades.csv"
    equity_path = out / "equity_curve.csv"

    pd.DataFrame([t.__dict__ for t in portfolio.trades]).to_csv(trades_path, index=False)
    pd.DataFrame(portfolio.equity_curve).to_csv(equity_path, index=False)
    return trades_path, equity_path
