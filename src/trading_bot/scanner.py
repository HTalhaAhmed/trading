from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from trading_bot.alerts import format_board
from trading_bot.caps import CapsManager
from trading_bot.features import compute_features
from trading_bot.grader import GradeResult, grade_symbol
from trading_bot.logger import ScanLogger
from trading_bot.trade_ideas import TradeIdea, generate_trade_idea


@dataclass
class ScanCycleResult:
    cycle_id: str
    timestamp: str
    surfaced: list
    suppressed: list
    errors: list
    session: str


class MT5Scanner:
    def __init__(self, config: dict, mt5_client, caps_manager: CapsManager, scan_logger: ScanLogger):
        self.config = config
        self.mt5_client = mt5_client
        self.caps_manager = caps_manager
        self.scan_logger = scan_logger

    def _grade_rank(self, trade_idea: TradeIdea) -> tuple[int, float]:
        rank = {"A+": 0, "A": 1, "B": 2, "C": 3, "NO_TRADE": 4}
        return (rank.get(trade_idea.grade, 99), -trade_idea.score)

    def scan_all(self) -> ScanCycleResult:
        cycle_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)
        surfaced_candidates: list[TradeIdea] = []
        suppressed: list[dict] = []
        errors: list[dict] = []

        watchlist = list(self.config.get("broker", {}).get("watchlist", []))
        available_symbols = set(self.mt5_client.get_symbols())
        all_positions = self.mt5_client.get_open_positions()
        total_open = len(all_positions)

        for symbol in watchlist:
            try:
                if symbol not in available_symbols or not self.mt5_client.select_symbol(symbol):
                    raise ValueError("symbol not available in MT5")

                bars = self.mt5_client.get_bars(symbol, "M1", 500)
                if bars is None or bars.empty or len(bars) < 50:
                    raise ValueError("insufficient bar data")

                symbol_info = self.mt5_client.get_symbol_info(symbol)
                features = compute_features(
                    symbol,
                    bars,
                    ask=float(symbol_info.get("ask", 0.0)),
                    bid=float(symbol_info.get("bid", 0.0)),
                )
                session = self.caps_manager.get_session(features.timestamp)
                caps_state = self.caps_manager.check(symbol, session, all_positions, total_open)
                grade_result = grade_symbol(
                    symbol=symbol,
                    features=features,
                    spread=float(symbol_info.get("spread", 0.0)),
                    config=self.config,
                    caps_state=caps_state,
                    open_positions_total=total_open,
                )
                self.scan_logger.log_scan_result(symbol, grade_result, features)

                if grade_result.surfaced:
                    surfaced_candidates.append(generate_trade_idea(grade_result, features, symbol_info))
                else:
                    if self.config.get("logging", {}).get("log_blocked", True):
                        suppressed.append({"symbol": symbol, "grade_result": grade_result})
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

        surfaced_candidates.sort(key=self._grade_rank)
        top_n = int(self.config.get("scanner", {}).get("top_n_setups", 3))
        surfaced = surfaced_candidates[:top_n]
        for dropped in surfaced_candidates[top_n:]:
            dropped_grade = GradeResult(
                symbol=dropped.symbol,
                grade=dropped.grade,
                score=dropped.score,
                direction=dropped.direction,
                reasons=dropped.reasons,
                blockers=["not in top setups limit"],
                surfaced=False,
                timestamp=datetime.fromisoformat(dropped.timestamp),
                session=dropped.session,
                spread_atr_ratio=0.0,
            )
            suppressed.append({"symbol": dropped.symbol, "grade_result": dropped_grade})

        for idea in surfaced:
            self.scan_logger.log_alert(idea)
            self.caps_manager.record_alert(idea.symbol, idea.session)

        top_grade = surfaced[0].grade if surfaced else None
        self.scan_logger.log_cycle_summary(cycle_id, len(watchlist), len(surfaced), len(suppressed), top_grade=top_grade)
        self.scan_logger.flush()

        return ScanCycleResult(
            cycle_id=cycle_id,
            timestamp=now.isoformat(),
            surfaced=surfaced,
            suppressed=suppressed,
            errors=errors,
            session=self.caps_manager.get_session(now),
        )

    def run_continuous(self, interval_seconds: int | None = None):
        interval = interval_seconds or int(self.config.get("broker", {}).get("polling_interval_seconds", 30))
        try:
            while True:
                result = self.scan_all()
                print(format_board(result.surfaced, result.suppressed))
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Scanner stopped.")
        finally:
            self.scan_logger.flush()
            self.scan_logger.close()
            self.mt5_client.disconnect()
