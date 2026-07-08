from __future__ import annotations

from enum import Enum


class RegimeType(str, Enum):
    TRENDING = 'TRENDING'
    RANGING = 'RANGING'
    VOLATILE = 'VOLATILE'
    UNKNOWN = 'UNKNOWN'


class DirectionBias(str, Enum):
    BULLISH = 'BULLISH'
    BEARISH = 'BEARISH'
    NEUTRAL = 'NEUTRAL'


def determine_direction_bias(features: dict[str, float]) -> DirectionBias:
    ema_9 = features.get('ema_9', 0.0)
    ema_21 = features.get('ema_21', 0.0)
    ema_50 = features.get('ema_50', 0.0)
    ema_200 = features.get('ema_200', 0.0)
    rsi = features.get('rsi', 50.0)
    bullish = ema_9 > ema_21 > ema_50 > ema_200 and rsi >= 55.0
    bearish = ema_9 < ema_21 < ema_50 < ema_200 and rsi <= 45.0
    if bullish:
        return DirectionBias.BULLISH
    if bearish:
        return DirectionBias.BEARISH
    return DirectionBias.NEUTRAL


def detect_regime(features: dict[str, float]) -> RegimeType:
    adx = features.get('adx', 0.0)
    atr = features.get('atr', 0.0)
    atr_mean = features.get('atr_mean_20', atr)
    bias = determine_direction_bias(features)
    if atr <= 0:
        return RegimeType.UNKNOWN
    if atr_mean > 0 and atr >= atr_mean * 1.5:
        return RegimeType.VOLATILE
    if adx > 25 and bias is not DirectionBias.NEUTRAL:
        return RegimeType.TRENDING
    return RegimeType.RANGING
