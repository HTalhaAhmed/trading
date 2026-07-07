"""
Grader: aggregates reviewer results into a final grade and explanation.

Grade scale (deterministic, config-driven):
  A+       score >= 90  AND all per-reviewer minimums met AND no hard blockers
  A        score >= 80  AND no hard blockers
  B        score >= 70  AND no hard blockers
  C        score >= 60  AND no hard blockers
  REJECTED score < 60   OR any hard blocker

A+ is intentionally strict:
  - raw score >= 90/100
  - every single reviewer must individually pass its A+ minimum
  - no hard blockers at all

This makes A+ meaningfully rare while remaining achievable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import GradeThresholds, ReviewerConfig
from .reviewers import (
    ReviewResult,
    TrendReviewer,
    MomentumReviewer,
    VolatilityReviewer,
    ExecutionReviewer,
    RiskReviewer,
    SessionReviewer,
)


GRADE_ORDER = ["A+", "A", "B", "C", "REJECTED"]


@dataclass
class GradeReport:
    """Complete grading output for one scan result."""

    direction: str                   # LONG | SHORT | NO TRADE
    grade: str                       # A+ | A | B | C | REJECTED
    score: int                       # 0-100 aggregate
    max_score: int = 100
    reviews: List[ReviewResult] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    # Explains why score was NOT elevated to A+
    a_plus_gap: List[str] = field(default_factory=list)

    @property
    def score_pct(self) -> float:
        return round(100 * self.score / self.max_score, 1)

    @property
    def is_a_plus(self) -> bool:
        return self.grade == "A+"

    @property
    def is_tradeable(self) -> bool:
        return self.grade in ("A+", "A", "B")


class Grader:
    """
    Runs all six reviewers and produces a GradeReport.

    Usage::

        grader = Grader(grade_cfg, reviewer_cfg)
        report = grader.grade(m1, m5, m15, direction, extra)
    """

    def __init__(
        self,
        grade_cfg: Optional[GradeThresholds] = None,
        reviewer_cfg: Optional[ReviewerConfig] = None,
    ) -> None:
        self.grade_cfg = grade_cfg or GradeThresholds()
        self.reviewer_cfg = reviewer_cfg or ReviewerConfig()

        self._reviewers = [
            TrendReviewer(self.reviewer_cfg, self.grade_cfg),
            MomentumReviewer(self.reviewer_cfg, self.grade_cfg),
            VolatilityReviewer(self.reviewer_cfg, self.grade_cfg),
            ExecutionReviewer(self.reviewer_cfg, self.grade_cfg),
            RiskReviewer(self.reviewer_cfg, self.grade_cfg),
            SessionReviewer(self.reviewer_cfg, self.grade_cfg),
        ]

    def grade(
        self,
        m1: pd.DataFrame,
        m5: pd.DataFrame,
        m15: pd.DataFrame,
        direction: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> GradeReport:
        """Run all reviewers and compute the final grade."""

        if direction not in ("LONG", "SHORT"):
            return GradeReport(
                direction=direction,
                grade="REJECTED",
                score=0,
                blockers=["Direction is NO TRADE — nothing to grade"],
            )

        extra = extra or {}
        reviews: List[ReviewResult] = []

        # ---- Collect reviewer results ----
        for reviewer in self._reviewers:
            result = reviewer.review(m1, m5, m15, direction, extra)
            reviews.append(result)

        # ---- Aggregate ----
        total_score = sum(r.score for r in reviews)
        max_possible = sum(r.max_score for r in reviews)

        # Normalise to 100
        score_100 = round(100 * total_score / max_possible) if max_possible > 0 else 0

        all_blockers: List[str] = []
        all_reasons: List[str] = []
        all_cautions: List[str] = []
        for r in reviews:
            all_blockers.extend(r.blockers)
            all_reasons.extend(r.reasons)
            all_cautions.extend(r.cautions)

        # ---- Determine grade ----
        grade = self._compute_grade(score_100, reviews, all_blockers)

        # ---- Explain A+ gap (if not A+) ----
        a_plus_gap = self._explain_a_plus_gap(score_100, reviews, all_blockers, grade)

        return GradeReport(
            direction=direction,
            grade=grade,
            score=score_100,
            max_score=100,
            reviews=reviews,
            reasons=all_reasons,
            cautions=all_cautions,
            blockers=all_blockers,
            a_plus_gap=a_plus_gap,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_grade(
        self,
        score: int,
        reviews: List[ReviewResult],
        blockers: List[str],
    ) -> str:
        g = self.grade_cfg

        # Any hard blocker → REJECTED regardless of score
        if blockers:
            return "REJECTED"

        if score >= g.a_plus:
            # Extra A+ requirements
            if self._meets_a_plus_requirements(score, reviews):
                return "A+"
            # Falls through to A if score is high enough but extras not met
            if score >= g.a:
                return "A"
            return "B"

        if score >= g.a:
            return "A"
        if score >= g.b:
            return "B"
        if score >= g.c:
            return "C"
        return "REJECTED"

    def _meets_a_plus_requirements(
        self, score: int, reviews: List[ReviewResult]
    ) -> bool:
        """Return True only when ALL A+ hard requirements are satisfied."""
        g = self.grade_cfg

        reviewer_map = {r.reviewer_name: r for r in reviews}

        checks = [
            reviewer_map.get("Trend", ReviewResult("Trend")).score >= g.a_plus_trend_min,
            reviewer_map.get("Momentum", ReviewResult("Momentum")).score >= g.a_plus_momentum_min,
            reviewer_map.get("Volatility", ReviewResult("Volatility")).score >= g.a_plus_volatility_min,
            reviewer_map.get("Execution", ReviewResult("Execution")).score >= g.a_plus_execution_min,
            reviewer_map.get("Risk", ReviewResult("Risk")).score >= g.a_plus_risk_min,
            reviewer_map.get("Session", ReviewResult("Session")).score >= g.a_plus_session_min,
        ]

        reviewers_passing = sum(r.passed for r in reviews)

        return (
            all(checks)
            and reviewers_passing >= g.a_plus_min_reviewers_passing
        )

    def _explain_a_plus_gap(
        self,
        score: int,
        reviews: List[ReviewResult],
        blockers: List[str],
        grade: str,
    ) -> List[str]:
        """Return a list of reasons why the setup did NOT achieve A+."""
        if grade == "A+":
            return []

        g = self.grade_cfg
        gap: List[str] = []

        if blockers:
            gap.append(f"Hard blocker(s) present: {'; '.join(blockers[:2])}")
            return gap  # blockers already explain everything

        if score < g.a_plus:
            gap.append(
                f"Score {score}/100 below A+ threshold {g.a_plus} "
                f"(need {g.a_plus - score} more points)"
            )

        reviewer_map = {r.reviewer_name: r for r in reviews}
        minimums = {
            "Trend": g.a_plus_trend_min,
            "Momentum": g.a_plus_momentum_min,
            "Volatility": g.a_plus_volatility_min,
            "Execution": g.a_plus_execution_min,
            "Risk": g.a_plus_risk_min,
            "Session": g.a_plus_session_min,
        }

        for name, min_score in minimums.items():
            r = reviewer_map.get(name)
            if r and r.score < min_score:
                gap.append(
                    f"{name} reviewer: {r.score}/{r.max_score} "
                    f"(need {min_score} for A+)"
                )

        return gap
