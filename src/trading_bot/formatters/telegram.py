"""Telegram-friendly plain-text alert formatter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scanner.scanner import ScanResult

_MAX_REASONS = 5
_MAX_CAUTIONS = 3


def format_telegram(result: "ScanResult") -> str:
    """
    Telegram-friendly compact alert text.

    Designed to be readable in a mobile Telegram notification:
    - concise enough for messaging
    - includes all actionable information
    - avoids Markdown formatting that may break in some clients

    Example output::

        📊 XAUUSD SIGNAL
        Direction: 📈 LONG
        Grade: A+   Score: 92/100
        Session: London/NY Overlap
        Time: 2025-01-15 14:32 UTC

        ✅ REASONS
        · M15 full bull EMA stack confirmed
        · M5 bull EMA stack with price above all EMAs
        · M15 higher-highs / higher-lows structure intact
        · M5 RSI 62 in bullish momentum zone
        · London/NY overlap — highest liquidity

        ⚠ CAUTIONS
        · Momentum slightly extended

        Entry: 2345.60  Stop: 2330.60  Target: 2375.60  R:R 2.0
    """
    r = result.report
    c = result.candidate
    ts = result.timestamp.strftime("%Y-%m-%d %H:%M UTC")

    dir_sym = {"LONG": "📈", "SHORT": "📉", "NO TRADE": "⏸"}.get(c.direction, "")
    grade_sym = {"A+": "🏆", "A": "✅", "B": "🔵", "C": "🟡", "REJECTED": "🚫"}.get(r.grade, "")

    lines = [
        "📊 XAUUSD SIGNAL",
        f"Direction: {dir_sym} {c.direction}",
        f"Grade: {grade_sym} {r.grade}   Score: {r.score}/100",
        f"Session: {result.session_label}",
        f"Time: {ts}",
        "",
    ]

    if r.blockers:
        lines.append("🚫 BLOCKED")
        for b in r.blockers[:3]:
            lines.append(f"· {b}")
    elif r.reasons:
        lines.append("✅ REASONS")
        for reason in r.reasons[:_MAX_REASONS]:
            lines.append(f"· {reason}")
        if len(r.reasons) > _MAX_REASONS:
            lines.append(f"  (+{len(r.reasons) - _MAX_REASONS} more)")

    if r.cautions:
        lines.append("")
        lines.append("⚠ CAUTIONS")
        for caution in r.cautions[:_MAX_CAUTIONS]:
            lines.append(f"· {caution}")
        if len(r.cautions) > _MAX_CAUTIONS:
            lines.append(f"  (+{len(r.cautions) - _MAX_CAUTIONS} more)")

    if r.a_plus_gap and r.grade != "A+":
        lines.append("")
        lines.append("ℹ WHY NOT A+")
        for gap in r.a_plus_gap[:2]:
            lines.append(f"· {gap}")

    if c.entry_price:
        lines.append("")
        lines.append(
            f"Entry: {c.entry_price:.2f}  "
            f"Stop: {c.stop_price:.2f}  "
            f"Target: {c.target_price:.2f}  "
            f"R:R {c.rr:.1f}"
        )

    return "\n".join(lines)
