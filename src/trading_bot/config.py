"""
Configuration for the trading bot scanner / grader.

All A+ controls live here so behaviour is fully deterministic and transparent.
Adjust these values to tune selectivity without touching scorer logic.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

@dataclass
class GradeThresholds:
    """Score-to-grade mapping.

    A+ is intentionally placed high and enforced with extra hard requirements
    so it represents genuinely rare, high-quality setups.
    """

    # Minimum raw score (out of 100) to reach each grade
    a_plus: int = 90
    a: int = 80
    b: int = 70
    c: int = 60

    # --- A+ extra hard requirements (must ALL pass for A+) ----------------
    # Minimum *score* each reviewer must contribute (not just total)
    a_plus_trend_min: int = 20       # TrendReviewer max = 25
    a_plus_momentum_min: int = 15    # MomentumReviewer max = 20
    a_plus_volatility_min: int = 11  # VolatilityReviewer max = 15
    a_plus_execution_min: int = 11   # ExecutionReviewer max = 15
    a_plus_risk_min: int = 11        # RiskReviewer max = 15
    a_plus_session_min: int = 7      # SessionReviewer max = 10

    # Minimum number of reviewers that must individually pass their threshold
    a_plus_min_reviewers_passing: int = 6  # all six must pass for A+

    # Minimum R:R ratio required for A+
    a_plus_min_rr: float = 2.0

    # Minimum room-to-target expressed in ATR multiples required for A+
    a_plus_min_room_atr: float = 2.0

    # Minimum HTF trend alignment quality score (0-10) required for A+
    a_plus_min_htf_score: int = 8


# ---------------------------------------------------------------------------
# Reviewer-level controls
# ---------------------------------------------------------------------------

@dataclass
class ReviewerConfig:
    """Controls passed to individual reviewers."""

    # Spread (in price points / pips) above which execution is penalised
    max_spread_points: float = 3.0      # hard block above this value
    warn_spread_points: float = 2.0     # caution below hard block

    # ATR (14, M5 bars) healthy range for XAUUSD in points
    min_atr_points: float = 5.0
    max_atr_points: float = 60.0

    # Minimum R:R ratio to qualify for high risk score
    min_rr_ratio: float = 2.0
    # Below this ratio the setup is a hard blocker
    hard_block_rr_ratio: float = 1.2

    # Minimum room to target expressed as price distance / stop distance
    min_room_to_target_r: float = 2.0
    hard_block_room_r: float = 1.0

    # EMA periods (for trend reviewer)
    ema_fast: int = 9
    ema_mid: int = 21
    ema_slow: int = 50
    ema_200: int = 200

    # RSI period and thresholds
    rsi_period: int = 14
    rsi_bull_min: int = 50
    rsi_bear_max: int = 50
    rsi_overbought: int = 75    # caution if above this on a buy
    rsi_oversold: int = 25      # caution if below this on a sell

    # Session definitions (UTC hours, inclusive)
    london_open: int = 7
    london_close: int = 12
    new_york_open: int = 13
    new_york_close: int = 17
    london_ny_overlap_start: int = 13
    london_ny_overlap_end: int = 16

    # MACD parameters
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


# ---------------------------------------------------------------------------
# Top-level scanner / CLI config
# ---------------------------------------------------------------------------

@dataclass
class ScannerConfig:
    """Top-level config consumed by Scanner and CLI."""

    symbol: str = "XAUUSD"

    # Grade / reviewer controls
    grades: GradeThresholds = field(default_factory=GradeThresholds)
    reviewer: ReviewerConfig = field(default_factory=ReviewerConfig)

    # Filter: when True, suppress any result that is not A+
    only_a_plus: bool = False

    # Output format: "report" | "compact" | "telegram" | "json"
    output_format: str = "report"

    # Mode: "scan" | "backtest" | "paper" | "mt5"
    mode: str = "scan"

    # Backtest / paper data files
    data_file: str = ""
    settings_file: str = ""
    news_file: str = ""

    # MT5 broker settings
    mt5_magic: int = 123456
    mt5_deviation: int = 20
    trade_enabled: bool = False
    max_open_positions: int = 1
    risk_per_trade: float = 0.25   # percent


DEFAULT_CONFIG = ScannerConfig()
