"""Compact single-line / card summary formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scanner.scanner import ScanResult

_GRADE_BADGE = {
    "A+": "[A+]",
    "A":  "[ A]",
    "B":  "[ B]",
    "C":  "[ C]",
    "REJECTED": "[--]",
}


def format_compact(result: "ScanResult") -> str:
    """
    Compact one-line summary suitable for dashboard cards or log lines.

    Example::

        XAUUSD | LONG | [A+] 92/100 | London/NY Overlap | 2025-01-15 14:32 UTC
        Top: M15 full bull EMA stack | Caution: RSI near overbought
    """
    r = result.report
    c = result.candidate
    badge = _GRADE_BADGE.get(r.grade, "[??]")
    ts = result.timestamp.strftime("%Y-%m-%d %H:%M UTC")

    top_reason = r.reasons[0] if r.reasons else "No reasons"
    top_caution = f" | ⚠ {r.cautions[0]}" if r.cautions else ""
    top_blocker = f" | ✖ {r.blockers[0]}" if r.blockers else ""

    line1 = f"{result.symbol} | {c.direction} | {badge} {r.score}/100 | {result.session_label} | {ts}"
    line2 = f"  {top_reason}{top_caution}{top_blocker}"
    return f"{line1}\n{line2}"
