from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    starting_equity: float
    daily_max_loss_pct: float
    max_consecutive_losses: int

    current_day: str | None = None
    daily_pnl: float = 0.0
    consecutive_losses: int = 0

    def reset_day_if_needed(self, day_key: str) -> None:
        if self.current_day != day_key:
            self.current_day = day_key
            self.daily_pnl = 0.0
            self.consecutive_losses = 0

    def record_trade(self, pnl: float) -> None:
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def can_trade(self) -> bool:
        max_daily_loss = self.starting_equity * self.daily_max_loss_pct
        if self.daily_pnl <= -max_daily_loss:
            return False
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False
        return True
