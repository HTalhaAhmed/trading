from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from trading_bot.features import FeatureSet


@dataclass
class GradeResult:
    symbol: str
    grade: str
    score: float
    direction: str
    reasons: list[str]
    blockers: list[str]
    surfaced: bool
    timestamp: datetime
    session: str
    spread_atr_ratio: float = 0.0


def _get_session_name(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    minutes = dt.hour * 60 + dt.minute
    if 12 * 60 <= minutes < 16 * 60:
        return "Overlap"
    if 7 * 60 <= minutes < 16 * 60:
        return "London"
    if 12 * 60 <= minutes < 21 * 60:
        return "NewYork"
    if 0 <= minutes < 9 * 60:
        return "Asian"
    return "Off-hours"


def grade_symbol(
    symbol: str,
    features: FeatureSet,
    spread: float,
    config: dict,
    caps_state: dict,
    open_positions_total: int = 0,
) -> GradeResult:
    reasons: list[str] = []
    blockers: list[str] = []
    score = 0.0
    timestamp = features.timestamp if isinstance(features.timestamp, datetime) else datetime.now(timezone.utc)
    session = _get_session_name(timestamp)
    good_session = session in {"London", "NewYork", "Overlap"}
    atr = features.atr14 if features.atr14 > 0 else 0.0
    spread_atr_ratio = (spread / atr) if atr > 0 else float("inf")

    if features.trend_direction != "neutral":
        score += 0.25
        reasons.append(f"Trend detected: {features.trend_direction.upper()}")

    if features.adx14 > 25:
        score += 0.20
        reasons.append(f"ADX trending ({features.adx14:.1f})")
    elif features.adx14 > 20:
        score += 0.10
        reasons.append(f"ADX supportive ({features.adx14:.1f})")

    if features.htf_aligned:
        score += 0.20
        reasons.append("HTF alignment confirmed")

    if good_session:
        score += 0.15
        reasons.append(f"Active session: {session}")
    elif config.get("scanner", {}).get("require_trending_market_first", True):
        reasons.append("Caution: off-prime session")

    max_spread_ratio = config.get("scanner", {}).get("max_spread_atr_ratio", 0.3)
    if atr > 0 and spread_atr_ratio < 0.2:
        score += 0.10
        reasons.append("Low spread relative to ATR")

    if features.trend_direction == "long" and features.price > features.vwap:
        score += 0.10
        reasons.append("Price above VWAP")
    elif features.trend_direction == "short" and features.price < features.vwap:
        score += 0.10
        reasons.append("Price below VWAP")

    score = round(min(score, 1.0), 2)

    if features.trend_direction == "neutral" or score < 0.30:
        grade = "NO_TRADE" if features.trend_direction == "neutral" or score < 0.30 else "C"
    elif score >= 0.85 and features.adx14 > 20 and features.htf_aligned and good_session:
        grade = "A+"
    elif score >= 0.70 and features.adx14 > 20:
        grade = "A"
    elif score >= 0.50:
        grade = "B"
    else:
        grade = "C"

    direction = {"long": "LONG", "short": "SHORT"}.get(features.trend_direction, "NO_TRADE")

    if caps_state.get("symbol_capped"):
        blockers.append(
            f"daily symbol cap reached ({caps_state.get('symbol_count', 0)}/{caps_state.get('symbol_cap', 0)})"
        )
    if caps_state.get("in_cooldown"):
        blockers.append(f"cooldown active ({caps_state.get('cooldown_remaining_min', 0):.0f} min remaining)")
    if caps_state.get("session_capped"):
        blockers.append(
            f"session cap reached ({caps_state.get('session_count', 0)}/{caps_state.get('session_cap', 0)})"
        )
    if caps_state.get("has_open_position"):
        blockers.append("already has open position")
    if caps_state.get("total_positions_maxed"):
        blockers.append(
            f"max open positions reached ({caps_state.get('total_positions', open_positions_total)}/{caps_state.get('total_cap', 0)})"
        )
    if atr <= 0 or spread > max_spread_ratio * max(atr, 1e-12):
        blockers.append("spread too high")

    only_a_plus = config.get("scanner", {}).get("only_a_plus", True)
    if blockers:
        surfaced = False
    elif only_a_plus:
        surfaced = grade == "A+"
    else:
        surfaced = grade in {"A+", "A"}

    return GradeResult(
        symbol=symbol,
        grade=grade,
        score=score,
        direction=direction,
        reasons=reasons,
        blockers=blockers,
        surfaced=surfaced,
        timestamp=timestamp,
        session=session,
        spread_atr_ratio=0.0 if spread_atr_ratio == float("inf") else round(spread_atr_ratio, 4),
    )
