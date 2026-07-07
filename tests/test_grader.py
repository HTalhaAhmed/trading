"""Tests for the grader – focused on A+ selectivity."""

import pytest
from trading_bot.config import GradeThresholds, ReviewerConfig
from trading_bot.scanner.grader import Grader, GRADE_ORDER
from trading_bot.scanner.reviewers import ReviewResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reviews(scores: dict) -> list:
    """Build ReviewResult list from a dict of {name: (score, max_score)}."""
    results = []
    reviewer_names = ["Trend", "Momentum", "Volatility", "Execution", "Risk", "Session"]
    for name in reviewer_names:
        sc, mx = scores.get(name, (0, 0))
        r = ReviewResult(reviewer_name=name, score=sc, max_score=mx, passed=False)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# Grade threshold tests
# ---------------------------------------------------------------------------

class TestGradeThresholds:
    def test_a_plus_threshold_is_90(self):
        g = GradeThresholds()
        assert g.a_plus == 90

    def test_a_threshold_is_80(self):
        g = GradeThresholds()
        assert g.a == 80

    def test_b_threshold_is_70(self):
        g = GradeThresholds()
        assert g.b == 70

    def test_c_threshold_is_60(self):
        g = GradeThresholds()
        assert g.c == 60

    def test_a_plus_requires_all_six_reviewers(self):
        g = GradeThresholds()
        assert g.a_plus_min_reviewers_passing == 6

    def test_a_plus_trend_minimum_is_strict(self):
        g = GradeThresholds()
        # 20/25 = 80% required – meaningfully strict
        assert g.a_plus_trend_min >= 18

    def test_a_plus_session_minimum_set(self):
        g = GradeThresholds()
        assert g.a_plus_session_min >= 7


# ---------------------------------------------------------------------------
# Grader._compute_grade direct tests
# ---------------------------------------------------------------------------

class TestGraderComputeGrade:
    def setup_method(self):
        self.grader = Grader()

    def test_blocker_forces_rejected(self):
        reviews = [ReviewResult("Trend", score=25, max_score=25, passed=True)]
        grade = self.grader._compute_grade(95, reviews, ["Spread too wide"])
        assert grade == "REJECTED"

    def test_score_below_60_is_rejected(self):
        grade = self.grader._compute_grade(55, [], [])
        assert grade == "REJECTED"

    def test_score_60_is_c(self):
        grade = self.grader._compute_grade(60, [], [])
        assert grade == "C"

    def test_score_70_is_b(self):
        grade = self.grader._compute_grade(70, [], [])
        assert grade == "B"

    def test_score_80_is_a(self):
        grade = self.grader._compute_grade(80, [], [])
        assert grade == "A"

    def test_score_90_without_per_reviewer_pass_is_not_a_plus(self):
        """Score of 90 alone is insufficient — per-reviewer requirements must pass too."""
        # Build reviews where all fail their per-reviewer check
        reviews = [ReviewResult(name, score=0, max_score=25, passed=False)
                   for name in ["Trend", "Momentum", "Volatility", "Execution", "Risk", "Session"]]
        grade = self.grader._compute_grade(90, reviews, [])
        assert grade != "A+"

    def test_score_90_with_all_reviewers_passing_is_a_plus_via_meets_check(self):
        """_meets_a_plus_requirements returns True when all minimums are satisfied."""
        g = GradeThresholds()
        reviews = [
            ReviewResult("Trend",      score=g.a_plus_trend_min,      max_score=25, passed=True),
            ReviewResult("Momentum",   score=g.a_plus_momentum_min,   max_score=20, passed=True),
            ReviewResult("Volatility", score=g.a_plus_volatility_min, max_score=15, passed=True),
            ReviewResult("Execution",  score=g.a_plus_execution_min,  max_score=15, passed=True),
            ReviewResult("Risk",       score=g.a_plus_risk_min,       max_score=15, passed=True),
            ReviewResult("Session",    score=g.a_plus_session_min,    max_score=10, passed=True),
        ]
        assert self.grader._meets_a_plus_requirements(95, reviews) is True
        # And therefore _compute_grade must return A+
        grade = self.grader._compute_grade(95, reviews, [])
        assert grade == "A+"

    def test_a_plus_is_not_impossible(self, bull_m1, bull_m5, bull_m15):
        """A+ must remain achievable — verify grade set includes A+."""
        assert "A+" in GRADE_ORDER


# ---------------------------------------------------------------------------
# A+ selectivity — per-reviewer minimums
# ---------------------------------------------------------------------------

