from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json


@dataclass
class ModeConfig:
    mode: str = "backtest"  # backtest | paper | mt5
    trade_enabled: bool = False
    mt5_explicit_opt_in: bool = False


@dataclass
class MT5Config:
    login: int | None = None
    password: str | None = None
    server: str | None = None


@dataclass
class QualityConfig:
    only_a_plus: bool = False
    min_score: float = 0.6
    live_min_score: float = 0.8


@dataclass
class FilterConfig:
    allowed_sessions: tuple[str, ...] = ("london", "new_york")
    min_volatility_atr: float = 0.8
    max_volatility_atr: float = 2.5
    max_spread_points: float = 35.0
    max_recent_losses: int = 1
    cooldown_after_losses_minutes: int = 30
    min_room_to_target_atr: float = 1.2
    max_trigger_candle_atr_ratio: float = 1.8
    news_blackout_enabled: bool = True
    post_news_stabilization_minutes: int = 15


@dataclass
class WeightConfig:
    htf_alignment: float = 0.25
    session: float = 0.1
    volatility: float = 0.15
    spread: float = 0.15
    room_to_target: float = 0.2
    trigger_size: float = 0.15


@dataclass
class GateConfig:
    min_forward_trades: int = 30
    max_drawdown: float = 0.12
    min_profit_factor: float = 1.2
    min_expectancy: float = 0.05
    disable_after_recent_underperformance: bool = True


@dataclass
class TradingConfig:
    mode: ModeConfig = field(default_factory=ModeConfig)
    mt5: MT5Config = field(default_factory=MT5Config)
    quality: QualityConfig = field(default_factory=QualityConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)
    gates: GateConfig = field(default_factory=GateConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "TradingConfig":
        if path is None:
            return cls()
        data = json.loads(Path(path).read_text())
        return cls(
            mode=ModeConfig(**data.get("mode", {})),
            mt5=MT5Config(**data.get("mt5", {})),
            quality=QualityConfig(**data.get("quality", {})),
            filters=FilterConfig(**data.get("filters", {})),
            weights=WeightConfig(**data.get("weights", {})),
            gates=GateConfig(**data.get("gates", {})),
        )

    def as_dict(self) -> dict:
        return asdict(self)
