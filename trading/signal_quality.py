from __future__ import annotations

from .config import FilterConfig, QualityConfig, WeightConfig
from .models import SignalAssessment, SignalContext


def _grade(score: float) -> str:
    if score >= 0.9:
        return "A+"
    if score >= 0.8:
        return "A"
    if score >= 0.65:
        return "B"
    return "C"


def assess_signal(
    ctx: SignalContext,
    quality_cfg: QualityConfig,
    filter_cfg: FilterConfig,
    weights: WeightConfig,
    mode: str,
) -> SignalAssessment:
    blocked: list[str] = []
    weighted_score = 0.0
    max_score = sum(vars(weights).values())

    checks = {
        "htf_alignment": ctx.direction == ctx.htf_direction,
        "session": ctx.session in filter_cfg.allowed_sessions,
        "volatility": filter_cfg.min_volatility_atr <= ctx.atr_normalized <= filter_cfg.max_volatility_atr,
        "spread": ctx.spread_points <= filter_cfg.max_spread_points,
        "room_to_target": ctx.room_to_target_atr >= filter_cfg.min_room_to_target_atr,
        "trigger_size": ctx.trigger_candle_atr_ratio <= filter_cfg.max_trigger_candle_atr_ratio,
    }

    if filter_cfg.news_blackout_enabled and ctx.is_news_blackout:
        checks["news_blackout"] = False
        blocked.append("news_blackout")
    if filter_cfg.news_blackout_enabled and ctx.minutes_since_news < filter_cfg.post_news_stabilization_minutes:
        checks["post_news_stabilization"] = False
        blocked.append("post_news_stabilization")

    if ctx.recent_losses > filter_cfg.max_recent_losses:
        checks["recent_loss_cooldown"] = False
        blocked.append("recent_loss_cooldown")
    if ctx.cooldown_remaining_minutes > 0:
        checks["cooldown_active"] = False
        blocked.append("cooldown_active")

    for name, ok in checks.items():
        weight = getattr(weights, name, 0.0)
        if ok:
            weighted_score += weight
        elif name in {
            "htf_alignment",
            "session",
            "volatility",
            "spread",
            "room_to_target",
            "trigger_size",
        }:
            blocked.append(name)

    score = 0.0 if max_score == 0 else round(weighted_score / max_score, 4)
    min_score = quality_cfg.live_min_score if mode == "mt5" else quality_cfg.min_score

    if score < min_score:
        blocked.append("below_min_score")

    grade = _grade(score)
    if quality_cfg.only_a_plus and grade != "A+":
        blocked.append("not_a_plus")

    return SignalAssessment(allowed=not blocked, score=score, grade=grade, blocked_reasons=blocked)
