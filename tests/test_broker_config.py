"""Tests for broker configuration parsing and safety defaults."""
from __future__ import annotations

import yaml

from trading_bot.config_loader import load_settings


def _write_settings(tmp_path, cfg: dict) -> str:
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.dump(cfg))
    return str(path)


def _minimal_cfg(**extras) -> dict:
    base = {
        "project": {"symbol": "XAUUSD", "starting_equity": 10000, "timezone": "UTC"},
        "risk": {
            "risk_per_trade": 0.005,
            "daily_max_loss_pct": 0.03,
            "max_consecutive_losses": 3,
        },
        "strategy": {
            "trend": {
                "ema_fast": 20,
                "ema_slow": 50,
                "pullback_ema": 20,
                "stop_atr_mult": 1.5,
                "take_profit_r": 1.5,
            },
            "range": {
                "rsi_overbought": 70,
                "rsi_oversold": 30,
                "stop_atr_mult": 1.2,
                "take_profit_r": 1.2,
            },
        },
        "news": {
            "enabled": False,
            "blackout_pre_minutes": 15,
            "blackout_post_minutes": 15,
            "impacts": [],
        },
        "sessions": {"trade_hours_utc": [7, 16]},
        "execution": {"spread_points": 0.25, "slippage_points": 0.10},
    }
    base.update(extras)
    return base


class TestBrokerConfigParsing:
    def test_settings_load_without_broker_section(self, tmp_path) -> None:
        """Settings without a broker section load correctly."""
        path = _write_settings(tmp_path, _minimal_cfg())
        settings = load_settings(path)
        assert "project" in settings
        assert settings.get("broker", {}).get("trade_enabled", False) is False

    def test_settings_load_with_broker_section(self, tmp_path) -> None:
        """Broker section values are preserved after loading."""
        cfg = _minimal_cfg(
            broker={
                "mode": "paper",
                "mt5_symbol": "XAUUSD",
                "polling_interval_seconds": 60,
                "magic_number": 234000,
                "deviation": 10,
                "max_spread_points": 3.0,
                "trade_enabled": False,
            }
        )
        path = _write_settings(tmp_path, cfg)
        settings = load_settings(path)
        assert settings["broker"]["mode"] == "paper"
        assert settings["broker"]["mt5_symbol"] == "XAUUSD"
        assert settings["broker"]["magic_number"] == 234000
        assert settings["broker"]["trade_enabled"] is False

    def test_trade_enabled_absent_defaults_to_false(self, tmp_path) -> None:
        """trade_enabled must never default to True — core safety invariant."""
        cfg = _minimal_cfg(broker={"mode": "mt5"})  # no trade_enabled key
        path = _write_settings(tmp_path, cfg)
        settings = load_settings(path)
        assert settings["broker"].get("trade_enabled", False) is False

    def test_mode_backtest_is_valid(self, tmp_path) -> None:
        cfg = _minimal_cfg(broker={"mode": "backtest"})
        path = _write_settings(tmp_path, cfg)
        settings = load_settings(path)
        assert settings["broker"]["mode"] == "backtest"

    def test_mt5_credentials_placeholders(self, tmp_path) -> None:
        """MT5 sub-section credentials are stored as provided (placeholders)."""
        cfg = _minimal_cfg(
            broker={
                "mode": "mt5",
                "trade_enabled": False,
                "mt5": {"login": 0, "password": "", "server": ""},
            }
        )
        path = _write_settings(tmp_path, cfg)
        settings = load_settings(path)
        mt5_creds = settings["broker"]["mt5"]
        assert mt5_creds["login"] == 0
        assert mt5_creds["password"] == ""
