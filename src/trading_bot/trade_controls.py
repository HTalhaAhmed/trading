from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_datetime(value: datetime | None = None) -> datetime:
    value = value or utc_now()
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def resolve_session(now: datetime | None = None) -> str:
    now = normalize_datetime(now)
    hour = now.hour
    if 7 <= hour < 16:
        return 'london'
    if 12 <= hour < 21:
        return 'ny'
    if 0 <= hour < 9:
        return 'tokyo'
    if hour >= 21 or hour < 6:
        return 'sydney'
    return 'off'


@dataclass(slots=True)
class TradeRecord:
    symbol: str
    timestamp: datetime
    session: str


class TradeCounter:
    """Persistent in-process tracking of executed trades per symbol per day."""

    def __init__(self, max_per_symbol_per_day: int = 5, max_total_per_day: int = 8):
        self._lock = threading.Lock()
        self._records: list[TradeRecord] = []
        self.max_per_symbol_per_day = max_per_symbol_per_day
        self.max_total_per_day = max_total_per_day

    def record_trade(self, symbol: str, timestamp: datetime = None, session: str = 'unknown') -> None:
        timestamp = normalize_datetime(timestamp)
        with self._lock:
            self._records.append(TradeRecord(symbol=symbol, timestamp=timestamp, session=session))

    def _filter_records_for_day(self, today: date) -> list[TradeRecord]:
        return [record for record in self._records if record.timestamp.date() == today]

    def get_count_for_symbol_today(self, symbol: str, today: date = None) -> int:
        target = today or utc_now().date()
        with self._lock:
            return sum(1 for record in self._filter_records_for_day(target) if record.symbol == symbol)

    def get_total_count_today(self, today: date = None) -> int:
        target = today or utc_now().date()
        with self._lock:
            return len(self._filter_records_for_day(target))

    def is_symbol_capped(self, symbol: str, today: date = None) -> bool:
        return self.get_count_for_symbol_today(symbol, today) >= self.max_per_symbol_per_day

    def is_total_capped(self, today: date = None) -> bool:
        return self.get_total_count_today(today) >= self.max_total_per_day

    def reset_for_day(self, today: date = None) -> None:
        target = today or utc_now().date()
        with self._lock:
            self._records = [record for record in self._records if record.timestamp.date() != target]

    def _today_records(self, today: date = None) -> list[TradeRecord]:
        target = today or utc_now().date()
        with self._lock:
            return list(self._filter_records_for_day(target))


class CooldownTracker:
    """Tracks cooldown timers between trades for the same symbol."""

    def __init__(self, min_minutes_between_trades: int = 20):
        self._lock = threading.Lock()
        self._last_trade_time: dict[str, datetime] = {}
        self.min_minutes_between_trades = min_minutes_between_trades

    def record_trade(self, symbol: str, timestamp: datetime = None) -> None:
        timestamp = normalize_datetime(timestamp)
        with self._lock:
            self._last_trade_time[symbol] = timestamp

    def is_in_cooldown(self, symbol: str, now: datetime = None) -> bool:
        now = normalize_datetime(now)
        with self._lock:
            last_trade = self._last_trade_time.get(symbol)
        if last_trade is None:
            return False
        return now < last_trade + timedelta(minutes=self.min_minutes_between_trades)

    def cooldown_remaining_minutes(self, symbol: str, now: datetime = None) -> int:
        now = normalize_datetime(now)
        with self._lock:
            last_trade = self._last_trade_time.get(symbol)
        if last_trade is None:
            return 0
        remaining = (last_trade + timedelta(minutes=self.min_minutes_between_trades) - now).total_seconds()
        if remaining <= 0:
            return 0
        return math.ceil(remaining / 60.0)


