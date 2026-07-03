from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SignalContext:
    direction: str
    htf_direction: str
    session: str
    atr_normalized: float
    spread_points: float
    room_to_target_atr: float
    trigger_candle_atr_ratio: float
    recent_losses: int = 0
    cooldown_remaining_minutes: int = 0
    is_news_blackout: bool = False
    minutes_since_news: int = 999


@dataclass
class SignalAssessment:
    allowed: bool
    score: float
    grade: str
    blocked_reasons: list[str] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    forward_trades: int
    max_drawdown: float
    profit_factor: float
    expectancy_r: float
    recent_underperformance: bool = False


@dataclass
class GateStatus:
    eligible_for_scaling: bool
    eligible_for_live: bool
    reasons: list[str]


@dataclass
class OrderRequest:
    symbol: str
    side: str
    volume: float
    stop_loss: float
    take_profit: float


@dataclass
class ExecutionResult:
    accepted: bool
    reason: str
    broker_order_id: str | None = None
