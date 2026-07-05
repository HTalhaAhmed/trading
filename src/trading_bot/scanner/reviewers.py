"""Multi-reviewer framework for setup grading.

Each reviewer evaluates one aspect of the trade setup and returns a
:class:`ReviewerResult`.  They are deterministic, rule-based, and
transparent — no hidden AI logic.

Reviewer roster:
  1. TrendReviewer       – higher-timeframe and EMA trend alignment
  2. MomentumReviewer    – RSI, ADX strength, and price location
  3. VolatilityReviewer  – ATR range, spread quality, and candle shape
  4. ExecutionReviewer   – candle body quality, volume, and entry clarity
  5. RiskReviewer        – daily loss, recent losses, and cooldown state
  6. SessionReviewer     – trading session and news blackout checks
"""
from __future__ import annotations

from .models import ReviewerResult, ScanContext

# ---------------------------------------------------------------------------
# Thresholds (module-level constants for transparency)
# ---------------------------------------------------------------------------
_RSI_OB = 70.0          # overbought
_RSI_OS = 30.0          # oversold
_RSI_BULL_ZONE = 55.0   # bullish momentum lower bound
_RSI_BEAR_ZONE = 45.0   # bearish momentum upper bound
_ADX_TREND_MIN = 22.0   # minimum ADX for trend regime
_ADX_STRONG = 30.0      # strong trend
_ATR_MIN = 0.3          # minimum ATR (too tight, skip)
_ATR_MAX = 5.0          # maximum ATR (too volatile, skip)
_SPREAD_TIGHT = 0.5     # tight spread threshold (price points)
_SPREAD_MAX = 3.0       # absolute maximum spread
_BODY_STRONG = 0.6      # strong candle body / range ratio
_VOL_RATIO_HIGH = 1.2   # above-average volume threshold
_PRIME_HOURS = {7, 8, 9, 10, 11, 12, 13, 14, 15, 16}  # UTC prime window
_POST_NEWS_MIN = 15     # minutes post-news stabilisation


# ---------------------------------------------------------------------------
# 1. TrendReviewer
# ---------------------------------------------------------------------------

