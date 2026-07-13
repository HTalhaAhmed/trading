from datetime import datetime, timezone

from trading_bot.features import FeatureSet
from trading_bot.grader import GradeResult
from trading_bot.trade_ideas import TradeIdea, generate_trade_idea


def make_grade_result(direction="LONG", grade="A+", score=0.92):
    return GradeResult(
        symbol="XAUUSD",
        grade=grade,
        score=score,
        direction=direction,
        reasons=["HTF aligned", "ADX trending"],
        blockers=[],
        surfaced=True,
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
        session="London",
        spread_atr_ratio=0.1,
    )


def make_features(price=2371.35, atr14=0.8, atr14_5m=1.2):
    feature_set = FeatureSet(
        symbol="XAUUSD",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
        price=price,
    )
    feature_set.atr14 = atr14
    feature_set.atr14_5m = atr14_5m
    feature_set.trend_direction = "long"
    return feature_set


def make_symbol_info(ask=2371.50, bid=2371.40, digits=2):
    return {"ask": ask, "bid": bid, "spread": 0.10, "digits": digits, "point": 0.01}


def test_generate_long_trade_idea():
    grade = make_grade_result("LONG")
    features = make_features()
    info = make_symbol_info()
    idea = generate_trade_idea(grade, features, info)
    assert isinstance(idea, TradeIdea)
    assert idea.direction == "LONG"
    assert idea.stop_loss < idea.entry
    assert idea.take_profit_1 > idea.entry
    assert idea.take_profit_2 > idea.take_profit_1
    assert idea.take_profit_3 > idea.take_profit_2


def test_generate_short_trade_idea():
    grade = make_grade_result("SHORT")
    features = make_features()
    info = make_symbol_info()
    idea = generate_trade_idea(grade, features, info)
    assert idea.direction == "SHORT"
    assert idea.stop_loss > idea.entry
    assert idea.take_profit_1 < idea.entry
    assert idea.take_profit_2 < idea.take_profit_1


def test_risk_reward_positive():
    grade = make_grade_result("LONG")
    features = make_features()
    info = make_symbol_info()
    idea = generate_trade_idea(grade, features, info)
    assert idea.risk_reward_1 > 0
    assert idea.risk_reward_2 > idea.risk_reward_1


def test_levels_rounded_to_digits():
    grade = make_grade_result("LONG")
    features = make_features()
    info = make_symbol_info(digits=2)
    idea = generate_trade_idea(grade, features, info)
    for level in [idea.entry, idea.stop_loss, idea.take_profit_1, idea.take_profit_2]:
        assert round(level, 2) == level


def test_model_note_present():
    grade = make_grade_result("LONG")
    features = make_features()
    info = make_symbol_info()
    idea = generate_trade_idea(grade, features, info)
    assert idea.model_note
    assert "research" in idea.model_note.lower() or "aid" in idea.model_note.lower()
