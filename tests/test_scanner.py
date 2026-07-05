"""Tests for the trade scanner, setup grader, and A+ filtering logic."""
from __future__ import annotations

import pytest

from trading_bot.scanner import ScanContext, ScanResult, grade_setup
from trading_bot.scanner.grader import _compute_grade, _infer_direction
from trading_bot.scanner.reviewers import (
    execution_reviewer,
    momentum_reviewer,
    risk_reviewer,
    session_reviewer,
    trend_reviewer,
    volatility_reviewer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_ctx(**overrides) -> ScanContext:
    """Return a well-formed ScanContext representing a high-quality LONG setup."""
    defaults = dict(
        close=1950.0,
        ema_20=1948.0,
        ema_50=1940.0,
        atr_14=1.0,
        adx_14=28.0,
        rsi_14=60.0,
        session_vwap=1945.0,
        htf_trend="up",
        session="london",
        hour_utc=10,
        spread_points=0.3,
        recent_losses=0,
        cooldown_remaining_minutes=0,
        daily_loss_pct=0.005,
        is_news_blackout=False,
        minutes_since_news=60,
        regime="trending",
        raw_signal={"side": "long", "stop_atr_mult": 1.5, "take_profit_r": 1.5},
        price_above_ema50_bars=7,
        body_to_range_ratio=0.7,
        volume_ratio=1.3,
    )
    defaults.update(overrides)
    return ScanContext(**defaults)


def _blocker_ctx(**overrides) -> ScanContext:
    """Return a ScanContext that should produce a REJECTED result."""
    return _base_ctx(
        is_news_blackout=True,
        recent_losses=4,
        cooldown_remaining_minutes=10,
        spread_points=5.0,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

class TestGradeThresholds:
    def test_a_plus(self):
        assert _compute_grade(0.90) == "A+"

    def test_a_plus_boundary(self):
        assert _compute_grade(0.88) == "A+"

    def test_a(self):
        assert _compute_grade(0.80) == "A"

    def test_b(self):
        assert _compute_grade(0.65) == "B"

    def test_c(self):
        assert _compute_grade(0.50) == "C"

    def test_rejected(self):
        assert _compute_grade(0.40) == "REJECTED"

    def test_zero(self):
        assert _compute_grade(0.0) == "REJECTED"


# ---------------------------------------------------------------------------
# Direction inference
# ---------------------------------------------------------------------------

class TestDirectionInference:
    def test_long_direction(self):
        ctx = _base_ctx()
        reviewers = []  # no blockers
        direction = _infer_direction(ctx, reviewers)
        assert direction == "LONG"

    def test_short_direction(self):
        ctx = _base_ctx(
            close=1930.0,
            ema_20=1932.0,
            ema_50=1940.0,
            session_vwap=1945.0,
            htf_trend="down",
            raw_signal={"side": "short"},
        )
        direction = _infer_direction(ctx, [])
        assert direction == "SHORT"

    def test_none_when_blockers(self):
        from trading_bot.scanner.reviewers import ReviewerResult
        blocker_rv = ReviewerResult(
            name="Test", score=0.0, max_score=1.0,
            blockers=["some_blocker"]
        )
        ctx = _base_ctx()
        direction = _infer_direction(ctx, [blocker_rv])
        assert direction == "NONE"


# ---------------------------------------------------------------------------
# Individual reviewers
# ---------------------------------------------------------------------------

class TestTrendReviewer:
    def test_bullish_alignment_scores_positively(self):
        ctx = _base_ctx()
        result = trend_reviewer(ctx)
        assert result.score > 0
        assert result.name == "TrendReviewer"
        assert any("EMA" in r for r in result.reasons)

    def test_htf_alignment_boosts_score(self):
        ctx_aligned = _base_ctx(htf_trend="up")
        ctx_neutral = _base_ctx(htf_trend="neutral")
        assert trend_reviewer(ctx_aligned).score > trend_reviewer(ctx_neutral).score

    def test_no_blockers_for_normal_trend(self):
        ctx = _base_ctx()
        result = trend_reviewer(ctx)
        assert len(result.blockers) == 0


class TestMomentumReviewer:
    def test_healthy_rsi_scores(self):
        ctx = _base_ctx(rsi_14=60.0)
        result = momentum_reviewer(ctx)
        assert result.score > 0
        assert result.name == "MomentumReviewer"

    def test_strong_adx_adds_score(self):
        ctx_strong = _base_ctx(adx_14=35.0)
        ctx_weak = _base_ctx(adx_14=15.0)
        assert momentum_reviewer(ctx_strong).score > momentum_reviewer(ctx_weak).score

    def test_sustained_bars_above_ema50_adds_score(self):
        ctx_sustained = _base_ctx(price_above_ema50_bars=8)
        ctx_flat = _base_ctx(price_above_ema50_bars=2)
        assert momentum_reviewer(ctx_sustained).score > momentum_reviewer(ctx_flat).score


class TestVolatilityReviewer:
    def test_acceptable_atr_and_spread_scores(self):
        ctx = _base_ctx(atr_14=1.0, spread_points=0.3)
        result = volatility_reviewer(ctx)
        assert result.score > 0
        assert result.name == "VolatilityReviewer"

    def test_too_low_atr_is_blocker(self):
        ctx = _base_ctx(atr_14=0.1)
        result = volatility_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_too_high_atr_is_blocker(self):
        ctx = _base_ctx(atr_14=10.0)
        result = volatility_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_excessive_spread_is_blocker(self):
        ctx = _base_ctx(spread_points=5.0)
        result = volatility_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_strong_body_adds_reason(self):
        ctx = _base_ctx(body_to_range_ratio=0.8)
        result = volatility_reviewer(ctx)
        assert any("body" in r.lower() or "candle" in r.lower() for r in result.reasons)


class TestExecutionReviewer:
    def test_no_signal_is_blocker(self):
        ctx = _base_ctx(raw_signal=None)
        result = execution_reviewer(ctx)
        assert len(result.blockers) > 0
        assert result.score == 0.0

    def test_signal_with_vwap_confirmation_scores(self):
        ctx = _base_ctx()
        result = execution_reviewer(ctx)
        assert result.score > 0
        assert result.name == "ExecutionReviewer"

    def test_high_volume_ratio_adds_reason(self):
        ctx = _base_ctx(volume_ratio=1.5)
        result = execution_reviewer(ctx)
        assert any("volume" in r.lower() or "participation" in r.lower() for r in result.reasons)


class TestRiskReviewer:
    def test_clean_risk_state_scores_well(self):
        ctx = _base_ctx(recent_losses=0, cooldown_remaining_minutes=0, daily_loss_pct=0.005)
        result = risk_reviewer(ctx)
        assert result.score >= 3.0
        assert result.name == "RiskReviewer"

    def test_daily_stop_reached_is_blocker(self):
        ctx = _base_ctx(daily_loss_pct=0.04)
        result = risk_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_too_many_losses_is_blocker(self):
        ctx = _base_ctx(recent_losses=3)
        result = risk_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_active_cooldown_is_blocker(self):
        ctx = _base_ctx(cooldown_remaining_minutes=5)
        result = risk_reviewer(ctx)
        assert len(result.blockers) > 0


class TestSessionReviewer:
    def test_london_session_prime_hours_scores(self):
        ctx = _base_ctx(session="london", hour_utc=10)
        result = session_reviewer(ctx)
        assert result.score > 0
        assert result.name == "SessionReviewer"

    def test_news_blackout_is_blocker(self):
        ctx = _base_ctx(is_news_blackout=True)
        result = session_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_post_news_too_soon_is_blocker(self):
        ctx = _base_ctx(is_news_blackout=False, minutes_since_news=5)
        result = session_reviewer(ctx)
        assert len(result.blockers) > 0

    def test_off_hours_caution(self):
        ctx = _base_ctx(session="off", hour_utc=2)
        result = session_reviewer(ctx)
        assert any("off" in c.lower() or "outside" in c.lower() for c in result.cautions)


# ---------------------------------------------------------------------------
# Full grader integration
# ---------------------------------------------------------------------------

class TestGradeSetup:
    def test_strong_setup_produces_high_grade(self):
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        assert isinstance(result, ScanResult)
        assert result.grade in ("A+", "A", "B")
        assert result.direction == "LONG"
        assert result.score > 0.0

    def test_blocker_setup_produces_rejected(self):
        ctx = _blocker_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        assert result.grade == "REJECTED"
        assert result.direction == "NONE"
        assert len(result.blockers) > 0
        assert result.surfaced is False

    def test_a_plus_only_suppresses_lower_grades(self):
        ctx = _base_ctx(adx_14=12.0, rsi_14=50.0, htf_trend="neutral", price_above_ema50_bars=1)
        result = grade_setup(ctx, only_a_plus=True)
        if result.grade != "A+":
            assert result.surfaced is False

    def test_a_plus_only_surfaces_a_plus(self):
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=True)
        if result.grade == "A+":
            assert result.surfaced is True

    def test_result_has_all_reviewer_results(self):
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        assert len(result.reviewer_results) == 6
        names = {r.name for r in result.reviewer_results}
        assert "TrendReviewer" in names
        assert "MomentumReviewer" in names
        assert "VolatilityReviewer" in names
        assert "ExecutionReviewer" in names
        assert "RiskReviewer" in names
        assert "SessionReviewer" in names

    def test_to_dict_is_serialisable(self):
        import json
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        d = result.to_dict()
        serialised = json.dumps(d)
        assert "grade" in serialised
        assert "direction" in serialised
        assert "score" in serialised
        assert "reviewers" in serialised

    def test_report_string_contains_grade(self):
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        report = result.report()
        assert result.grade in report
        assert result.direction in report

    def test_summary_string(self):
        ctx = _base_ctx()
        result = grade_setup(ctx, only_a_plus=False)
        summary = result.summary()
        assert result.grade in summary
        assert result.direction in summary

    def test_score_bounded_0_1(self):
        for _ in range(5):
            ctx = _base_ctx()
            result = grade_setup(ctx)
            assert 0.0 <= result.score <= 1.0

    def test_raw_score_consistent(self):
        ctx = _base_ctx()
        result = grade_setup(ctx)
        expected_raw = sum(r.score for r in result.reviewer_results)
        assert abs(result.raw_score - expected_raw) < 1e-9


# ---------------------------------------------------------------------------
# A+ only mode filtering behaviour
# ---------------------------------------------------------------------------

class TestAPlusOnlyMode:
    def test_rejected_setup_never_surfaced_in_a_plus_mode(self):
        ctx = _blocker_ctx()
        result = grade_setup(ctx, only_a_plus=True)
        assert result.surfaced is False

    def test_b_grade_not_surfaced_in_a_plus_mode(self):
        ctx = _base_ctx(adx_14=10.0, rsi_14=51.0, htf_trend="neutral", price_above_ema50_bars=1)
        result = grade_setup(ctx, only_a_plus=True)
        if result.grade == "B":
            assert result.surfaced is False

    def test_b_grade_surfaced_when_not_a_plus_mode(self):
        ctx = _base_ctx(adx_14=10.0, rsi_14=51.0, htf_trend="neutral", price_above_ema50_bars=1)
        result = grade_setup(ctx, only_a_plus=False)
        if result.grade == "B":
            assert result.surfaced is True

    def test_blockers_still_recorded_in_a_plus_mode(self):
        ctx = _blocker_ctx()
        result = grade_setup(ctx, only_a_plus=True)
        assert len(result.blockers) > 0
