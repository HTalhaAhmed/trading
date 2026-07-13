from __future__ import annotations

from dataclasses import dataclass

from trading_bot.features import FeatureSet
from trading_bot.grader import GradeResult


@dataclass
class TradeIdea:
    symbol: str
    direction: str
    entry: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_reward_1: float
    risk_reward_2: float
    grade: str
    score: float
    reasons: list[str]
    blockers: list[str]
    timestamp: str
    session: str
    atr: float
    model_note: str = "First-pass research aid. Levels are ATR-based estimates, not guaranteed."


def _round(value: float, digits: int) -> float:
    return round(float(value), int(digits))


def generate_trade_idea(
    grade_result: GradeResult,
    features: FeatureSet,
    symbol_info: dict,
) -> TradeIdea:
    digits = int(symbol_info.get("digits", 5))
    ask = float(symbol_info.get("ask", features.ask or features.price))
    bid = float(symbol_info.get("bid", features.bid or features.price))
    atr = float(features.atr14_5m or 0.0) if float(features.atr14_5m or 0.0) > 0 else float(features.atr14 or 0.0)
    if atr <= 0:
        point = float(symbol_info.get("point", 10 ** (-digits)))
        atr = max(point * 10, 10 ** (-digits))

    if grade_result.direction == "SHORT":
        entry = bid
        entry_zone_low = bid
        entry_zone_high = bid + (0.25 * atr)
        stop_loss = bid + (1.5 * atr)
        take_profit_1 = bid - (1.0 * atr)
        take_profit_2 = bid - (2.0 * atr)
        take_profit_3 = bid - (3.0 * atr)
    else:
        entry = ask
        entry_zone_low = ask - (0.25 * atr)
        entry_zone_high = ask
        stop_loss = ask - (1.5 * atr)
        take_profit_1 = ask + (1.0 * atr)
        take_profit_2 = ask + (2.0 * atr)
        take_profit_3 = ask + (3.0 * atr)

    risk = abs(entry - stop_loss) or 1e-12
    rr1 = round(abs(entry - take_profit_1) / risk, 2)
    rr2 = round(abs(entry - take_profit_2) / risk, 2)

    return TradeIdea(
        symbol=grade_result.symbol,
        direction=grade_result.direction,
        entry=_round(entry, digits),
        entry_zone_low=_round(entry_zone_low, digits),
        entry_zone_high=_round(entry_zone_high, digits),
        stop_loss=_round(stop_loss, digits),
        take_profit_1=_round(take_profit_1, digits),
        take_profit_2=_round(take_profit_2, digits),
        take_profit_3=_round(take_profit_3, digits),
        risk_reward_1=rr1,
        risk_reward_2=rr2,
        grade=grade_result.grade,
        score=grade_result.score,
        reasons=list(grade_result.reasons),
        blockers=list(grade_result.blockers),
        timestamp=grade_result.timestamp.isoformat(),
        session=grade_result.session,
        atr=round(atr, digits if digits <= 4 else 5),
    )
