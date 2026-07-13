from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "broker": {
        "mode": "mt5",
        "trade_enabled": False,
        "alert_only": True,
        "watchlist": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "XAGUSD"],
        "polling_interval_seconds": 30,
    },
    "risk_limits": {
        "max_trades_per_symbol_per_day": 5,
        "max_trades_per_session": 2,
        "min_minutes_between_trades": 20,
        "max_open_positions_per_symbol": 1,
        "max_open_positions_total": 2,
    },
    "scanner": {
        "only_a_plus": True,
        "top_n_setups": 3,
        "require_trending_market_first": True,
        "min_adx": 20,
        "max_spread_atr_ratio": 0.3,
    },
    "logging": {
        "log_dir": "output/logs",
        "log_scan_results": True,
        "log_alerts": True,
        "log_blocked": True,
    },
    "sessions": {
        "london_start_utc": "07:00",
        "london_end_utc": "16:00",
        "newyork_start_utc": "12:00",
        "newyork_end_utc": "21:00",
    },
}

_CURRENT_CONFIG: dict[str, Any] | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_config(path: str | None = None) -> dict[str, Any]:
    global _CURRENT_CONFIG

    config = deepcopy(DEFAULT_CONFIG)
    if path:
        try:
            with Path(path).open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            if not isinstance(loaded, dict):
                loaded = {}
            config = _deep_merge(config, loaded)
        except FileNotFoundError:
            config = deepcopy(DEFAULT_CONFIG)

    _CURRENT_CONFIG = config
    return deepcopy(config)


def get_config() -> dict[str, Any]:
    global _CURRENT_CONFIG
    if _CURRENT_CONFIG is None:
        _CURRENT_CONFIG = deepcopy(DEFAULT_CONFIG)
    return deepcopy(_CURRENT_CONFIG)
