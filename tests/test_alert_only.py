import pytest

from trading_bot.caps import CapsManager
from trading_bot.config import load_config
from trading_bot.logger import ScanLogger
from trading_bot.mt5_client import MT5Client
from trading_bot.scanner import MT5Scanner


def test_place_order_raises():
    """MT5Client.place_order must always raise RuntimeError."""
    client = MT5Client(mock=True)
    with pytest.raises(RuntimeError):
        client.place_order()


def test_trade_enabled_false_by_default():
    """Default config must have trade_enabled=False."""
    config = load_config()
    assert config["broker"]["trade_enabled"] is False


def test_alert_only_true_by_default():
    """Default config must have alert_only=True."""
    config = load_config()
    assert config["broker"]["alert_only"] is True


def test_scan_does_not_call_place_order(sample_bars, tmp_path, default_config):
    """Full scan cycle must not call place_order even if A+ setups found."""
    from unittest.mock import patch

    client = MT5Client(mock=True, mock_data={"XAUUSD": sample_bars})
    caps = CapsManager(default_config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(default_config, client, caps, logger)

    with patch.object(client, "place_order", side_effect=RuntimeError("Should not be called")) as mock_order:
        scanner.scan_all()
        mock_order.assert_not_called()


def test_scan_returns_cycle_result(sample_bars, tmp_path, default_config):
    """scan_all must return a ScanCycleResult."""
    from trading_bot.scanner import ScanCycleResult

    client = MT5Client(mock=True, mock_data={"XAUUSD": sample_bars})
    caps = CapsManager(default_config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(default_config, client, caps, logger)
    result = scanner.scan_all()
    assert isinstance(result, ScanCycleResult)
    assert result.cycle_id is not None
    assert result.timestamp is not None
