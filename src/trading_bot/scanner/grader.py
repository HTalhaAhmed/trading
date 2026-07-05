"""Setup grader: aggregates reviewer results into a final ScanResult.

Usage::

    from trading_bot.scanner import grade_setup, ScanResult
    from trading_bot.scanner.models import ScanContext

    ctx = ScanContext(close=1950.0, ema_20=1948.0, ema_50=1940.0, ...)
    result: ScanResult = grade_setup(ctx, only_a_plus=True)
    print(result.summary())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ScanContext, ReviewerResult
from .reviewers import run_all_reviewers


# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------
_GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (0.88, "A+"),
    (0.75, "A"),
    (0.60, "B"),
    (0.45, "C"),
]
_REJECTED_GRADE = "REJECTED"


def _compute_grade(score: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return _REJECTED_GRADE


# ---------------------------------------------------------------------------
# Direction inference
# ---------------------------------------------------------------------------

def _infer_direction(ctx: ScanContext, reviewer_results: list[ReviewerResult]) -> str:
    """Determine the recommended trade direction from context signals.

    Returns ``'LONG'``, ``'SHORT'``, or ``'NONE'``.
    """
    # Hard blockers anywhere → no trade
    all_blockers = [b for r in reviewer_results for b in r.blockers]
    if all_blockers:
        return "NONE"

    long_signals = 0
    short_signals = 0

    # Raw signal from strategy router
    if ctx.raw_signal is not None:
        side = ctx.raw_signal.get("side", "")
        if side == "long":
            long_signals += 3
        elif side == "short":
            short_signals += 3

    # EMA alignment
    if ctx.ema_20 > ctx.ema_50:
        long_signals += 1
    elif ctx.ema_20 < ctx.ema_50:
        short_signals += 1

    # VWAP
    if ctx.close > ctx.session_vwap:
        long_signals += 1
    elif ctx.close < ctx.session_vwap:
        short_signals += 1

    # HTF trend
    if ctx.htf_trend == "up":
        long_signals += 2
    elif ctx.htf_trend == "down":
        short_signals += 2

    if long_signals > short_signals:
        return "LONG"
    if short_signals > long_signals:
        return "SHORT"
    return "NONE"


# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    """Final output of the trade scanner for one bar/moment.

    Attributes
    ----------
    direction:
        ``'LONG'``, ``'SHORT'``, or ``'NONE'``.
    grade:
        ``'A+'``, ``'A'``, ``'B'``, ``'C'``, or ``'REJECTED'``.
    score:
        Aggregate score normalised to [0, 1].
    surfaced:
        ``True`` if the setup should be shown to the user.  In A+ only mode
        this is ``True`` only for A+ setups.
    reasons:
        Human-readable confluences supporting the grade.
    cautions:
        Concerns or warnings that do not block but reduce conviction.
    blockers:
        Hard-stop conditions that caused a REJECTED / NONE result.
    reviewer_results:
        Detailed per-reviewer breakdown.
    raw_score:
        Unnormalised aggregate points.
    max_raw_score:
        Maximum possible aggregate points across all reviewers.
    """

    direction: str
    grade: str
    score: float
    surfaced: bool
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    reviewer_results: list[ReviewerResult] = field(default_factory=list)
    raw_score: float = 0.0
    max_raw_score: float = 0.0

    # ------------------------------------------------------------------
    # Human-readable output
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a concise one-line summary of the scan result."""
        surfaced_str = "✅ SURFACED" if self.surfaced else "🚫 SUPPRESSED"
        return (
            f"[{self.grade}] {self.direction} | score={self.score:.2f} | {surfaced_str}"
        )

    def report(self) -> str:
        """Return a full human-readable multi-section report."""
        lines: list[str] = [
            "=" * 60,
            "  TRADE SCANNER — SETUP GRADE REPORT",
            "=" * 60,
            f"  Direction   : {self.direction}",
            f"  Grade       : {self.grade}",
            f"  Score       : {self.score:.4f}  ({self.raw_score:.1f} / {self.max_raw_score:.1f} pts)",
            f"  Surfaced    : {'YES — A+ opportunity' if self.surfaced else 'NO — suppressed'}",
            "",
        ]

        if self.reasons:
            lines.append("  ✅ CONFLUENCES (why this setup qualifies):")
            for r in self.reasons:
                lines.append(f"     • {r}")
            lines.append("")

        if self.cautions:
            lines.append("  ⚠️  CAUTIONS (reduce conviction):")
            for c in self.cautions:
                lines.append(f"     • {c}")
            lines.append("")

        if self.blockers:
            lines.append("  🚫 BLOCKERS (why this setup is rejected):")
            for b in self.blockers:
                lines.append(f"     • {b}")
            lines.append("")

        lines.append("  REVIEWER BREAKDOWN:")
        lines.append(f"  {'Reviewer':<22} {'Score':>7}  {'Pct':>6}")
        lines.append("  " + "-" * 38)
        for rv in self.reviewer_results:
            bar = _pct_bar(rv.pct)
            lines.append(
                f"  {rv.name:<22} {rv.score:>4.1f}/{rv.max_score:<4.1f}  {rv.pct:>5.0%}  {bar}"
            )

        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable dict for use in logs or JSON reports."""
        return {
            "direction": self.direction,
            "grade": self.grade,
            "score": round(self.score, 4),
            "surfaced": self.surfaced,
            "raw_score": round(self.raw_score, 2),
            "max_raw_score": round(self.max_raw_score, 2),
            "reasons": list(self.reasons),
            "cautions": list(self.cautions),
            "blockers": list(self.blockers),
            "reviewers": [
                {
                    "name": rv.name,
                    "score": round(rv.score, 2),
                    "max_score": round(rv.max_score, 2),
                    "pct": round(rv.pct, 4),
                    "reasons": list(rv.reasons),
                    "cautions": list(rv.cautions),
                    "blockers": list(rv.blockers),
                }
                for rv in self.reviewer_results
            ],
        }


def _pct_bar(pct: float, width: int = 10) -> str:
    filled = round(pct * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


# ---------------------------------------------------------------------------
# Main grading function
# ---------------------------------------------------------------------------

def grade_setup(ctx: ScanContext, only_a_plus: bool = False) -> ScanResult:
    """Grade a trade setup and return a :class:`ScanResult`.

    Parameters
    ----------
    ctx:
        Market data and state for the current bar.
    only_a_plus:
        When ``True``, only A+ setups will be surfaced.  Lower-grade setups
        are still evaluated and logged but ``surfaced`` will be ``False``.

    Returns
    -------
    ScanResult
        Full grading result including direction, grade, score, reasons,
        blockers, and per-reviewer breakdown.
    """
    reviewer_results = run_all_reviewers(ctx)

    # Aggregate raw scores
    raw_score = sum(r.score for r in reviewer_results)
    max_raw_score = sum(r.max_score for r in reviewer_results)
    norm_score = round(raw_score / max_raw_score, 4) if max_raw_score > 0 else 0.0

    # Collect reasons, cautions, blockers from all reviewers
    all_reasons: list[str] = [r for rv in reviewer_results for r in rv.reasons]
    all_cautions: list[str] = [c for rv in reviewer_results for c in rv.cautions]
    all_blockers: list[str] = [b for rv in reviewer_results for b in rv.blockers]

    # Direction
    direction = _infer_direction(ctx, reviewer_results)

    # Grade — hard REJECTED if any blockers exist
    if all_blockers:
        grade = _REJECTED_GRADE
        norm_score = min(norm_score, 0.44)  # cap below C threshold for blocker cases
    else:
        grade = _compute_grade(norm_score)

    # A+ only mode surfacing
    if only_a_plus:
        surfaced = grade == "A+" and direction != "NONE"
    else:
        surfaced = grade not in (_REJECTED_GRADE, "C") and direction != "NONE"

    return ScanResult(
        direction=direction,
        grade=grade,
        score=norm_score,
        surfaced=surfaced,
        reasons=all_reasons,
        cautions=all_cautions,
        blockers=all_blockers,
        reviewer_results=reviewer_results,
        raw_score=raw_score,
        max_raw_score=max_raw_score,
    )
