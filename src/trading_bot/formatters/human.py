"""Human-readable full report formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scanner.scanner import ScanResult


_GRADE_EMOJI = {
    "A+": "🏆",
    "A":  "✅",
    "B":  "🔵",
    "C":  "🟡",
    "REJECTED": "🚫",
}

_DIR_EMOJI = {
    "LONG":     "📈",
    "SHORT":    "📉",
    "NO TRADE": "⏸ ",
}


def format_report(result: "ScanResult") -> str:
    """
    Full human-readable scan report.

    Suitable for CLI / operator logs where verbosity is acceptable.
    """
    r = result.report
    c = result.candidate
    grade_sym = _GRADE_EMOJI.get(r.grade, "")
    dir_sym = _DIR_EMOJI.get(c.direction, "")

    ts = result.timestamp.strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "═" * 60,
        f"  XAUUSD SCAN RESULT  ·  {ts}",
        "═" * 60,
        f"  Symbol    : {result.symbol}",
        f"  Session   : {result.session_label}",
        f"  Direction : {dir_sym} {c.direction}",
        f"  Grade     : {grade_sym} {r.grade}",
        f"  Score     : {r.score}/100",
        "─" * 60,
    ]

    if r.reasons:
        lines.append("  ✔  WHY THIS SETUP QUALIFIES")
        for reason in r.reasons:
            lines.append(f"     · {reason}")

    if r.cautions:
        lines.append("  ⚠  CAUTIONS")
        for caution in r.cautions:
            lines.append(f"     · {caution}")

    if r.blockers:
        lines.append("  ✖  BLOCKERS (forced REJECTED)")
        for blocker in r.blockers:
            lines.append(f"     · {blocker}")

    if r.a_plus_gap:
        lines.append("  ℹ  WHY NOT A+")
        for gap in r.a_plus_gap:
            lines.append(f"     · {gap}")

    lines.append("─" * 60)
    lines.append("  REVIEWER BREAKDOWN")
    for rev in r.reviews:
        pass_flag = "✔" if rev.passed else "✘"
        lines.append(
            f"  {pass_flag} {rev.reviewer_name:<12} {rev.score:>3}/{rev.max_score:<3}"
            f"  ({rev.score_pct:.0f}%)"
        )

    lines.append("─" * 60)
    if c.entry_price:
        lines.append(f"  Entry   : {c.entry_price:.2f}")
        lines.append(f"  Stop    : {c.stop_price:.2f}  (dist: {c.stop_distance:.1f} pts)")
        lines.append(f"  Target  : {c.target_price:.2f}  (R:R = {c.rr:.1f})")

    lines.append("═" * 60)
    return "\n".join(lines)
