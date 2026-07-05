"""Build a ScanContext from existing trading_bot data structures.

This bridges the scanner to the existing regime / strategy / features pipeline
so it can be called from the backtest engine, live runner, and CLI without
duplicating feature computation.
"""
from __future__ import annotations

import math
from typing import Any

from .models import ScanContext


def build_scan_context(
    row: dict[str, float],
    regime: str,
    raw_signal: dict[str, Any] | None,
    *,
    htf_trend: str = "neutral",
    session: str = "london",
    hour_utc: int = 10,
    spread_points: float = 0.0,
    recent_losses: int = 0,
    cooldown_remaining_minutes: int = 0,
    daily_loss_pct: float = 0.0,
    is_news_blackout: bool = False,
    minutes_since_news: int = 999,
    price_above_ema50_bars: int = 0,
    body_to_range_ratio: float = 0.5,
    volume_ratio: float = 1.0,
) -> ScanContext:
    """Construct a :class:`ScanContext` from a feature row dict.

    Parameters
    ----------
    row:
        Dict of feature values (output of :func:`trading_bot.features.add_features`).
    regime:
        Market regime string from :func:`trading_bot.regime.classify_regime`.
    raw_signal:
        Raw signal dict from :func:`trading_bot.strategy_router.route_signal`,
        or ``None`` if no signal was generated.
    **kwargs:
        All other fields are passed directly; see :class:`ScanContext`.
    """
    def _f(key: str, default: float = 0.0) -> float:
        val = row.get(key, default)
        return float(val) if val is not None and not (isinstance(val, float) and math.isnan(val)) else default

    return ScanContext(
        close=_f("close"),
        ema_20=_f("ema_20"),
        ema_50=_f("ema_50"),
        atr_14=_f("atr_14"),
        adx_14=_f("adx_14"),
        rsi_14=_f("rsi_14", 50.0),
        session_vwap=_f("session_vwap", _f("close")),
        htf_trend=htf_trend,
        session=session,
        hour_utc=hour_utc,
        spread_points=spread_points,
        recent_losses=recent_losses,
        cooldown_remaining_minutes=cooldown_remaining_minutes,
        daily_loss_pct=daily_loss_pct,
        is_news_blackout=is_news_blackout,
        minutes_since_news=minutes_since_news,
        regime=regime,
        raw_signal=raw_signal,
        price_above_ema50_bars=price_above_ema50_bars,
        body_to_range_ratio=body_to_range_ratio,
        volume_ratio=volume_ratio,
    )
