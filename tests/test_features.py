import pandas as pd

from trading_bot.features import session_vwap


def test_session_vwap_resets_by_day() -> None:
    idx = pd.to_datetime(
        ["2025-01-01 00:00:00+00:00", "2025-01-01 00:01:00+00:00", "2025-01-02 00:00:00+00:00"],
        utc=True,
    )
    df = pd.DataFrame(
        {
            "high": [10, 12, 20],
            "low": [8, 10, 18],
            "close": [9, 11, 19],
            "volume": [100, 100, 100],
        },
        index=idx,
    )
    out = session_vwap(df)
    assert out.iloc[2] == 19.0