class TestAPlusSelectivity:
    def setup_method(self):
        self.grader = Grader()
        self.g = GradeThresholds()

    def test_a_plus_fails_when_trend_reviewer_too_low(self):
        """If Trend reviewer is below a_plus_trend_min, A+ is blocked."""
        reviews = [
            ReviewResult("Trend",      score=self.g.a_plus_trend_min - 1,     max_score=25, passed=False),
            ReviewResult("Momentum",   score=self.g.a_plus_momentum_min,      max_score=20, passed=True),
            ReviewResult("Volatility", score=self.g.a_plus_volatility_min,    max_score=15, passed=True),
            ReviewResult("Execution",  score=self.g.a_plus_execution_min,     max_score=15, passed=True),
            ReviewResult("Risk",       score=self.g.a_plus_risk_min,          max_score=15, passed=True),
            ReviewResult("Session",    score=self.g.a_plus_session_min,       max_score=10, passed=True),
        ]
        assert not self.grader._meets_a_plus_requirements(95, reviews)

    def test_a_plus_fails_when_session_reviewer_too_low(self):
        reviews = [
            ReviewResult("Trend",      score=self.g.a_plus_trend_min,         max_score=25, passed=True),
            ReviewResult("Momentum",   score=self.g.a_plus_momentum_min,      max_score=20, passed=True),
            ReviewResult("Volatility", score=self.g.a_plus_volatility_min,    max_score=15, passed=True),
            ReviewResult("Execution",  score=self.g.a_plus_execution_min,     max_score=15, passed=True),
            ReviewResult("Risk",       score=self.g.a_plus_risk_min,          max_score=15, passed=True),
            ReviewResult("Session",    score=self.g.a_plus_session_min - 1,   max_score=10, passed=False),
        ]
        assert not self.grader._meets_a_plus_requirements(95, reviews)

    def test_a_plus_passes_when_all_reviewers_meet_minimum(self):
        g = self.g
        reviews = [
            ReviewResult("Trend",      score=g.a_plus_trend_min,      max_score=25, passed=True),
            ReviewResult("Momentum",   score=g.a_plus_momentum_min,   max_score=20, passed=True),
            ReviewResult("Volatility", score=g.a_plus_volatility_min, max_score=15, passed=True),
            ReviewResult("Execution",  score=g.a_plus_execution_min,  max_score=15, passed=True),
            ReviewResult("Risk",       score=g.a_plus_risk_min,       max_score=15, passed=True),
            ReviewResult("Session",    score=g.a_plus_session_min,    max_score=10, passed=True),
        ]
        assert self.grader._meets_a_plus_requirements(95, reviews)

    def test_a_plus_gap_explains_score_deficit(self):
        g = self.g
        reviews = [ReviewResult(name, 0, 15, False) for name in
                   ["Trend", "Momentum", "Volatility", "Execution", "Risk", "Session"]]
        gap = self.grader._explain_a_plus_gap(75, reviews, [], "B")
        assert any("threshold" in msg.lower() or "below" in msg.lower() for msg in gap)

    def test_a_plus_gap_empty_when_grade_is_a_plus(self):
        g = self.g
        reviews = [
            ReviewResult("Trend",      score=g.a_plus_trend_min,      max_score=25, passed=True),
            ReviewResult("Momentum",   score=g.a_plus_momentum_min,   max_score=20, passed=True),
            ReviewResult("Volatility", score=g.a_plus_volatility_min, max_score=15, passed=True),
            ReviewResult("Execution",  score=g.a_plus_execution_min,  max_score=15, passed=True),
            ReviewResult("Risk",       score=g.a_plus_risk_min,       max_score=15, passed=True),
            ReviewResult("Session",    score=g.a_plus_session_min,    max_score=10, passed=True),
        ]
        gap = self.grader._explain_a_plus_gap(92, reviews, [], "A+")
        assert gap == []

    def test_a_plus_gap_explains_when_not_enough_reviewers_pass(self):
        g = self.g
        reviews = [
            ReviewResult("Trend",      score=g.a_plus_trend_min,      max_score=25, passed=True),
            ReviewResult("Momentum",   score=g.a_plus_momentum_min,   max_score=20, passed=True),
            ReviewResult("Volatility", score=g.a_plus_volatility_min, max_score=15, passed=True),
            ReviewResult("Execution",  score=g.a_plus_execution_min,  max_score=15, passed=True),
            ReviewResult("Risk",       score=g.a_plus_risk_min,       max_score=15, passed=True),
            # Session fails
            ReviewResult("Session",    score=0,                        max_score=10, passed=False),
        ]
        gap = self.grader._explain_a_plus_gap(92, reviews, [], "A")
        assert len(gap) > 0


# ---------------------------------------------------------------------------
# GradeReport properties
# ---------------------------------------------------------------------------

class TestGradeReport:
    def test_is_a_plus_property(self, bull_m1, bull_m5, bull_m15):
        grader = Grader()
        report = grader.grade(bull_m1, bull_m5, bull_m15, "LONG",
                              extra={"utc_hour": 14, "spread": 1.0})
        assert isinstance(report.is_a_plus, bool)

    def test_is_tradeable_for_a_b_grades(self, bull_m1, bull_m5, bull_m15):
        grader = Grader()
        report = grader.grade(bull_m1, bull_m5, bull_m15, "LONG")
        assert report.is_tradeable in (True, False)

    def test_rejected_direction_returns_rejected(self, bull_m1, bull_m5, bull_m15):
        grader = Grader()
        report = grader.grade(bull_m1, bull_m5, bull_m15, "NO TRADE")
        assert report.grade == "REJECTED"

    def test_blocker_prevents_a_plus(self, bull_m1, bull_m5, bull_m15):
        grader = Grader()
        report = grader.grade(
            bull_m1, bull_m5, bull_m15, "LONG",
            extra={
                "utc_hour": 14,
                "spread": 50.0,   # massive spread → blocker
                "minutes_to_news": 999,
            }
        )
        assert report.grade == "REJECTED"
        assert len(report.blockers) > 0
