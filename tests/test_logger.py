import csv
import json
import os
from datetime import datetime, timezone

from trading_bot.features import FeatureSet
from trading_bot.grader import GradeResult
from trading_bot.logger import ScanLogger
from trading_bot.trade_ideas import TradeIdea


def make_trade_idea():
    return TradeIdea(
        symbol="XAUUSD",
        direction="LONG",
        entry=2371.50,
        entry_zone_low=2371.20,
        entry_zone_high=2371.50,
        stop_loss=2369.70,
        take_profit_1=2373.70,
        take_profit_2=2375.90,
        take_profit_3=2378.10,
        risk_reward_1=0.67,
        risk_reward_2=1.33,
        grade="A+",
        score=0.92,
        reasons=["HTF aligned", "ADX trending (28.5)"],
        blockers=[],
        timestamp="2024-01-15T09:32:15+00:00",
        session="London",
        atr=1.8,
        model_note="First-pass research aid.",
    )


def make_grade_result():
    return GradeResult(
        symbol="XAUUSD",
        grade="A+",
        score=0.92,
        direction="LONG",
        reasons=["HTF aligned"],
        blockers=[],
        surfaced=True,
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
        session="London",
        spread_atr_ratio=0.1,
    )


def test_logger_creates_files(tmp_path):
    logger = ScanLogger(str(tmp_path))
    logger.close()
    logger2 = ScanLogger(str(tmp_path))
    grade = make_grade_result()
    logger2.log_scan_result("XAUUSD", grade)
    logger2.flush()
    assert os.path.exists(os.path.join(str(tmp_path), "scan_history.jsonl"))


def test_scan_log_jsonl_format(tmp_path):
    logger = ScanLogger(str(tmp_path))
    grade = make_grade_result()
    logger.log_scan_result("XAUUSD", grade)
    logger.flush()

    log_path = os.path.join(str(tmp_path), "scan_history.jsonl")
    with open(log_path) as handle:
        line = handle.readline()
    record = json.loads(line)
    assert record["symbol"] == "XAUUSD"
    assert record["grade"] == "A+"
    assert record["direction"] == "LONG"
    assert "timestamp" in record
    assert "score" in record


def test_alert_log_jsonl_format(tmp_path):
    logger = ScanLogger(str(tmp_path))
    idea = make_trade_idea()
    logger.log_alert(idea)
    logger.flush()

    log_path = os.path.join(str(tmp_path), "alerts.jsonl")
    with open(log_path) as handle:
        line = handle.readline()
    record = json.loads(line)
    assert record["symbol"] == "XAUUSD"
    assert record["direction"] == "LONG"
    assert record["grade"] == "A+"


def test_trade_ideas_csv(tmp_path):
    logger = ScanLogger(str(tmp_path))
    idea = make_trade_idea()
    logger.log_alert(idea)
    logger.flush()

    csv_path = os.path.join(str(tmp_path), "trade_ideas.csv")
    with open(csv_path) as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "XAUUSD"
    assert rows[0]["direction"] == "LONG"
    assert rows[0]["grade"] == "A+"


def test_multiple_scans_appended(tmp_path):
    logger = ScanLogger(str(tmp_path))
    grade = make_grade_result()
    for _ in range(3):
        logger.log_scan_result("XAUUSD", grade)
    logger.flush()

    log_path = os.path.join(str(tmp_path), "scan_history.jsonl")
    with open(log_path) as handle:
        lines = handle.readlines()
    assert len(lines) == 3
