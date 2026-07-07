"""Stable machine-readable JSON formatter for dashboard integrations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scanner.scanner import ScanResult


def format_json(result: "ScanResult") -> str:
    """
    Serialise a ScanResult to a stable JSON string.

    The schema is intentionally flat and stable so external dashboards
    can rely on key names not changing between versions.

    Schema::

        {
          "schema_version": 1,
          "symbol": "XAUUSD",
          "timestamp_utc": "2025-01-15T14:32:00+00:00",
          "session": "London/NY Overlap",
          "direction": "LONG",
          "grade": "A+",
          "score": 92,
          "max_score": 100,
          "is_a_plus": true,
          "is_tradeable": true,
          "entry": 2345.60,
          "stop": 2330.60,
          "target": 2375.60,
          "rr": 2.0,
          "stop_distance": 15.0,
          "reasons": [...],
          "cautions": [...],
          "blockers": [...],
          "a_plus_gap": [...],
          "reviewer_scores": {
            "Trend": {"score": 22, "max_score": 25, "passed": true},
            ...
          }
        }
    """
    r = result.report
    c = result.candidate

    reviewer_scores = {
        rev.reviewer_name: {
            "score": rev.score,
            "max_score": rev.max_score,
            "passed": rev.passed,
            "reasons": rev.reasons,
            "cautions": rev.cautions,
            "blockers": rev.blockers,
        }
        for rev in r.reviews
    }

    payload = {
        "schema_version": 1,
        "symbol": result.symbol,
        "timestamp_utc": result.timestamp.isoformat(),
        "session": result.session_label,
        "direction": c.direction,
        "grade": r.grade,
        "score": r.score,
        "max_score": r.max_score,
        "is_a_plus": r.is_a_plus,
        "is_tradeable": r.is_tradeable,
        "entry": round(c.entry_price, 5) if c.entry_price else None,
        "stop": round(c.stop_price, 5) if c.stop_price else None,
        "target": round(c.target_price, 5) if c.target_price else None,
        "rr": round(c.rr, 2),
        "stop_distance": round(c.stop_distance, 2),
        "reasons": r.reasons,
        "cautions": r.cautions,
        "blockers": r.blockers,
        "a_plus_gap": r.a_plus_gap,
        "reviewer_scores": reviewer_scores,
    }

    return json.dumps(payload, indent=2, ensure_ascii=False)
