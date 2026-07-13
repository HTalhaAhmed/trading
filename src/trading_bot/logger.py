from __future__ import annotations

import csv
import json
import threading
from pathlib import Path

from trading_bot.alerts import trade_idea_to_dict
from trading_bot.features import FeatureSet
from trading_bot.grader import GradeResult
from trading_bot.trade_ideas import TradeIdea


class ScanLogger:
    def __init__(self, log_dir: str = "output/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self.scan_history_path = self.log_dir / "scan_history.jsonl"
        self.alerts_path = self.log_dir / "alerts.jsonl"
        self.trade_ideas_path = self.log_dir / "trade_ideas.csv"

        self.scan_history_file = self.scan_history_path.open("a", encoding="utf-8")
        self.alerts_file = self.alerts_path.open("a", encoding="utf-8")
        self.trade_ideas_file = self.trade_ideas_path.open("a", encoding="utf-8", newline="")
        self.trade_ideas_writer = csv.DictWriter(
            self.trade_ideas_file,
            fieldnames=[
                "timestamp",
                "symbol",
                "direction",
                "grade",
                "score",
                "entry",
                "stop_loss",
                "take_profit_1",
                "take_profit_2",
                "take_profit_3",
                "risk_reward_1",
                "risk_reward_2",
                "session",
                "reasons",
                "blockers",
            ],
        )
        if self.trade_ideas_path.stat().st_size == 0:
            self.trade_ideas_writer.writeheader()
            self.trade_ideas_file.flush()

    def log_scan_result(self, symbol: str, grade_result: GradeResult, features: FeatureSet | None = None):
        record = {
            "type": "scan_result",
            "timestamp": grade_result.timestamp,
            "symbol": symbol,
            "grade": grade_result.grade,
            "score": grade_result.score,
            "direction": grade_result.direction,
            "surfaced": grade_result.surfaced,
            "reasons": grade_result.reasons,
            "blockers": grade_result.blockers,
            "session": grade_result.session,
        }
        if features is not None:
            record["price"] = features.price
            record["adx14"] = features.adx14
            record["atr14"] = features.atr14

        with self._lock:
            self.scan_history_file.write(json.dumps(record, default=str) + "\n")

    def log_alert(self, trade_idea: TradeIdea):
        payload = trade_idea_to_dict(trade_idea)
        with self._lock:
            self.alerts_file.write(json.dumps(payload, default=str) + "\n")
            self.trade_ideas_writer.writerow(
                {
                    "timestamp": trade_idea.timestamp,
                    "symbol": trade_idea.symbol,
                    "direction": trade_idea.direction,
                    "grade": trade_idea.grade,
                    "score": trade_idea.score,
                    "entry": trade_idea.entry,
                    "stop_loss": trade_idea.stop_loss,
                    "take_profit_1": trade_idea.take_profit_1,
                    "take_profit_2": trade_idea.take_profit_2,
                    "take_profit_3": trade_idea.take_profit_3,
                    "risk_reward_1": trade_idea.risk_reward_1,
                    "risk_reward_2": trade_idea.risk_reward_2,
                    "session": trade_idea.session,
                    "reasons": " | ".join(trade_idea.reasons),
                    "blockers": " | ".join(trade_idea.blockers),
                }
            )

    def log_cycle_summary(
        self,
        cycle_id: str,
        symbol_count: int,
        surfaced_count: int,
        suppressed_count: int,
        top_grade: str | None = None,
    ):
        record = {
            "type": "cycle_summary",
            "cycle_id": cycle_id,
            "symbol_count": symbol_count,
            "surfaced_count": surfaced_count,
            "suppressed_count": suppressed_count,
            "top_grade": top_grade,
        }
        with self._lock:
            self.scan_history_file.write(json.dumps(record, default=str) + "\n")

    def flush(self):
        with self._lock:
            self.scan_history_file.flush()
            self.alerts_file.flush()
            self.trade_ideas_file.flush()

    def close(self):
        with self._lock:
            self.scan_history_file.close()
            self.alerts_file.close()
            self.trade_ideas_file.close()
