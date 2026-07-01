from __future__ import annotations

from typing import Any

import pandas as pd

from .cost_model import apply_execution_costs
from .features import add_features
from .news_calendar import is_in_news_blackout
from .portfolio import PortfolioState, Position
from .regime import classify_regime
from .resampling import resample_ohlcv
from .risk_limits import RiskLimits
from .risk_sizing import position_size_from_risk
from .strategy_router import route_signal


def _in_trading_hours(ts: pd.Timestamp, settings: dict[str, Any]) -> bool:
    start, end = settings["sessions"]["trade_hours_utc"]
    return start <= ts.hour < end


def run_backtest(df_1m: pd.DataFrame, settings: dict[str, Any], news_df: pd.DataFrame | None = None) -> PortfolioState:
    news_df = news_df if news_df is not None else pd.DataFrame()
    f1 = add_features(df_1m)
    f5 = add_features(resample_ohlcv(df_1m, "5min"))
    f15 = add_features(resample_ohlcv(df_1m, "15min"))

    portfolio = PortfolioState(equity=float(settings["project"]["starting_equity"]))
    limits = RiskLimits(
        starting_equity=portfolio.equity,
        daily_max_loss_pct=float(settings["risk"]["daily_max_loss_pct"]),
        max_consecutive_losses=int(settings["risk"]["max_consecutive_losses"]),
    )

    for ts, row in f1.iterrows():
        limits.reset_day_if_needed(str(ts.date()))
        row_dict = row.to_dict()
        row5 = f5.loc[:ts].tail(1)
        row15 = f15.loc[:ts].tail(1)
        if not row5.empty:
            row_dict.update({f"5m_{k}": v for k, v in row5.iloc[0].to_dict().items()})
        if not row15.empty:
            row_dict.update({f"15m_{k}": v for k, v in row15.iloc[0].to_dict().items()})

        price = float(row["close"])
        portfolio.mark_to_market(ts.isoformat(), price)

        if portfolio.position:
            p = portfolio.position
            hit_stop = (p.side == "long" and row["low"] <= p.stop_price) or (p.side == "short" and row["high"] >= p.stop_price)
            hit_tp = (p.side == "long" and row["high"] >= p.take_profit_price) or (p.side == "short" and row["low"] <= p.take_profit_price)
            if hit_stop:
                pnl = portfolio.close_position(ts.isoformat(), p.stop_price, "stop")
                limits.record_trade(pnl)
            elif hit_tp:
                pnl = portfolio.close_position(ts.isoformat(), p.take_profit_price, "target")
                limits.record_trade(pnl)
            continue

        if not limits.can_trade() or not _in_trading_hours(ts, settings):
            continue

        if settings["news"]["enabled"]:
            impacts = set(settings["news"].get("impacts", []))
            if is_in_news_blackout(
                ts,
                news_df,
                int(settings["news"]["blackout_pre_minutes"]),
                int(settings["news"]["blackout_post_minutes"]),
                impacts,
            ):
                continue

        regime = classify_regime(row_dict, settings)
        signal = route_signal(regime, row_dict, settings)
        if not signal:
            continue

        atr_value = float(row_dict.get("atr_14", 0.0))
        if atr_value <= 0:
            continue

        side = signal["side"]
        spread = float(row.get("spread", settings["execution"]["spread_points"]))
        slippage = float(settings["execution"]["slippage_points"])

        stop_distance = atr_value * float(signal["stop_atr_mult"])
        direction = 1 if side == "long" else -1
        raw_entry = price
        raw_stop = raw_entry - stop_distance * direction
        raw_tp = raw_entry + (stop_distance * float(signal["take_profit_r"]) * direction)

        entry_price, _ = apply_execution_costs(raw_entry, raw_tp, side, spread, slippage)
        size = position_size_from_risk(
            equity=portfolio.equity,
            risk_pct=float(settings["risk"]["risk_per_trade"]),
            entry=entry_price,
            stop=raw_stop,
            contract_value_per_point=float(settings["risk"].get("contract_value_per_point", 1.0)),
        )
        if size <= 0:
            continue

        portfolio.open_position(
            Position(
                side=side,
                entry_price=entry_price,
                stop_price=raw_stop,
                take_profit_price=raw_tp,
                size=size,
                entry_time=ts.isoformat(),
            )
        )

    if portfolio.position:
        last_ts = f1.index[-1]
        last_close = float(f1.iloc[-1]["close"])
        pnl = portfolio.close_position(last_ts.isoformat(), last_close, "session_close")
        limits.record_trade(pnl)

    return portfolio
