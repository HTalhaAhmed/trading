"""Data models for the trade scanner and setup grader."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReviewerResult:
    """Output from one reviewer in the multi-reviewer framework.

    Each reviewer scores a specific aspect of the trade setup and returns
    a numeric contribution, pass/fail checks, and human-readable reasons.
    """

    name: str
    """Reviewer name, e.g. 'TrendReviewer'."""

    score: float
    """Points awarded by this reviewer (0.0 – max_score)."""

    max_score: float
    """Maximum points this reviewer can award."""

    reasons: list[str] = field(default_factory=list)
    """Confluences and positive factors found by this reviewer."""

    cautions: list[str] = field(default_factory=list)
    """Warnings or concerns (does not necessarily block the trade)."""

    blockers: list[str] = field(default_factory=list)
    """Hard-stop conditions that make the trade invalid."""

    @property
    def pct(self) -> float:
        """Score as a fraction of max_score (0.0–1.0)."""
        return self.score / self.max_score if self.max_score > 0 else 0.0


@dataclass
class ScanContext:
    """All market data and state required by the scanner."""

    # --- Price / feature values ---
    close: float
    ema_20: float
    ema_50: float
    atr_14: float
    adx_14: float
    rsi_14: float
    session_vwap: float

    # --- Higher-timeframe bias (e.g. 15m / 1h trend direction) ---
    htf_trend: str = "neutral"  # "up" | "down" | "neutral"

    # --- Session / time context ---
    session: str = "london"  # "london" | "new_york" | "asian" | "off"
    hour_utc: int = 10

    # --- Execution quality ---
    spread_points: float = 0.0
    """Current bid/ask spread in price points."""

    # --- Risk / drawdown context ---
    recent_losses: int = 0
    """Number of losses in the recent lookback window."""

    cooldown_remaining_minutes: int = 0
    """Minutes remaining in a post-loss cooldown window."""

    daily_loss_pct: float = 0.0
    """Day's unrealised + realised loss as % of starting equity."""

    # --- News / event context ---
    is_news_blackout: bool = False
    """True when inside a pre/post-news blackout window."""

    minutes_since_news: int = 999
    """Minutes since the last high-impact news event."""

    # --- Signal context ---
    regime: str = "neutral"
    """Market regime: 'trending' | 'ranging' | 'high_vol' | 'neutral'."""

    raw_signal: dict[str, Any] | None = None
    """Raw signal dict from the strategy router, if any."""

    # --- Lookback statistics ---
    price_above_ema50_bars: int = 0
    """Number of recent bars where close > EMA-50 (momentum proxy)."""

    body_to_range_ratio: float = 0.5
    """Last candle body / full range (execution quality proxy)."""

    volume_ratio: float = 1.0
    """Current bar volume / 20-bar average volume."""
