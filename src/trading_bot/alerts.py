from __future__ import annotations

from dataclasses import asdict, is_dataclass


def format_alert(trade_idea) -> str:
    emoji = "🟢" if trade_idea.direction == "LONG" else "🔴"
    header = f"{emoji} {trade_idea.grade} {trade_idea.direction} — {trade_idea.symbol}"
    width = max(len(header) + 4, 28)
    top = "╔" + ("═" * (width - 2)) + "╗"
    mid = f"║ {header.ljust(width - 4)} ║"
    bottom = "╚" + ("═" * (width - 2)) + "╝"
    reasons = "\n".join(f"  • {reason}" for reason in trade_idea.reasons) if trade_idea.reasons else "  • None"
    return (
        f"{top}\n{mid}\n{bottom}\n"
        f"📊 Score: {trade_idea.score:.2f} | Session: {trade_idea.session}\n\n"
        f"💰 Entry Zone: {trade_idea.entry_zone_low} – {trade_idea.entry_zone_high}\n"
        f"🛑 Stop Loss:  {trade_idea.stop_loss}\n"
        f"🎯 TP1: {trade_idea.take_profit_1}  (R/R {trade_idea.risk_reward_1:.2f}:1)\n"
        f"🎯 TP2: {trade_idea.take_profit_2}  (R/R {trade_idea.risk_reward_2:.2f}:1)\n"
        f"🎯 TP3: {trade_idea.take_profit_3}\n\n"
        f"✅ Why:\n{reasons}\n\n"
        f"⏰ {trade_idea.timestamp.replace('T', ' ').replace('+00:00', ' UTC')}\n"
        f"⚠️ Research aid. User makes final execution decision."
    )


def format_compact(trade_idea) -> str:
    return (
        f"{trade_idea.grade} {trade_idea.direction} {trade_idea.symbol} | "
        f"Score {trade_idea.score:.2f} | Entry ~{trade_idea.entry} | "
        f"SL {trade_idea.stop_loss} | TP1 {trade_idea.take_profit_1}"
    )


def format_suppressed(symbol, grade_result) -> str:
    blockers = "; ".join(grade_result.blockers) if getattr(grade_result, "blockers", None) else "not surfaced"
    return f"NO TRADE — {symbol} [{grade_result.grade}, {grade_result.score:.2f}] | {blockers}"


def format_board(surfaced, suppressed) -> str:
    lines = ["=== Opportunity Board ==="]
    if surfaced:
        lines.append("Surfaced:")
        lines.extend(f"  {format_compact(item)}" for item in surfaced)
    else:
        lines.append("Surfaced: none")
    if suppressed:
        lines.append("Suppressed:")
        for item in suppressed:
            symbol = item.get("symbol", "?")
            grade_result = item.get("grade_result")
            if grade_result is not None:
                lines.append(f"  {format_suppressed(symbol, grade_result)}")
            else:
                lines.append(f"  NO TRADE — {symbol} | {item.get('message', 'suppressed')}")
    return "\n".join(lines)


def trade_idea_to_dict(trade_idea) -> dict:
    if is_dataclass(trade_idea):
        return asdict(trade_idea)
    return dict(trade_idea)
