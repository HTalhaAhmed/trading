from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    side: str
    entry_price: float
    stop_price: float
    take_profit_price: float
    size: float
    entry_time: str


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    reason: str


@dataclass
class PortfolioState:
    equity: float
    position: Position | None = None
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict[str, float | str]] = field(default_factory=list)

    def mark_to_market(self, ts: str, price: float) -> None:
        floating = 0.0
        if self.position:
            direction = 1 if self.position.side == "long" else -1
            floating = (price - self.position.entry_price) * direction * self.position.size
        self.equity_curve.append({"timestamp": ts, "equity": self.equity + floating})

    def open_position(self, position: Position) -> None:
        self.position = position

    def close_position(self, ts: str, price: float, reason: str) -> float:
        if not self.position:
            return 0.0

        direction = 1 if self.position.side == "long" else -1
        pnl = (price - self.position.entry_price) * direction * self.position.size
        self.equity += pnl
        self.trades.append(
            Trade(
                entry_time=self.position.entry_time,
                exit_time=ts,
                side=self.position.side,
                entry_price=self.position.entry_price,
                exit_price=price,
                size=self.position.size,
                pnl=pnl,
                reason=reason,
            )
        )
        self.position = None
        return pnl
