import pandas as pd

from trading_bot.indicators import ema, rsi


def test_ema_tracks_series_direction() -> None:
    s = pd.Series([1, 2, 3, 4, 5])
    out = ema(s, 3)
    assert out.iloc[-1] > out.iloc[0]


def test_rsi_bounds() -> None:
    s = pd.Series([100, 101, 102, 101, 100, 99, 100, 101])
    out = rsi(s, 5)
    assert ((out >= 0) & (out <= 100)).all()
