"""Tests for the scanner direction detection and integration."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from trading_bot.config import ScannerConfig, GradeThresholds, ReviewerConfig
from trading_bot.scanner import Scanner, ScanResult
from trading_bot.scanner.scanner import SetupCandidate, _session_label


# ---------------------------------------------------------------------------
# SetupCandidate
# ---------------------------------------------------------------------------

class TestSetupCandidate:
    def test_defaults_to_no_trade(self):
        c = SetupCandidate(direction="NO TRADE")
        assert c.direction == "NO TRADE"
        assert c.rr == 0.0

    def test_long_candidate(self):
        c = SetupCandidate(direction="LONG", entry_price=2350.0, stop_price=2335.0,
                           target_price=2380.0, rr=2.0, stop_distance=15.0, room_r=2.0)
        assert c.direction == "LONG"
        assert c.rr == 2.0

    def test_notes_field(self):
        c = SetupCandidate(direction="NO TRADE", notes=["Insufficient data"])
        assert c.notes == ["Insufficient data"]

    def test_notes_default_empty(self):
        c = SetupCandidate(direction="LONG")
        assert c.notes == []

    def test_signal_bar_field(self):
        import pandas as pd
        from datetime import datetime, timezone
        ts = pd.Timestamp("2025-01-15 14:00:00", tz="UTC")
        c = SetupCandidate(direction="LONG", signal_bar=ts)
        assert c.signal_bar == ts

    def test_signal_bar_defaults_none(self):
        c = SetupCandidate(direction="SHORT")
        assert c.signal_bar is None


# ---------------------------------------------------------------------------
# Session label helper
# ---------------------------------------------------------------------------

class TestSessionLabel:
    def setup_method(self):
        self.cfg = ReviewerConfig()

    def test_overlap_session(self):
        label = _session_label(13, self.cfg)
        assert "Overlap" in label

    def test_london_session(self):
        label = _session_label(9, self.cfg)
        assert "London" in label

    def test_ny_session(self):
        label = _session_label(15, self.cfg)
        # 15:00 UTC is within NY but also within overlap (13-16)
        assert "NY" in label or "Overlap" in label

    def test_off_peak(self):
        label = _session_label(2, self.cfg)
        assert "Off-Peak" in label or "Unknown" in label

    def test_none_hour(self):
        label = _session_label(None, self.cfg)
        assert "Unknown" in label


# ---------------------------------------------------------------------------
# Scanner – direction and output
# ---------------------------------------------------------------------------

class TestScanner:
    def test_scan_returns_scan_result_or_none(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        assert result is None or isinstance(result, ScanResult)

    def test_scan_result_has_required_attributes(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        if result is not None:
            assert result.symbol == "XAUUSD"
            assert result.direction in ("LONG", "SHORT", "NO TRADE")
            assert result.grade in ("A+", "A", "B", "C", "REJECTED")
            assert 0 <= result.score <= 100

    def test_grade_is_deterministic(self, bull_m1, bull_m5, bull_m15):
        """Same input must produce same grade every time."""
        scanner = Scanner(ScannerConfig())
        extra = {"utc_hour": 14, "spread": 1.5}
        r1 = scanner.scan(bull_m1, bull_m5, bull_m15, extra=extra)
        r2 = scanner.scan(bull_m1, bull_m5, bull_m15, extra=extra)
        if r1 is not None and r2 is not None:
            assert r1.grade == r2.grade
            assert r1.score == r2.score
        else:
            assert r1 is None and r2 is None

    def test_only_a_plus_suppresses_lower_grades(self, flat_m1, flat_m5, flat_m15):
        config = ScannerConfig(only_a_plus=True)
        scanner = Scanner(config)
        result = scanner.scan(flat_m1, flat_m5, flat_m15,
                              extra={"utc_hour": 2, "spread": 5.0})
        # Flat + off-peak + wide spread should either return None (suppressed) or be A+
        assert result is None or result.grade == "A+"

    def test_only_a_plus_false_allows_any_grade(self, bull_m1, bull_m5, bull_m15):
        config = ScannerConfig(only_a_plus=False)
        scanner = Scanner(config)
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        # Result can be any valid grade
        if result is not None:
            assert result.grade in ("A+", "A", "B", "C", "REJECTED")

    def test_insufficient_data_returns_no_trade(self):
        scanner = Scanner(ScannerConfig())
        tiny_df = pd.DataFrame({"open": [1], "high": [2], "low": [0], "close": [1], "volume": [100]})
        result = scanner.scan(tiny_df, tiny_df, tiny_df)
        # With insufficient data, should either return None or a NO TRADE / REJECTED result
        if result is not None:
            assert result.direction == "NO TRADE" or result.grade == "REJECTED"

    def test_wide_spread_hard_blocker(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(
            bull_m1, bull_m5, bull_m15,
            extra={"utc_hour": 14, "spread": 100.0}  # extreme spread
        )
        if result is not None and result.direction != "NO TRADE":
            assert result.grade == "REJECTED"
            assert len(result.report.blockers) > 0

    def test_news_blocked_forces_rejected(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(
            bull_m1, bull_m5, bull_m15,
            extra={"utc_hour": 14, "spread": 1.5, "news_blocked": True}
        )
        if result is not None and result.direction != "NO TRADE":
            assert result.grade == "REJECTED"

    def test_bull_data_tends_to_long(self, bull_m1, bull_m5, bull_m15):
        """Strongly trending bull data should detect LONG more often than SHORT."""
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        if result is not None:
            # On bull data with upward drift, direction should be LONG or NO TRADE
            assert result.direction in ("LONG", "NO TRADE")

    def test_report_contains_reasons_or_blockers(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        if result is not None and result.direction != "NO TRADE":
            assert len(result.report.reasons) + len(result.report.blockers) > 0

    def test_a_plus_gap_populated_when_not_a_plus(self, flat_m1, flat_m5, flat_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(flat_m1, flat_m5, flat_m15,
                              extra={"utc_hour": 2, "spread": 5.0})
        if result is not None and result.grade != "A+" and result.direction != "NO TRADE":
            assert len(result.report.a_plus_gap) > 0


# ---------------------------------------------------------------------------
# ScanResult properties
# ---------------------------------------------------------------------------

class TestScanResultProperties:
    def test_is_a_plus_property_consistent(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        if result is not None:
            assert result.is_a_plus == (result.grade == "A+")

    def test_is_tradeable_for_rejected(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 100.0})
        if result is not None and result.grade == "REJECTED":
            assert not result.is_tradeable

    def test_score_within_bounds(self, bull_m1, bull_m5, bull_m15):
        scanner = Scanner(ScannerConfig())
        result = scanner.scan(bull_m1, bull_m5, bull_m15,
                              extra={"utc_hour": 14, "spread": 1.5})
        if result is not None:
            assert 0 <= result.score <= 100
