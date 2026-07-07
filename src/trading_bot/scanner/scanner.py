"""
Scanner: determines trade direction and runs the grader.

The scanner inspects multi-timeframe OHLCV data, decides LONG/SHORT/NO TRADE,
then passes the candidate to the Grader which scores all six reviewers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from ..config import ScannerConfig, DEFAULT_CONFIG
from .grader import Grader, GradeReport
from .reviewers import _ema, _rsi, _atr

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SetupCandidate:
    """Minimal description of a detected trade setup before grading."""

    direction: str          # LONG | SHORT | NO TRADE
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    rr: float = 0.0
    stop_distance: float = 0.0
    room_r: float = 0.0
    signal_bar: Optional[pd.Timestamp] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Full output of a single scan pass."""

    symbol: str
    timestamp: datetime
    candidate: SetupCandidate
    report: GradeReport
    session_label: str = ""          # e.g. "London/NY Overlap"
    utc_hour: Optional[int] = None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def direction(self) -> str:
        return self.candidate.direction

    @property
    def grade(self) -> str:
        return self.report.grade

    @property
    def score(self) -> int:
        return self.report.score

    @property
    def is_a_plus(self) -> bool:
        return self.report.is_a_plus

    @property
    def is_tradeable(self) -> bool:
        return self.report.is_tradeable


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class Scanner:
    """
    Scans multi-timeframe OHLCV data, detects a setup, and grades it.

    Parameters
    ----------
    config:
        ScannerConfig.  Pass ``only_a_plus=True`` to suppress non-A+ results.

    Usage::

        scanner = Scanner(config)
        result = scanner.scan(m1_df, m5_df, m15_df, extra={...})
        if result is not None:
            print(result.grade)
    """

    def __init__(self, config: Optional[ScannerConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.grader = Grader(
            grade_cfg=self.config.grades,
            reviewer_cfg=self.config.reviewer,
        )

    def scan(
        self,
        m1: pd.DataFrame,
        m5: pd.DataFrame,
        m15: pd.DataFrame,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScanResult]:
        """
        Perform a full scan pass.

        Returns ``None`` if no setup was found or if ``only_a_plus`` is True
        and the result is not A+.
        """
        extra = extra or {}

        # ---- Step 1: determine direction ----
        candidate = self._detect_setup(m1, m5, m15, extra)

        # ---- Step 2: grade the candidate ----
        report = self.grader.grade(m1, m5, m15, candidate.direction, extra={
            **extra,
            "room_r": candidate.room_r,
            "rr": candidate.rr,
            "stop_distance": candidate.stop_distance,
        })

        # ---- Step 3: resolve session label ----
        utc_hour = extra.get("utc_hour")
        if utc_hour is None and len(m1) > 0 and isinstance(m1.index, pd.DatetimeIndex):
            utc_hour = m1.index[-1].hour
        session_label = _session_label(utc_hour, self.config.reviewer)

        # ---- Step 4: build timestamp ----
        if len(m1) > 0 and isinstance(m1.index, pd.DatetimeIndex):
            ts = m1.index[-1].to_pydatetime()
        else:
            ts = datetime.now(tz=timezone.utc)

        result = ScanResult(
            symbol=self.config.symbol,
            timestamp=ts,
            candidate=candidate,
            report=report,
            session_label=session_label,
            utc_hour=utc_hour,
        )

        # ---- Step 5: apply A+ filter ----
        if self.config.only_a_plus and not result.is_a_plus:
            logger.debug(
                "A+ only mode: suppressing %s grade=%s score=%d",
                result.direction,
                result.grade,
                result.score,
            )
            return None

        return result

    # ------------------------------------------------------------------
    # Direction detection
    # ------------------------------------------------------------------

    def _detect_setup(
        self,
        m1: pd.DataFrame,
        m5: pd.DataFrame,
        m15: pd.DataFrame,
        extra: Dict[str, Any],
    ) -> SetupCandidate:
        """
        Determine LONG / SHORT / NO TRADE direction.

        Uses a simple, transparent rule set:
        - M15 EMA trend defines the bias
        - M5 confirms or rejects
        - M1 trigger candle confirms entry timing
        """
        cfg = self.config.reviewer

        if len(m5) < cfg.ema_slow or len(m15) < cfg.ema_slow:
            return SetupCandidate(direction="NO TRADE", notes=["Insufficient data"])

        # M15 bias
        e50_15 = _ema(m15["close"], cfg.ema_slow).iloc[-1]
        e21_15 = _ema(m15["close"], cfg.ema_mid).iloc[-1]
        close_15 = m15["close"].iloc[-1]
        m15_bull = close_15 > e50_15 and e21_15 > e50_15
        m15_bear = close_15 < e50_15 and e21_15 < e50_15

        # M5 confirmation
        e21_5 = _ema(m5["close"], cfg.ema_mid).iloc[-1]
        e9_5  = _ema(m5["close"], cfg.ema_fast).iloc[-1]
        close_5 = m5["close"].iloc[-1]
        m5_bull = close_5 > e21_5 and e9_5 > e21_5
        m5_bear = close_5 < e21_5 and e9_5 < e21_5

        # RSI cross-check
        rsi_5 = _rsi(m5["close"], cfg.rsi_period).iloc[-1] if len(m5) >= cfg.rsi_period + 5 else 50.0

        # M1 trigger (last bar body direction)
        if len(m1) >= 2:
            last_m1 = m1.iloc[-1]
            m1_bull_trigger = last_m1["close"] > last_m1["open"]
        else:
            m1_bull_trigger = None

        # Combine
        if m15_bull and m5_bull and rsi_5 > cfg.rsi_bull_min:
            if m1_bull_trigger is not False:
                direction = "LONG"
            else:
                direction = "LONG"   # still long — M1 dip can be entry
        elif m15_bear and m5_bear and rsi_5 < cfg.rsi_bear_max:
            direction = "SHORT"
        else:
            return SetupCandidate(direction="NO TRADE", notes=["No confluent directional bias"])

        # ---- Estimate SL / TP from ATR ----
        atr = _atr(m5).iloc[-1] if len(m5) >= 15 else 10.0
        entry = m5["close"].iloc[-1]
        stop_dist = atr * 1.5
        target_dist = atr * 3.0

        if direction == "LONG":
            stop = entry - stop_dist
            target = entry + target_dist
        else:
            stop = entry + stop_dist
            target = entry - target_dist

        rr = target_dist / stop_dist if stop_dist > 0 else 0.0

        return SetupCandidate(
            direction=direction,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            rr=rr,
            stop_distance=stop_dist,
            room_r=rr,
        )


# ---------------------------------------------------------------------------
# Session label helper
# ---------------------------------------------------------------------------

def _session_label(utc_hour: Optional[int], cfg) -> str:
    if utc_hour is None:
        return "Unknown Session"
    if cfg.london_ny_overlap_start <= utc_hour < cfg.london_ny_overlap_end:
        return "London/NY Overlap"
    if cfg.london_open <= utc_hour < cfg.london_close:
        return "London Session"
    if cfg.new_york_open <= utc_hour < cfg.new_york_close:
        return "New York Session"
    return "Off-Peak Session"
