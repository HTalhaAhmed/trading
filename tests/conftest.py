"""Shared pytest fixtures for trading_bot tests."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone


def _make_bars(n: int, start_price: float, drift: float, seed: int, freq: str = "1min"):
    rng = np.random.default_rng(seed)
    closes = start_price + np.cumsum(rng.normal(drift, 2.0, n))
    opens  = closes - rng.normal(0, 1.0, n)
    highs  = np.maximum(opens, closes) + rng.uniform(0.3, 2.0, n)
    lows   = np.minimum(opens, closes) - rng.uniform(0.3, 2.0, n)
    vols   = rng.uniform(100, 500, n)
    idx = pd.date_range(
        end=datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc),
        periods=n,
        freq=freq,
        tz="UTC",
    )
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=idx,
    )


@pytest.fixture
def bull_m1():
    return _make_bars(300, 2300.0, 0.5, seed=1)


@pytest.fixture
def bull_m5():
    return _make_bars(200, 2300.0, 0.5, seed=2, freq="5min")


@pytest.fixture
def bull_m15():
    return _make_bars(100, 2300.0, 0.5, seed=3, freq="15min")


@pytest.fixture
def bear_m1():
    return _make_bars(300, 2300.0, -0.5, seed=4)


@pytest.fixture
def bear_m5():
    return _make_bars(200, 2300.0, -0.5, seed=5, freq="5min")


@pytest.fixture
def bear_m15():
    return _make_bars(100, 2300.0, -0.5, seed=6, freq="15min")


@pytest.fixture
def flat_m1():
    return _make_bars(300, 2300.0, 0.0, seed=7)


@pytest.fixture
def flat_m5():
    return _make_bars(200, 2300.0, 0.0, seed=8, freq="5min")


@pytest.fixture
def flat_m15():
    return _make_bars(100, 2300.0, 0.0, seed=9, freq="15min")
