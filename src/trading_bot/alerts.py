from __future__ import annotations

from typing import Iterable


def _normalize_reason(reason: str | None) -> str:
    if not reason:
        return "setup rejected"
    prefix = "NO TRADE — "
    return reason[len(prefix) :] if reason.startswith(prefix) else reason


def format_scan_result(result) -> str:
    """Format a single scan result as Telegram/dashboard-style text."""
    symbol = getattr(result, "symbol", "UNKNOWN")
    control_result = getattr(result, "control_result", None)
    if control_result is not None and not control_result.allowed:
        reason = _normalize_reason(control_result.blocker_reason)
        icon = "⏸" if "cooldown" in reason else "🚫" if "session cap" in reason else "❌"
        return f"{icon} NO TRADE — {reason} — {symbol}"

    direction = getattr(result, "direction", "NO TRADE")
    grade = getattr(result, "grade", "REJECTED")
    score = float(getattr(result, "score", 0.0))
    if direction == "NO TRADE" or grade == "REJECTED":
        blockers = getattr(result, "blockers", []) or []
        reason = _normalize_reason(blockers[0] if blockers else "setup rejected")
        return f"❌ NO TRADE — {reason} — {symbol}"
    return f"✅ {grade} {direction}  — {symbol}  — Score {score:.2f}"


def format_scan_board(results: Iterable) -> str:
    """Format full scan board as text."""
    results = list(results)
    tradable = [result for result in results if getattr(result, "is_tradable", False)]
    blocked = [result for result in results if not getattr(result, "is_tradable", False)]

    lines = ["MT5 Scan Board", "Tradable:"]
    if tradable:
        lines.extend(format_scan_result(result) for result in tradable)
    else:
        lines.append("None")

    lines.extend(["", "All Results:"])
    lines.extend(format_scan_result(result) for result in results)

    if blocked:
        lines.extend(["", "Diagnostic / Blocked:"])
        lines.extend(format_scan_result(result) for result in blocked)
    return "\n".join(lines)


def format_blocked_alert(symbol: str, reason: str) -> str:
    """Format a blocked trade alert."""
    return f"🚫 NO TRADE — {_normalize_reason(reason)} — {symbol}"
