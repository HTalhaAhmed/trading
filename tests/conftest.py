from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_config() -> dict:
    return {
        'broker': {
            'mode': 'paper',
            'trade_enabled': False,
            'polling_interval_seconds': 5,
            'watchlist': ['XAUUSD', 'EURUSD', 'GBPUSD'],
        },
        'risk_limits': {
            'max_trades_per_symbol_per_day': 5,
            'max_trades_total_per_day': 8,
            'max_trades_per_session': 2,
            'min_minutes_between_trades': 20,
            'max_open_positions_per_symbol': 1,
            'max_open_positions_total': 2,
        },
        'scanner': {
            'only_a_plus': True,
            'top_n_setups': 3,
            'require_trending_market_first': True,
            'a_plus_min_score': 0.85,
            'a_min_score': 0.70,
            'b_min_score': 0.55,
            'c_min_score': 0.40,
        },
    }


@pytest.fixture
def sample_bars() -> pd.DataFrame:
    periods = 250
    start = datetime(2026, 7, 1, 8, 0, 0)
    index = pd.date_range(start=start, periods=periods, freq='min', tz='UTC')
    base = np.linspace(1900, 1940, periods)
    oscillation = np.sin(np.linspace(0, 12, periods)) * 0.6
    close = base + oscillation
    open_ = close - 0.12
    high = close + 0.25
    low = close - 0.25
    bid = close - 0.03
    ask = close + 0.03
    volume = np.linspace(100, 500, periods)
    return pd.DataFrame(
        {
            'time': index,
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'bid': bid,
            'ask': ask,
            'volume': volume,
        }
    )
