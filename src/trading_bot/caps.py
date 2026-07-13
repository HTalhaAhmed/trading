from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


class CapsManager:
    def __init__(self, config: dict):
        self.config = config
        self.max_per_symbol_day = config["risk_limits"]["max_trades_per_symbol_per_day"]
        self.max_per_session = config["risk_limits"]["max_trades_per_session"]
        self.cooldown_minutes = config["risk_limits"]["min_minutes_between_trades"]
        self.max_open_per_symbol = config["risk_limits"]["max_open_positions_per_symbol"]
        self.max_open_total = config["risk_limits"]["max_open_positions_total"]
        self._daily_counts: dict[str, int] = {}
        self._session_counts: dict[str, int] = {}
        self._cooldown_until: dict[str, datetime] = {}
        self._day: date | None = None

    def reset_if_new_day(self):
        today = datetime.now(timezone.utc).date()
        if self._day is None:
            self._day = today
            return
        if today != self._day:
            self._daily_counts = {}
            self._session_counts = {}
            self._cooldown_until = {}
            self._day = today

    def _parse_hhmm(self, value: str) -> time:
        hour, minute = (int(part) for part in value.split(":", 1))
        return time(hour=hour, minute=minute, tzinfo=timezone.utc)

    def get_session(self, dt: datetime | None = None) -> str:
        dt = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
        minutes = dt.hour * 60 + dt.minute
        if 12 * 60 <= minutes < 16 * 60:
            return "Overlap"
        if 7 * 60 <= minutes < 16 * 60:
            return "London"
        if 12 * 60 <= minutes < 21 * 60:
            return "NewYork"
        if 0 <= minutes < 9 * 60:
            return "Asian"
        return "Off-hours"

    def check(self, symbol: str, session: str, open_positions: list[dict], total_open: int) -> dict:
        self.reset_if_new_day()
        now = datetime.now(timezone.utc)
        symbol_positions = [position for position in open_positions if position.get("symbol") == symbol]
        cooldown_until = self._cooldown_until.get(symbol)
        cooldown_remaining = 0.0
        in_cooldown = False
        if cooldown_until and cooldown_until > now:
            in_cooldown = True
            cooldown_remaining = round((cooldown_until - now).total_seconds() / 60.0, 2)

        symbol_count = self._daily_counts.get(symbol, 0)
        session_count = self._session_counts.get(session, 0)
        has_open_position = len(symbol_positions) >= self.max_open_per_symbol

        return {
            "symbol_capped": symbol_count >= self.max_per_symbol_day,
            "symbol_count": symbol_count,
            "symbol_cap": self.max_per_symbol_day,
            "in_cooldown": in_cooldown,
            "cooldown_remaining_min": cooldown_remaining,
            "session_capped": session_count >= self.max_per_session,
            "session_count": session_count,
            "session_cap": self.max_per_session,
            "has_open_position": has_open_position,
            "total_positions_maxed": total_open >= self.max_open_total,
            "total_positions": total_open,
            "total_cap": self.max_open_total,
        }

    def record_alert(self, symbol: str, session: str):
        self.reset_if_new_day()
        self._daily_counts[symbol] = self._daily_counts.get(symbol, 0) + 1
        self._session_counts[session] = self._session_counts.get(session, 0) + 1
        self._cooldown_until[symbol] = datetime.now(timezone.utc) + timedelta(minutes=self.cooldown_minutes)
