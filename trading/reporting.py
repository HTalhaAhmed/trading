from __future__ import annotations

from collections import Counter

from .models import GateStatus, SignalAssessment


def summarize_signal_quality(assessments: list[SignalAssessment]) -> dict:
    grade_counts = Counter(a.grade for a in assessments)
    blocked_counts = Counter(reason for a in assessments for reason in a.blocked_reasons)
    return {
        "total_signals": len(assessments),
        "grade_distribution": dict(grade_counts),
        "blocked_reasons": dict(blocked_counts),
    }


def summarize_gate_status(gate_status: GateStatus) -> dict:
    return {
        "eligible_for_scaling": gate_status.eligible_for_scaling,
        "eligible_for_live": gate_status.eligible_for_live,
        "gate_fail_reasons": gate_status.reasons,
    }
