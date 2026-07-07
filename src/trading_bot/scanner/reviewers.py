"""
Multi-reviewer scoring engine.

Each reviewer inspects a different quality dimension and returns a
ReviewResult containing:
  - score        integer points earned
  - max_score    maximum possible points for this reviewer
  - passed       True when the reviewer's own minimum threshold was met
  - reasons      list of positive findings
  - cautions     list of warnings that did not block but hurt quality
  - blockers     list of hard-fail conditions (force grade to REJECTED)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import ReviewerConfig, GradeThresholds


# ---------------------------------------------------------------------------
# Review result
# ---------------------------------------------------------------------------

@dataclass
class ReviewResult:
    reviewer_name: str
    score: int = 0
    max_score: int = 0
    passed: bool = False
    reasons: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    @property
    def score_pct(self) -> float:
        if self.max_score == 0:
            return 0.0
        return round(100 * self.score / self.max_score, 1)


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hi = df["high"]
    lo = df["low"]
    cl = df["close"]
    tr = pd.concat(
        [hi - lo, (hi - cl.shift()).abs(), (lo - cl.shift()).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _macd(series: pd.Series, fast: int, slow: int, signal: int):
    fast_ema = _ema(series, fast)
    slow_ema = _ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ---------------------------------------------------------------------------
# Base reviewer
# ---------------------------------------------------------------------------

class _BaseReviewer:
    name: str = "base"
    max_score: int = 0

    def __init__(
        self,
        cfg: ReviewerConfig,
        grade_cfg: GradeThresholds,
    ) -> None:
        self.cfg = cfg
        self.grade_cfg = grade_cfg

    # Subclasses implement this
    def review(
        self,
        m1: pd.DataFrame,
        m5: pd.DataFrame,
        m15: pd.DataFrame,
        direction: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ReviewResult:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# TrendReviewer  (max 25)
# ---------------------------------------------------------------------------

class TrendReviewer(_BaseReviewer):
    """
    Scores higher-timeframe trend alignment and price structure.

    Points:
      HTF (M15) EMA alignment    0–10
      MTF (M5) EMA alignment     0–8
      Price structure quality    0–7
    Max: 25
    """

    name = "Trend"
    max_score = 25

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0
        is_long = direction == "LONG"

        # ---- HTF M15 EMA alignment (0-10) ----
        if len(m15) >= cfg.ema_200:
            e9  = _ema(m15["close"], cfg.ema_fast).iloc[-1]
            e21 = _ema(m15["close"], cfg.ema_mid).iloc[-1]
            e50 = _ema(m15["close"], cfg.ema_slow).iloc[-1]
            e200 = _ema(m15["close"], cfg.ema_200).iloc[-1]
            price = m15["close"].iloc[-1]

            # Full bull stack
            if is_long:
                if e9 > e21 > e50 > e200 and price > e9:
                    score += 10
                    res.reasons.append("M15 full bull EMA stack confirmed (9>21>50>200)")
                elif e9 > e21 > e50 and price > e21:
                    score += 7
                    res.reasons.append("M15 partial bull EMA stack (9>21>50)")
                elif price > e50:
                    score += 4
                    res.reasons.append("M15 price above EMA50 — mild bull bias")
                else:
                    res.cautions.append("M15 EMA structure not bullish — weak HTF support")
            else:  # SHORT
                if e9 < e21 < e50 < e200 and price < e9:
                    score += 10
                    res.reasons.append("M15 full bear EMA stack confirmed (9<21<50<200)")
                elif e9 < e21 < e50 and price < e21:
                    score += 7
                    res.reasons.append("M15 partial bear EMA stack (9<21<50)")
                elif price < e50:
                    score += 4
                    res.reasons.append("M15 price below EMA50 — mild bear bias")
                else:
                    res.cautions.append("M15 EMA structure not bearish — weak HTF support")
        else:
            e50 = _ema(m15["close"], cfg.ema_slow).iloc[-1]
            price = m15["close"].iloc[-1]
            if (is_long and price > e50) or (not is_long and price < e50):
                score += 4
                res.reasons.append("M15 price on correct side of EMA50")
            else:
                res.cautions.append("Insufficient M15 history for full EMA analysis")

        # ---- MTF M5 EMA alignment (0-8) ----
        if len(m5) >= cfg.ema_slow:
            e9m  = _ema(m5["close"], cfg.ema_fast).iloc[-1]
            e21m = _ema(m5["close"], cfg.ema_mid).iloc[-1]
            e50m = _ema(m5["close"], cfg.ema_slow).iloc[-1]
            pm5  = m5["close"].iloc[-1]

            if is_long:
                if e9m > e21m > e50m and pm5 > e9m:
                    score += 8
                    res.reasons.append("M5 bull EMA stack with price above all EMAs")
                elif e9m > e21m and pm5 > e21m:
                    score += 5
                    res.reasons.append("M5 EMA9 above EMA21 — bullish momentum")
                elif pm5 > e50m:
                    score += 2
                    res.reasons.append("M5 price above EMA50")
                else:
                    res.cautions.append("M5 EMA structure not supportive of long")
            else:
                if e9m < e21m < e50m and pm5 < e9m:
                    score += 8
                    res.reasons.append("M5 bear EMA stack with price below all EMAs")
                elif e9m < e21m and pm5 < e21m:
                    score += 5
                    res.reasons.append("M5 EMA9 below EMA21 — bearish momentum")
                elif pm5 < e50m:
                    score += 2
                    res.reasons.append("M5 price below EMA50")
                else:
                    res.cautions.append("M5 EMA structure not supportive of short")

        # ---- Price structure: HH/HL or LH/LL (0-7) ----
        if len(m15) >= 6:
            highs = m15["high"].iloc[-6:]
            lows  = m15["low"].iloc[-6:]
            last_high = highs.iloc[-1]
            prev_high = highs.iloc[-3]
            last_low  = lows.iloc[-1]
            prev_low  = lows.iloc[-3]

            if is_long and last_high > prev_high and last_low > prev_low:
                score += 7
                res.reasons.append("M15 higher-highs / higher-lows structure intact")
            elif is_long and last_low > prev_low:
                score += 4
                res.reasons.append("M15 higher-lows present — bullish structure building")
            elif not is_long and last_high < prev_high and last_low < prev_low:
                score += 7
                res.reasons.append("M15 lower-highs / lower-lows structure intact")
            elif not is_long and last_high < prev_high:
                score += 4
                res.reasons.append("M15 lower-highs present — bearish structure building")
            else:
                res.cautions.append("Price structure unclear / choppy on M15")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_trend_min
        return res


# ---------------------------------------------------------------------------
# MomentumReviewer  (max 20)
# ---------------------------------------------------------------------------

class MomentumReviewer(_BaseReviewer):
    """
    Scores momentum quality: RSI, MACD, and candle body.

    Points:
      RSI alignment             0–5
      MACD histogram            0–5
      Candle body / impulse     0–5
      Volume confirmation       0–5
    Max: 20
    """

    name = "Momentum"
    max_score = 20

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0
        is_long = direction == "LONG"

        # ---- RSI (0-5) ----
        if len(m5) >= cfg.rsi_period + 5:
            rsi = _rsi(m5["close"], cfg.rsi_period).iloc[-1]
            if is_long:
                if 55 <= rsi <= 70:
                    score += 5
                    res.reasons.append(f"M5 RSI {rsi:.0f} in bullish momentum zone (55-70)")
                elif 50 <= rsi < 55:
                    score += 3
                    res.reasons.append(f"M5 RSI {rsi:.0f} above 50 — mild bullish bias")
                elif rsi > cfg.rsi_overbought:
                    score += 1
                    res.cautions.append(f"M5 RSI {rsi:.0f} overbought — reversal risk")
                else:
                    res.cautions.append(f"M5 RSI {rsi:.0f} below 50 — momentum not with longs")
            else:
                if 30 <= rsi <= 45:
                    score += 5
                    res.reasons.append(f"M5 RSI {rsi:.0f} in bearish momentum zone (30-45)")
                elif 45 < rsi <= 50:
                    score += 3
                    res.reasons.append(f"M5 RSI {rsi:.0f} below 50 — mild bearish bias")
                elif rsi < cfg.rsi_oversold:
                    score += 1
                    res.cautions.append(f"M5 RSI {rsi:.0f} oversold — snap-back risk")
                else:
                    res.cautions.append(f"M5 RSI {rsi:.0f} above 50 — momentum not with shorts")

        # ---- MACD histogram (0-5) ----
        if len(m5) >= cfg.macd_slow + cfg.macd_signal + 5:
            _, _, hist = _macd(m5["close"], cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
            h = hist.iloc[-1]
            h_prev = hist.iloc[-2]
            if is_long:
                if h > 0 and h > h_prev:
                    score += 5
                    res.reasons.append("M5 MACD histogram positive and expanding")
                elif h > 0:
                    score += 3
                    res.reasons.append("M5 MACD histogram positive")
                elif h_prev < 0 and h > h_prev:
                    score += 2
                    res.reasons.append("M5 MACD histogram turning up from negative")
                else:
                    res.cautions.append("M5 MACD histogram negative — not confirming long")
            else:
                if h < 0 and h < h_prev:
                    score += 5
                    res.reasons.append("M5 MACD histogram negative and expanding")
                elif h < 0:
                    score += 3
                    res.reasons.append("M5 MACD histogram negative")
                elif h_prev > 0 and h < h_prev:
                    score += 2
                    res.reasons.append("M5 MACD histogram turning down from positive")
                else:
                    res.cautions.append("M5 MACD histogram positive — not confirming short")

        # ---- Candle body / impulse (0-5) ----
        if len(m5) >= 3:
            last = m5.iloc[-1]
            body = abs(last["close"] - last["open"])
            candle_range = last["high"] - last["low"]
            body_ratio = body / candle_range if candle_range > 0 else 0

            if is_long and last["close"] > last["open"]:
                if body_ratio >= 0.7:
                    score += 5
                    res.reasons.append(f"Strong bull close on M5 (body {body_ratio:.0%} of range)")
                elif body_ratio >= 0.5:
                    score += 3
                    res.reasons.append(f"Decent bull close on M5 (body {body_ratio:.0%} of range)")
                else:
                    score += 1
                    res.cautions.append("M5 close bullish but small body — weak conviction")
            elif not is_long and last["close"] < last["open"]:
                if body_ratio >= 0.7:
                    score += 5
                    res.reasons.append(f"Strong bear close on M5 (body {body_ratio:.0%} of range)")
                elif body_ratio >= 0.5:
                    score += 3
                    res.reasons.append(f"Decent bear close on M5 (body {body_ratio:.0%} of range)")
                else:
                    score += 1
                    res.cautions.append("M5 close bearish but small body — weak conviction")
            else:
                res.cautions.append("Last M5 candle closed against direction — no impulse confirmation")

        # ---- Volume (0-5) — only if volume column has meaningful data ----
        if "volume" in m5.columns and m5["volume"].iloc[-5:].sum() > 0:
            avg_vol = m5["volume"].iloc[-20:].mean()
            last_vol = m5["volume"].iloc[-1]
            if last_vol >= avg_vol * 1.5:
                score += 5
                res.reasons.append(f"Volume surge on signal bar ({last_vol / avg_vol:.1f}× average)")
            elif last_vol >= avg_vol * 1.1:
                score += 3
                res.reasons.append("Above-average volume supports signal")
            elif last_vol < avg_vol * 0.7:
                res.cautions.append("Below-average volume — low conviction")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_momentum_min
        return res


# ---------------------------------------------------------------------------
# VolatilityReviewer  (max 15)
# ---------------------------------------------------------------------------

class VolatilityReviewer(_BaseReviewer):
    """
    Scores volatility regime health.

    Points:
      ATR in healthy range      0–10
      No extreme spike          0–5
    Max: 15
    """

    name = "Volatility"
    max_score = 15

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0

        if len(m5) >= 15:
            atr_series = _atr(m5)
            atr = atr_series.iloc[-1]
            atr_avg = atr_series.iloc[-20:].mean() if len(m5) >= 20 else atr

            # ATR healthy range
            if cfg.min_atr_points <= atr <= cfg.max_atr_points * 0.6:
                score += 10
                res.reasons.append(f"ATR {atr:.1f} pts — healthy volatility regime")
            elif cfg.min_atr_points <= atr <= cfg.max_atr_points:
                score += 6
                res.reasons.append(f"ATR {atr:.1f} pts — acceptable volatility")
            elif atr < cfg.min_atr_points:
                score += 2
                res.cautions.append(f"ATR {atr:.1f} pts — dead market, spread consumes edge")
            else:
                res.blockers.append(f"ATR {atr:.1f} pts — extremely high volatility, not tradeable")

            # Spike check
            if atr > 0 and atr_avg > 0:
                spike_ratio = atr / atr_avg
                if spike_ratio <= 1.5:
                    score += 5
                    res.reasons.append(f"ATR stable (ratio vs 20-bar avg: {spike_ratio:.2f})")
                elif spike_ratio <= 2.5:
                    score += 2
                    res.cautions.append(f"ATR elevated vs 20-bar avg ({spike_ratio:.2f}×) — use caution")
                else:
                    res.blockers.append(f"ATR spike {spike_ratio:.2f}× average — abnormal market")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_volatility_min
        return res


# ---------------------------------------------------------------------------
# ExecutionReviewer  (max 15)
# ---------------------------------------------------------------------------

class ExecutionReviewer(_BaseReviewer):
    """
    Scores entry execution quality: spread, room to target, timing.

    Points:
      Spread acceptable         0–5
      Room to target            0–5
      Entry timing quality      0–5
    Max: 15
    """

    name = "Execution"
    max_score = 15

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0
        extra = extra or {}

        # ---- Spread (0-5) ----
        spread = extra.get("spread", 0.0)
        if spread == 0.0:
            # Estimate from recent M1 data if available
            if "spread" in m1.columns and len(m1) >= 3:
                spread = m1["spread"].iloc[-3:].mean()

        if spread > cfg.max_spread_points:
            res.blockers.append(
                f"Spread {spread:.1f} pts exceeds hard limit {cfg.max_spread_points:.1f} pts"
            )
        elif spread > cfg.warn_spread_points:
            score += 2
            res.cautions.append(f"Spread {spread:.1f} pts — above warning threshold, size down")
        elif spread > 0:
            score += 5
            res.reasons.append(f"Spread {spread:.1f} pts — acceptable")
        else:
            # No spread data — partial credit
            score += 3
            res.reasons.append("Spread data unavailable — assuming acceptable")

        # ---- Room to target (0-5) ----
        room_r = extra.get("room_r", 0.0)
        if room_r == 0.0 and "entry" in extra and "stop" in extra and "target" in extra:
            entry = extra["entry"]
            stop = extra["stop"]
            target = extra["target"]
            risk = abs(entry - stop)
            if risk > 0:
                room_r = abs(target - entry) / risk

        if room_r == 0.0:
            # Estimate from ATR if available
            if len(m5) >= 15:
                atr = _atr(m5).iloc[-1]
                last_close = m5["close"].iloc[-1]
                # Use 2× ATR as estimated room
                room_r = 2.0
                res.cautions.append("Room to target estimated (no explicit target provided)")

        # Partial credit scale: 0–4 points proportional to how close room_r is to minimum.
        _MAX_PARTIAL_ROOM_CREDIT = 4
        if room_r >= cfg.min_room_to_target_r:
            score += 5
            res.reasons.append(f"Room to target {room_r:.1f}R — strong potential")
        elif room_r >= cfg.hard_block_room_r:
            ratio_score = int(
                _MAX_PARTIAL_ROOM_CREDIT
                * (room_r - cfg.hard_block_room_r)
                / (cfg.min_room_to_target_r - cfg.hard_block_room_r)
            )
            score += max(0, ratio_score)
            res.cautions.append(f"Room to target {room_r:.1f}R — below ideal {cfg.min_room_to_target_r:.1f}R")
        else:
            res.blockers.append(
                f"Room to target {room_r:.1f}R — below hard minimum {cfg.hard_block_room_r:.1f}R"
            )

        # ---- Entry timing quality (0-5) ----
        # Score based on how close we are to a pullback entry vs chasing
        if len(m1) >= 5:
            last_close = m1["close"].iloc[-1]
            e9_m1 = _ema(m1["close"], 9).iloc[-1]
            e21_m1 = _ema(m1["close"], 21).iloc[-1]
            is_long = direction == "LONG"

            # Good entry: price near value area (EMA9-EMA21 band), not fully extended
            spread_emas = abs(e9_m1 - e21_m1)
            dist_from_e21 = last_close - e21_m1 if is_long else e21_m1 - last_close

            if spread_emas > 0 and 0 <= dist_from_e21 <= 2 * spread_emas:
                score += 5
                res.reasons.append("Entry near value area (EMA9-21 band) — quality pullback timing")
            elif 0 <= dist_from_e21:
                score += 3
                res.reasons.append("Entry on correct side of EMA21")
            elif dist_from_e21 < 0:
                score += 1
                res.cautions.append("Entry slightly below EMA21 (long) or above (short) — borderline")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_execution_min
        return res


# ---------------------------------------------------------------------------
# RiskReviewer  (max 15)
# ---------------------------------------------------------------------------

class RiskReviewer(_BaseReviewer):
    """
    Scores risk/reward quality and stop placement.

    Points:
      R:R ratio quality         0–8
      Stop placement quality    0–7
    Max: 15
    """

    name = "Risk"
    max_score = 15

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0
        extra = extra or {}

        rr = extra.get("rr", 0.0)
        if rr == 0.0:
            rr = extra.get("room_r", 0.0)
        if rr == 0.0 and len(m5) >= 15:
            rr = cfg.min_rr_ratio  # default assumption

        # ---- R:R ratio (0-8) ----
        if rr < cfg.hard_block_rr_ratio:
            res.blockers.append(
                f"R:R {rr:.1f} below hard minimum {cfg.hard_block_rr_ratio:.1f} — no edge"
            )
        elif rr >= 3.0:
            score += 8
            res.reasons.append(f"Excellent R:R ratio {rr:.1f}:1")
        elif rr >= cfg.min_rr_ratio:
            score += 6
            res.reasons.append(f"Good R:R ratio {rr:.1f}:1")
        elif rr >= 1.5:
            score += 3
            res.cautions.append(f"R:R ratio {rr:.1f}:1 — below ideal {cfg.min_rr_ratio:.1f}")
        else:
            score += 1
            res.cautions.append(f"R:R ratio {rr:.1f}:1 — marginal")

        # ---- Stop placement quality (0-7) ----
        # Check that stop is beyond a meaningful structure level (ATR-based)
        if len(m5) >= 15 and "stop_distance" in extra:
            atr = _atr(m5).iloc[-1]
            stop_dist = extra["stop_distance"]
            if stop_dist >= atr * 1.5:
                score += 7
                res.reasons.append(f"Stop at {stop_dist:.1f} pts — beyond 1.5× ATR, structurally sound")
            elif stop_dist >= atr * 0.8:
                score += 5
                res.reasons.append(f"Stop at {stop_dist:.1f} pts — within ATR range")
            elif stop_dist >= atr * 0.5:
                score += 2
                res.cautions.append(f"Stop at {stop_dist:.1f} pts — tight, could be stopped prematurely")
            else:
                score += 1
                res.cautions.append(f"Stop at {stop_dist:.1f} pts — very tight, high stop-out risk")
        elif len(m5) >= 15:
            # No explicit stop provided — give partial credit
            score += 4
            res.cautions.append("Stop distance not provided — using estimated ATR-based stop quality")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_risk_min
        return res


# ---------------------------------------------------------------------------
# SessionReviewer  (max 10)
# ---------------------------------------------------------------------------

class SessionReviewer(_BaseReviewer):
    """
    Scores session and news context.

    Points:
      Tradeable session         0–5
      No news blackout          0–3
      Not at session extremes   0–2
    Max: 10
    """

    name = "Session"
    max_score = 10

    def review(self, m1, m5, m15, direction, extra=None):
        cfg = self.cfg
        res = ReviewResult(reviewer_name=self.name, max_score=self.max_score)
        score = 0
        extra = extra or {}

        utc_hour = extra.get("utc_hour", None)
        if utc_hour is None and len(m1) > 0 and isinstance(m1.index, pd.DatetimeIndex):
            utc_hour = m1.index[-1].hour

        # ---- Session quality (0-5) ----
        if utc_hour is not None:
            london = cfg.london_open <= utc_hour < cfg.london_close
            newyork = cfg.new_york_open <= utc_hour < cfg.new_york_close
            overlap = cfg.london_ny_overlap_start <= utc_hour < cfg.london_ny_overlap_end

            if overlap:
                score += 5
                res.reasons.append(f"London/NY overlap session (UTC {utc_hour:02d}:xx) — highest liquidity")
            elif london:
                score += 4
                res.reasons.append(f"London session (UTC {utc_hour:02d}:xx) — good liquidity")
            elif newyork:
                score += 4
                res.reasons.append(f"New York session (UTC {utc_hour:02d}:xx) — good liquidity")
            else:
                score += 1
                res.cautions.append(
                    f"Off-peak session (UTC {utc_hour:02d}:xx) — low liquidity, wider spreads likely"
                )
        else:
            score += 3
            res.cautions.append("Session time unavailable — session quality unknown")

        # ---- News blackout (0-3) ----
        news_blocked = extra.get("news_blocked", False)
        if news_blocked:
            res.blockers.append("High-impact news window active — trade blocked")
        else:
            minutes_to_news = extra.get("minutes_to_news", 999)
            if minutes_to_news < 5:
                res.blockers.append(f"High-impact news in {minutes_to_news} min — too close")
            elif minutes_to_news < 15:
                score += 1
                res.cautions.append(f"High-impact news in {minutes_to_news} min — consider waiting")
            else:
                score += 3
                res.reasons.append("No imminent high-impact news — safe to trade")

        # ---- Not at session extremes (0-2) ----
        if utc_hour is not None:
            # Penalise trading in the last 15–20 min of London or NY sessions
            at_session_end = (
                utc_hour == cfg.london_close - 1
                or utc_hour == cfg.new_york_close - 1
            )
            if at_session_end:
                score += 0
                res.cautions.append("Approaching session close — liquidity thinning")
            else:
                score += 2
                res.reasons.append("Not at session extreme — good timing window")

        res.score = min(score, self.max_score)
        res.passed = res.score >= self.grade_cfg.a_plus_session_min
        return res