def trend_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate higher-timeframe trend alignment and EMA structure."""
    score = 0.0
    max_score = 4.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # EMA stack alignment: fast above/below slow
    ema_aligned_long = ctx.ema_20 > ctx.ema_50
    ema_aligned_short = ctx.ema_20 < ctx.ema_50

    if ema_aligned_long:
        score += 1.0
        reasons.append("EMA-20 > EMA-50: short-term bullish structure")
    elif ema_aligned_short:
        score += 1.0
        reasons.append("EMA-20 < EMA-50: short-term bearish structure")
    else:
        cautions.append("EMA-20 ≈ EMA-50: no clear EMA bias")

    # Price vs VWAP
    if ctx.close > ctx.session_vwap:
        score += 1.0
        reasons.append("Price above session VWAP: intraday buyers in control")
    elif ctx.close < ctx.session_vwap:
        score += 1.0
        reasons.append("Price below session VWAP: intraday sellers in control")
    else:
        cautions.append("Price at VWAP: no intraday directional bias")

    # HTF trend agreement
    if ctx.htf_trend == "up" and ema_aligned_long:
        score += 1.5
        reasons.append("HTF trend UP + EMA structure bullish: multi-timeframe alignment confirmed")
    elif ctx.htf_trend == "down" and ema_aligned_short:
        score += 1.5
        reasons.append("HTF trend DOWN + EMA structure bearish: multi-timeframe alignment confirmed")
    elif ctx.htf_trend == "neutral":
        cautions.append("HTF trend is neutral: missing higher-timeframe conviction")
    else:
        cautions.append("HTF trend conflicts with EMA structure: lower conviction")

    # Price vs EMA-50 (trend buffer)
    if ctx.close > ctx.ema_50:
        score += 0.5
        reasons.append("Price above EMA-50: above medium-term average")
    elif ctx.close < ctx.ema_50:
        score += 0.5
        reasons.append("Price below EMA-50: below medium-term average")

    score = min(score, max_score)
    return ReviewerResult(
        name="TrendReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 2. MomentumReviewer
# ---------------------------------------------------------------------------

def momentum_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate RSI positioning, ADX strength, and bar momentum."""
    score = 0.0
    max_score = 4.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # RSI positioning
    if _RSI_BULL_ZONE <= ctx.rsi_14 <= _RSI_OB - 5:
        score += 1.5
        reasons.append(f"RSI {ctx.rsi_14:.1f} in bullish momentum zone (55–65): healthy uptrend momentum")
    elif _RSI_OS + 5 <= ctx.rsi_14 <= _RSI_BEAR_ZONE:
        score += 1.5
        reasons.append(f"RSI {ctx.rsi_14:.1f} in bearish momentum zone (35–45): healthy downtrend momentum")
    elif ctx.rsi_14 >= _RSI_OB:
        score += 0.5
        cautions.append(f"RSI {ctx.rsi_14:.1f} overbought: reduced upside momentum, watch for reversal")
    elif ctx.rsi_14 <= _RSI_OS:
        score += 0.5
        cautions.append(f"RSI {ctx.rsi_14:.1f} oversold: reduced downside momentum, watch for reversal")
    else:
        cautions.append(f"RSI {ctx.rsi_14:.1f} in neutral zone (45–55): no clear momentum confirmation")

    # ADX trend strength
    if ctx.adx_14 >= _ADX_STRONG:
        score += 1.5
        reasons.append(f"ADX {ctx.adx_14:.1f} ≥ {_ADX_STRONG}: strong trending environment")
    elif ctx.adx_14 >= _ADX_TREND_MIN:
        score += 1.0
        reasons.append(f"ADX {ctx.adx_14:.1f}: moderate trend strength present")
    else:
        score += 0.25
        cautions.append(f"ADX {ctx.adx_14:.1f} < {_ADX_TREND_MIN}: weak or no trend — range-bound risk")

    # Recent consecutive bars above/below EMA-50 (sustained pressure)
    if ctx.price_above_ema50_bars >= 5:
        score += 1.0
        reasons.append(f"{ctx.price_above_ema50_bars} consecutive bars above EMA-50: sustained bullish pressure")
    elif ctx.price_above_ema50_bars <= -5:
        score += 1.0
        reasons.append(f"{abs(ctx.price_above_ema50_bars)} consecutive bars below EMA-50: sustained bearish pressure")
    else:
        cautions.append("Less than 5 bars of sustained EMA pressure: setup not fully confirmed")

    score = min(score, max_score)
    return ReviewerResult(
        name="MomentumReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 3. VolatilityReviewer
# ---------------------------------------------------------------------------

def volatility_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate ATR regime, spread quality, and volatility suitability."""
    score = 0.0
    max_score = 3.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # ATR range check
    if ctx.atr_14 < _ATR_MIN:
        blockers.append(f"ATR {ctx.atr_14:.3f} too low (< {_ATR_MIN}): market too compressed, skip")
    elif ctx.atr_14 > _ATR_MAX:
        blockers.append(f"ATR {ctx.atr_14:.3f} too high (> {_ATR_MAX}): excessive volatility, skip")
    else:
        score += 1.5
        reasons.append(f"ATR {ctx.atr_14:.3f} in acceptable range [{_ATR_MIN}–{_ATR_MAX}]: healthy volatility")

    # Spread quality
    if ctx.spread_points <= _SPREAD_TIGHT:
        score += 1.0
        reasons.append(f"Spread {ctx.spread_points:.2f} pts is tight: low execution cost")
    elif ctx.spread_points <= _SPREAD_MAX:
        score += 0.5
        cautions.append(f"Spread {ctx.spread_points:.2f} pts is acceptable but not ideal")
    else:
        blockers.append(f"Spread {ctx.spread_points:.2f} pts exceeds maximum {_SPREAD_MAX}: skip (too costly)")

    # Candle body quality (body-to-range ratio)
    if ctx.body_to_range_ratio >= _BODY_STRONG:
        score += 0.5
        reasons.append(f"Candle body/range ratio {ctx.body_to_range_ratio:.2f}: strong directional candle")
    else:
        cautions.append(f"Candle body/range {ctx.body_to_range_ratio:.2f}: indecisive candle shape")

    score = min(score, max_score)
    return ReviewerResult(
        name="VolatilityReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 4. ExecutionReviewer
# ---------------------------------------------------------------------------

def execution_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate entry clarity, volume confirmation, and signal presence."""
    score = 0.0
    max_score = 3.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # Raw strategy signal must be present
    if ctx.raw_signal is None:
        blockers.append("No raw strategy signal generated: no entry basis")
        return ReviewerResult(
            name="ExecutionReviewer",
            score=0.0,
            max_score=max_score,
            reasons=reasons,
            cautions=cautions,
            blockers=blockers,
        )

    score += 1.0
    reasons.append("Strategy signal confirmed: entry trigger is present")

    # Volume confirmation
    if ctx.volume_ratio >= _VOL_RATIO_HIGH:
        score += 1.0
        reasons.append(f"Volume ratio {ctx.volume_ratio:.2f}x average: above-average participation")
    elif ctx.volume_ratio >= 0.8:
        score += 0.5
        cautions.append(f"Volume ratio {ctx.volume_ratio:.2f}x: average activity — acceptable")
    else:
        cautions.append(f"Volume ratio {ctx.volume_ratio:.2f}x: below-average volume — weak conviction")

    # Price vs VWAP alignment with signal direction
    sig_side = ctx.raw_signal.get("side", "")
    if sig_side == "long" and ctx.close > ctx.session_vwap:
        score += 1.0
        reasons.append("Long signal with price above VWAP: buyers confirmed intraday")
    elif sig_side == "short" and ctx.close < ctx.session_vwap:
        score += 1.0
        reasons.append("Short signal with price below VWAP: sellers confirmed intraday")
    else:
        cautions.append("Signal direction not confirmed by VWAP positioning")

    score = min(score, max_score)
    return ReviewerResult(
        name="ExecutionReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 5. RiskReviewer
# ---------------------------------------------------------------------------

def risk_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate drawdown state, loss streaks, and cooldown compliance."""
    score = 0.0
    max_score = 3.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # Daily loss gate
    if ctx.daily_loss_pct >= 0.03:
        blockers.append(f"Daily loss {ctx.daily_loss_pct:.1%} ≥ 3%: daily stop reached — no more trades today")
    elif ctx.daily_loss_pct >= 0.015:
        score += 0.5
        cautions.append(f"Daily loss {ctx.daily_loss_pct:.1%}: approaching daily limit — reduced size recommended")
    else:
        score += 1.0
        reasons.append(f"Daily loss {ctx.daily_loss_pct:.1%}: within daily risk budget")

    # Recent loss streak
    if ctx.recent_losses >= 3:
        blockers.append(f"{ctx.recent_losses} consecutive recent losses: mandatory cooldown in effect")
    elif ctx.recent_losses == 2:
        score += 0.5
        cautions.append(f"{ctx.recent_losses} recent losses: caution — consider reduced size")
    else:
        score += 1.0
        reasons.append(f"{ctx.recent_losses} recent losses: acceptable loss history")

    # Cooldown check
    if ctx.cooldown_remaining_minutes > 0:
        blockers.append(
            f"{ctx.cooldown_remaining_minutes} min cooldown remaining: must wait before next entry"
        )
    else:
        score += 1.0
        reasons.append("No active cooldown: trade timing is clear")

    score = min(score, max_score)
    return ReviewerResult(
        name="RiskReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# 6. SessionReviewer
# ---------------------------------------------------------------------------

def session_reviewer(ctx: ScanContext) -> ReviewerResult:
    """Evaluate session quality, prime hours, and news blackout."""
    score = 0.0
    max_score = 3.0
    reasons: list[str] = []
    cautions: list[str] = []
    blockers: list[str] = []

    # News blackout hard block
    if ctx.is_news_blackout:
        blockers.append("Inside high-impact news blackout window: no trades permitted")
    elif ctx.minutes_since_news < _POST_NEWS_MIN:
        blockers.append(
            f"Only {ctx.minutes_since_news} min since high-impact news: "
            f"waiting for {_POST_NEWS_MIN}-min stabilisation period"
        )
    else:
        score += 1.0
        reasons.append("Outside all news blackout windows: safe to trade")

    # Session quality
    _high_quality = {"london", "new_york"}
    if ctx.session in _high_quality:
        score += 1.5
        reasons.append(f"Session: {ctx.session.title()} — high-liquidity prime session")
    elif ctx.session == "asian":
        score += 0.5
        cautions.append("Asian session: lower XAUUSD liquidity — wider spreads possible")
    else:
        score += 0.0
        cautions.append(f"Session '{ctx.session}': off-hours trading — lowest liquidity")

    # Prime trading hour check
    if ctx.hour_utc in _PRIME_HOURS:
        score += 0.5
        reasons.append(f"Hour {ctx.hour_utc:02d}:xx UTC is within prime trading window (07–16 UTC)")
    else:
        cautions.append(f"Hour {ctx.hour_utc:02d}:xx UTC is outside the prime trading window")

    score = min(score, max_score)
    return ReviewerResult(
        name="SessionReviewer",
        score=score,
        max_score=max_score,
        reasons=reasons,
        cautions=cautions,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# Public entry point: run all reviewers
# ---------------------------------------------------------------------------

def run_all_reviewers(ctx: ScanContext) -> list[ReviewerResult]:
    """Run all six reviewers and return their results in order."""
    return [
        trend_reviewer(ctx),
        momentum_reviewer(ctx),
        volatility_reviewer(ctx),
        execution_reviewer(ctx),
        risk_reviewer(ctx),
        session_reviewer(ctx),
    ]
