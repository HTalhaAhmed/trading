from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .regime import DirectionBias, determine_direction_bias
from .reviewers import (
    ExecutionReviewer,
    MomentumReviewer,
    ReviewResult,
    RiskReviewer,
    SessionReviewer,
    TrendReviewer,
    VolatilityReviewer,
)
from .trade_controls import utc_now


class Grade(str, Enum):
    APLUS = 'A+'
    A = 'A'
    B = 'B'
    C = 'C'
    REJECTED = 'REJECTED'


@dataclass(slots=True)
class ScanResult:
    symbol: str
    direction: str
    grade: Grade
    score: float
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utc_now)


class TradeScanner:
    def __init__(self, config: dict):
        self.config = config
        scanner_config = config.get('scanner', {})
        self.only_a_plus = bool(scanner_config.get('only_a_plus', True))
        self.thresholds = {
            Grade.APLUS: float(scanner_config.get('a_plus_min_score', 0.85)),
            Grade.A: float(scanner_config.get('a_min_score', 0.70)),
            Grade.B: float(scanner_config.get('b_min_score', 0.55)),
            Grade.C: float(scanner_config.get('c_min_score', 0.40)),
        }
        self.reviewers: list[tuple[object, float]] = [
            (TrendReviewer(), 0.25),
            (MomentumReviewer(), 0.20),
            (VolatilityReviewer(), 0.15),
            (ExecutionReviewer(), 0.15),
            (RiskReviewer(), 0.15),
            (SessionReviewer(), 0.10),
        ]

    def _resolve_direction(self, features: dict[str, float], direction_override: str | None = None) -> str:
        if direction_override:
            return direction_override
        bias = determine_direction_bias(features)
        if bias is DirectionBias.BULLISH:
            return 'LONG'
        if bias is DirectionBias.BEARISH:
            return 'SHORT'
        return 'NO TRADE'

    def _assign_grade(self, score: float, blockers: list[str]) -> Grade:
        if blockers:
            return Grade.REJECTED
        if score >= self.thresholds[Grade.APLUS]:
            return Grade.APLUS
        if score >= self.thresholds[Grade.A]:
            return Grade.A
        if score >= self.thresholds[Grade.B]:
            return Grade.B
        if score >= self.thresholds[Grade.C]:
            return Grade.C
        return Grade.REJECTED

    def scan(self, symbol: str, features: dict[str, float], direction_override: str | None = None) -> ScanResult:
        direction = self._resolve_direction(features, direction_override)
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        total_weight = 0.0
        weighted_score = 0.0

        for reviewer, weight in self.reviewers:
            review: ReviewResult = reviewer.review(features, direction)
            total_weight += weight
            weighted_score += review.score * weight
            reasons.extend(review.reasons)
            cautions.extend(review.cautions)
            blockers.extend(review.blockers)

        score = round(weighted_score / total_weight if total_weight else 0.0, 4)
        grade = self._assign_grade(score, blockers)
        if direction == 'NO TRADE' or grade is Grade.REJECTED:
            direction = 'NO TRADE'
        return ScanResult(
            symbol=symbol,
            direction=direction,
            grade=grade,
            score=score,
            reasons=reasons,
            cautions=cautions,
            blockers=blockers,
            timestamp=utc_now(),
        )

    def is_tradable(self, result: ScanResult) -> bool:
        if result.direction == 'NO TRADE' or result.grade is Grade.REJECTED or result.blockers:
            return False
        if self.only_a_plus:
            return result.grade is Grade.APLUS
        return result.grade in {Grade.APLUS, Grade.A, Grade.B}