class SessionCapTracker:
    """Tracks trades per session per symbol."""

    def __init__(self, max_per_session: int = 2):
        self._lock = threading.Lock()
        self._session_records: list[tuple[str, str, datetime]] = []
        self.max_per_session = max_per_session

    def record_trade(self, symbol: str, session: str, timestamp: datetime = None) -> None:
        timestamp = normalize_datetime(timestamp)
        with self._lock:
            self._session_records.append((symbol, session, timestamp))

    def get_count_for_symbol_session(self, symbol: str, session: str, today: date = None) -> int:
        target = today or utc_now().date()
        with self._lock:
            return sum(
                1
                for item_symbol, item_session, item_time in self._session_records
                if item_symbol == symbol and item_session == session and item_time.date() == target
            )

    def is_session_capped(self, symbol: str, session: str, today: date = None) -> bool:
        return self.get_count_for_symbol_session(symbol, session, today) >= self.max_per_session

    def _get_current_session(self, now: datetime = None) -> str:
        return resolve_session(now)


@dataclass(slots=True)
class ControlCheckResult:
    allowed: bool
    blocker_reason: Optional[str] = None
    symbol: str = ''
    session: str = ''


class TradeControlManager:
    """Combines all trade controls: daily cap, session cap, cooldown."""

    def __init__(self, config: dict):
        risk = config.get('risk_limits', {})
        self.trade_counter = TradeCounter(
            max_per_symbol_per_day=risk.get('max_trades_per_symbol_per_day', 5),
            max_total_per_day=risk.get('max_trades_total_per_day', 8),
        )
        self.cooldown_tracker = CooldownTracker(
            min_minutes_between_trades=risk.get('min_minutes_between_trades', 20),
        )
        self.session_cap_tracker = SessionCapTracker(
            max_per_session=risk.get('max_trades_per_session', 2),
        )

    def check(self, symbol: str, now: datetime = None) -> ControlCheckResult:
        now = normalize_datetime(now)
        today = now.date()
        session = self.session_cap_tracker._get_current_session(now)

        if self.trade_counter.is_symbol_capped(symbol, today=today):
            count = self.trade_counter.get_count_for_symbol_today(symbol, today=today)
            cap = self.trade_counter.max_per_symbol_per_day
            return ControlCheckResult(
                allowed=False,
                blocker_reason=f'NO TRADE — daily symbol cap reached ({count}/{cap})',
                symbol=symbol,
                session=session,
            )

        if self.trade_counter.is_total_capped(today=today):
            count = self.trade_counter.get_total_count_today(today=today)
            cap = self.trade_counter.max_total_per_day
            return ControlCheckResult(
                allowed=False,
                blocker_reason=f'NO TRADE — total daily cap reached ({count}/{cap})',
                symbol=symbol,
                session=session,
            )

        if self.cooldown_tracker.is_in_cooldown(symbol, now):
            remaining = self.cooldown_tracker.cooldown_remaining_minutes(symbol, now)
            return ControlCheckResult(
                allowed=False,
                blocker_reason=f'NO TRADE — cooldown active ({remaining}m remaining)',
                symbol=symbol,
                session=session,
            )

        if self.session_cap_tracker.is_session_capped(symbol, session, today=today):
            count = self.session_cap_tracker.get_count_for_symbol_session(symbol, session, today=today)
            cap = self.session_cap_tracker.max_per_session
            return ControlCheckResult(
                allowed=False,
                blocker_reason=f'NO TRADE — session cap reached ({count}/{cap} in {session})',
                symbol=symbol,
                session=session,
            )

        return ControlCheckResult(allowed=True, symbol=symbol, session=session)

    def record_trade(self, symbol: str, now: datetime = None) -> None:
        now = normalize_datetime(now)
        session = self.session_cap_tracker._get_current_session(now)
        self.trade_counter.record_trade(symbol, now, session)
        self.cooldown_tracker.record_trade(symbol, now)
        self.session_cap_tracker.record_trade(symbol, session, now)

    def execution_guard(self, symbol: str, now: datetime = None) -> ControlCheckResult:
        return self.check(symbol, now)
