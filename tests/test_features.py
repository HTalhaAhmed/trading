from __future__ import annotations

import pandas as pd

from trading_bot.features import compute_features


def test_compute_features_returns_expected_keys(sample_bars):
    features = compute_features(sample_bars)
    expected = {
        'ema_9', 'ema_21', 'ema_50', 'ema_200', 'adx', 'plus_di', 'minus_di',
        'atr', 'rsi', 'macd', 'macd_signal', 'macd_hist', 'bb_upper', 'bb_middle',
        'bb_lower', 'bb_width', 'spread'
    }
    assert expected.issubset(features.keys())


def test_ema_values_match_pandas(sample_bars):
    features = compute_features(sample_bars)
    expected_ema9 = sample_bars['close'].ewm(span=9, adjust=False).mean().iloc[-1]
    assert round(features['ema_9'], 8) == round(float(expected_ema9), 8)


def test_features_pipeline_works_on_200_bar_dataframe(sample_bars):
    features = compute_features(sample_bars.iloc[:200])
    assert isinstance(features, dict)
    assert len(features) >= 20


def test_features_are_nan_free_for_sufficient_data(sample_bars):
    features = compute_features(sample_bars)
    assert not any(pd.isna(value) for value in features.values())
