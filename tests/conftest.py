import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta, timezone


@pytest.fixture
def sample_bars():
    """Generate deterministic sample OHLCV bars (500 bars of M1 data, trending up)."""
    np.random.seed(42)
    n = 500
    base_price = 2000.0
    times = [datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]
    closes = base_price + np.cumsum(np.random.normal(0.02, 0.5, n))
    opens = np.roll(closes, 1)
    opens[0] = base_price
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 0.3, n))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 0.3, n))
    volumes = np.random.randint(100, 1000, n).astype(float)

    return pd.DataFrame(
        {
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


@pytest.fixture
def trending_down_bars():
    """Generate deterministic sample OHLCV bars trending down."""
    np.random.seed(99)
    n = 500
    base_price = 2100.0
    times = [datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]
    closes = base_price + np.cumsum(np.random.normal(-0.03, 0.5, n))
    opens = np.roll(closes, 1)
    opens[0] = base_price
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 0.3, n))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 0.3, n))
    volumes = np.random.randint(100, 1000, n).astype(float)

    return pd.DataFrame(
        {
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


@pytest.fixture
def default_config():
    """Return default configuration."""
    from trading_bot.config import load_config

    return load_config()


@pytest.fixture
def mock_mt5_client(sample_bars):
    """Return a mock MT5 client with sample data."""
    from trading_bot.mt5_client import MT5Client

    return MT5Client(mock=True, mock_data={"XAUUSD": sample_bars, "EURUSD": sample_bars})
