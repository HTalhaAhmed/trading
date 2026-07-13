import os

from trading_bot.caps import CapsManager
from trading_bot.config import load_config
from trading_bot.logger import ScanLogger
from trading_bot.mt5_client import MT5Client
from trading_bot.scanner import MT5Scanner, ScanCycleResult


def test_scan_returns_cycle_result(sample_bars, tmp_path):
    config = load_config()
    config["broker"]["watchlist"] = ["XAUUSD"]
    client = MT5Client(mock=True, mock_data={"XAUUSD": sample_bars})
    caps = CapsManager(config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(config, client, caps, logger)

    result = scanner.scan_all()
    assert isinstance(result, ScanCycleResult)
    assert result.cycle_id
    assert isinstance(result.surfaced, list)
    assert isinstance(result.suppressed, list)


def test_scan_respects_top_n(sample_bars, tmp_path):
    config = load_config()
    config["broker"]["watchlist"] = ["XAUUSD", "EURUSD", "GBPUSD"]
    config["scanner"]["top_n_setups"] = 2
    config["scanner"]["only_a_plus"] = False

    client = MT5Client(
        mock=True,
        mock_data={
            "XAUUSD": sample_bars,
            "EURUSD": sample_bars,
            "GBPUSD": sample_bars,
        },
    )
    caps = CapsManager(config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(config, client, caps, logger)

    result = scanner.scan_all()
    assert len(result.surfaced) <= 2


def test_scan_logs_results(sample_bars, tmp_path):
    config = load_config()
    config["broker"]["watchlist"] = ["XAUUSD"]
    client = MT5Client(mock=True, mock_data={"XAUUSD": sample_bars})
    caps = CapsManager(config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(config, client, caps, logger)

    scanner.scan_all()
    logger.flush()

    log_path = os.path.join(str(tmp_path), "scan_history.jsonl")
    assert os.path.exists(log_path)
    with open(log_path) as handle:
        lines = handle.readlines()
    assert len(lines) >= 1


def test_scan_handles_connection_error(tmp_path):
    config = load_config()
    config["broker"]["watchlist"] = ["XAUUSD"]

    client = MT5Client(mock=True, mock_data={})
    caps = CapsManager(config)
    logger = ScanLogger(str(tmp_path))
    scanner = MT5Scanner(config, client, caps, logger)

    result = scanner.scan_all()
    assert isinstance(result, ScanCycleResult)
