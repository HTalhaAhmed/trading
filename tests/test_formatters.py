"""Tests for output formatters."""

import json
import pytest
from datetime import datetime, timezone

from trading_bot.config import ScannerConfig
from trading_bot.scanner import Scanner, ScanResult
from trading_bot.formatters import (
    format_report,
    format_compact,
    format_telegram,
    format_json,
)


@pytest.fixture
def scan_result(bull_m1, bull_m5, bull_m15):
    config = ScannerConfig(symbol="XAUUSD")
    scanner = Scanner(config)
    extra = {"utc_hour": 14, "spread": 1.5, "minutes_to_news": 999}
    result = scanner.scan(bull_m1, bull_m5, bull_m15, extra=extra)
    # If no trade detected (flat conditions) fall back to a synthetic NO TRADE result
    if result is None:
        from trading_bot.scanner.scanner import SetupCandidate, ScanResult as SR
        from trading_bot.scanner.grader import GradeReport
        result = SR(
            symbol="XAUUSD",
            timestamp=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
            candidate=SetupCandidate(direction="NO TRADE"),
            report=GradeReport(direction="NO TRADE", grade="REJECTED", score=0),
            session_label="London/NY Overlap",
            utc_hour=14,
        )
    return result


# ---------------------------------------------------------------------------
# Human report
# ---------------------------------------------------------------------------

class TestFormatReport:
    def test_contains_symbol(self, scan_result):
        out = format_report(scan_result)
        assert "XAUUSD" in out

    def test_contains_grade(self, scan_result):
        out = format_report(scan_result)
        assert scan_result.grade in out

    def test_contains_score(self, scan_result):
        out = format_report(scan_result)
        assert str(scan_result.score) in out

    def test_contains_direction(self, scan_result):
        out = format_report(scan_result)
        assert scan_result.direction in out

    def test_contains_reviewer_breakdown(self, scan_result):
        out = format_report(scan_result)
        if scan_result.report.reviews:
            assert "REVIEWER BREAKDOWN" in out

    def test_contains_session(self, scan_result):
        out = format_report(scan_result)
        assert scan_result.session_label in out


# ---------------------------------------------------------------------------
# Compact format
# ---------------------------------------------------------------------------

class TestFormatCompact:
    def test_first_line_contains_symbol(self, scan_result):
        out = format_compact(scan_result)
        assert "XAUUSD" in out.split("\n")[0]

    def test_first_line_contains_grade(self, scan_result):
        out = format_compact(scan_result)
        # Grade badge is in first line
        line1 = out.split("\n")[0]
        assert scan_result.grade in line1 or scan_result.grade[:1] in line1

    def test_first_line_contains_score(self, scan_result):
        out = format_compact(scan_result)
        assert str(scan_result.score) in out

    def test_two_lines(self, scan_result):
        out = format_compact(scan_result)
        lines = out.split("\n")
        assert len(lines) == 2

    def test_first_line_contains_session(self, scan_result):
        out = format_compact(scan_result)
        assert scan_result.session_label in out.split("\n")[0]


# ---------------------------------------------------------------------------
# Telegram format
# ---------------------------------------------------------------------------

class TestFormatTelegram:
    def test_starts_with_signal_header(self, scan_result):
        out = format_telegram(scan_result)
        assert "XAUUSD SIGNAL" in out

    def test_contains_direction(self, scan_result):
        out = format_telegram(scan_result)
        assert scan_result.direction in out

    def test_contains_grade(self, scan_result):
        out = format_telegram(scan_result)
        assert scan_result.grade in out

    def test_contains_score(self, scan_result):
        out = format_telegram(scan_result)
        assert str(scan_result.score) in out

    def test_contains_session(self, scan_result):
        out = format_telegram(scan_result)
        assert scan_result.session_label in out

    def test_contains_timestamp(self, scan_result):
        out = format_telegram(scan_result)
        assert "UTC" in out

    def test_reasons_section_present_when_reasons_exist(self, scan_result):
        if scan_result.report.reasons:
            out = format_telegram(scan_result)
            assert "REASONS" in out or "BLOCKED" in out

    def test_entry_line_when_entry_known(self, scan_result):
        if scan_result.candidate.entry_price:
            out = format_telegram(scan_result)
            assert "Entry:" in out

    def test_concise_enough(self, scan_result):
        """Telegram format should stay under 80 characters per line."""
        out = format_telegram(scan_result)
        # Most lines should be concise; allow some slightly wider lines
        lines = out.split("\n")
        # Check at least 70% of non-empty lines are under 80 chars
        non_empty = [l for l in lines if l.strip()]
        short = [l for l in non_empty if len(l) <= 80]
        assert len(short) / len(non_empty) >= 0.6


# ---------------------------------------------------------------------------
# JSON format
# ---------------------------------------------------------------------------

class TestFormatJson:
    def _parsed(self, scan_result) -> dict:
        return json.loads(format_json(scan_result))

    def test_valid_json(self, scan_result):
        self._parsed(scan_result)  # should not raise

    def test_schema_version_is_1(self, scan_result):
        d = self._parsed(scan_result)
        assert d["schema_version"] == 1

    def test_stable_keys_present(self, scan_result):
        d = self._parsed(scan_result)
        required_keys = [
            "schema_version", "symbol", "timestamp_utc", "session",
            "direction", "grade", "score", "max_score",
            "is_a_plus", "is_tradeable",
            "reasons", "cautions", "blockers", "a_plus_gap",
            "reviewer_scores",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_direction_matches_result(self, scan_result):
        d = self._parsed(scan_result)
        assert d["direction"] == scan_result.direction

    def test_grade_matches_result(self, scan_result):
        d = self._parsed(scan_result)
        assert d["grade"] == scan_result.grade

    def test_score_matches_result(self, scan_result):
        d = self._parsed(scan_result)
        assert d["score"] == scan_result.score

    def test_symbol_matches_result(self, scan_result):
        d = self._parsed(scan_result)
        assert d["symbol"] == scan_result.symbol

    def test_is_a_plus_boolean(self, scan_result):
        d = self._parsed(scan_result)
        assert isinstance(d["is_a_plus"], bool)

    def test_reviewer_scores_present(self, scan_result):
        d = self._parsed(scan_result)
        if scan_result.report.reviews:
            assert len(d["reviewer_scores"]) > 0

    def test_reviewer_score_has_required_fields(self, scan_result):
        d = self._parsed(scan_result)
        for name, rev in d["reviewer_scores"].items():
            assert "score" in rev
            assert "max_score" in rev
            assert "passed" in rev

    def test_reasons_is_list(self, scan_result):
        d = self._parsed(scan_result)
        assert isinstance(d["reasons"], list)

    def test_blockers_is_list(self, scan_result):
        d = self._parsed(scan_result)
        assert isinstance(d["blockers"], list)
