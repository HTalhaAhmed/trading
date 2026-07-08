from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {'open', 'high', 'low', 'close'}


def _normalize_bars(bars: pd.DataFrame) -> pd.DataFrame:
    normalized = bars.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    missing = REQUIRED_COLUMNS.difference(normalized.columns)
    if missing:
        raise ValueError(f'Missing required OHLC columns: {sorted(missing)}')
    if 'volume' not in normalized.columns:
        if 'tick_volume' in normalized.columns:
            normalized['volume'] = normalized['tick_volume']
        else:
            normalized['volume'] = 0.0
    return normalized


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    tr_components = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )
    atr = _atr(high, low, close, period)
    atr = atr.replace(0, np.nan)
    plus_di = 100.0 * plus_dm.rolling(period, min_periods=period).mean() / atr
    minus_di = 100.0 * minus_dm.rolling(period, min_periods=period).mean() / atr
    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denominator
    adx = dx.rolling(period, min_periods=period).mean()
    return adx, plus_di, minus_di


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.rolling(period, min_periods=period).mean()
    average_loss = losses.rolling(period, min_periods=period).mean()
    rs = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(100.0)


def compute_features(bars: pd.DataFrame) -> dict[str, float]:
    frame = _normalize_bars(bars)
    close = frame['close'].astype(float)
    high = frame['high'].astype(float)
    low = frame['low'].astype(float)
    open_ = frame['open'].astype(float)
    volume = frame['volume'].astype(float)

    ema_9 = _ema(close, 9)
    ema_21 = _ema(close, 21)
    ema_50 = _ema(close, 50)
    ema_200 = _ema(close, 200)
    atr_14 = _atr(high, low, close, 14)
    adx_14, plus_di, minus_di = _adx(high, low, close, 14)
    rsi_14 = _rsi(close, 14)

    macd_line = _ema(close, 12) - _ema(close, 26)
    macd_signal = _ema(macd_line, 9)
    macd_hist = macd_line - macd_signal

    bb_middle = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std(ddof=0)
    bb_upper = bb_middle + (2.0 * bb_std)
    bb_lower = bb_middle - (2.0 * bb_std)
    bb_width = (bb_upper - bb_lower) / close.replace(0, np.nan)

    spread = None
    if {'ask', 'bid'}.issubset(frame.columns):
        spread = frame['ask'].astype(float) - frame['bid'].astype(float)
    else:
        spread = high - low

    candle_range = (high - low).replace(0, np.nan)
    body_pct = (close - open_).abs() / candle_range
    close_location = (close - low) / candle_range
    atr_mean_20 = atr_14.rolling(20, min_periods=1).mean()

    feature_frame = pd.DataFrame(
        {
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'ema_9': ema_9,
            'ema_21': ema_21,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'adx': adx_14,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'atr': atr_14,
            'atr_mean_20': atr_mean_20,
            'rsi': rsi_14,
            'macd': macd_line,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'bb_upper': bb_upper,
            'bb_middle': bb_middle,
            'bb_lower': bb_lower,
            'bb_width': bb_width,
            'spread': spread,
            'bar_range': high - low,
            'body_pct': body_pct,
            'close_location': close_location,
        }
    )
    latest = feature_frame.ffill().iloc[-1].fillna(0.0)
    return {key: float(value) for key, value in latest.to_dict().items()}
