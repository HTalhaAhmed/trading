from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .trade_controls import resolve_session, utc_now


@dataclass(slots=True)
class ReviewResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def _clamp(score: float) -> float:
    return max(0.0, min(1.0, score))


class TrendReviewer:
    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        score = 0.15
        ema_9 = features.get('ema_9', 0.0)
        ema_21 = features.get('ema_21', 0.0)
        ema_50 = features.get('ema_50', 0.0)
        ema_200 = features.get('ema_200', 0.0)
        adx = features.get('adx', 0.0)
        close = features.get('close', 0.0)

        bullish = ema_9 > ema_21 > ema_50 > ema_200
        bearish = ema_9 < ema_21 < ema_50 < ema_200
        aligned = (direction == 'LONG' and bullish) or (direction == 'SHORT' and bearish)
        if direction == 'NO TRADE':
            blockers.append('trend direction unclear')
        elif aligned:
            score += 0.45
            reasons.append('EMA stack aligned with trade direction')
        else:
            blockers.append('EMA trend alignment missing')

        if adx > 25:
            score += 0.25
            reasons.append('ADX confirms trending conditions')
        elif adx >= 20:
            score += 0.10
            cautions.append('ADX is below ideal trend threshold')
        else:
            cautions.append('weak trend strength')

        if direction == 'LONG' and close >= ema_21:
            score += 0.10
            reasons.append('price holding above EMA21')
        elif direction == 'SHORT' and close <= ema_21:
            score += 0.10
            reasons.append('price holding below EMA21')
        else:
            cautions.append('price is extended away from EMA21 support/resistance')

        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)


class MomentumReviewer:
    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        score = 0.20
        rsi = features.get('rsi', 50.0)
        macd = features.get('macd', 0.0)
        signal = features.get('macd_signal', 0.0)
        hist = features.get('macd_hist', 0.0)

        if direction == 'LONG':
            if 55 <= rsi <= 72:
                score += 0.30
                reasons.append('RSI supports bullish momentum')
            elif rsi > 75:
                cautions.append('RSI is overbought')
            else:
                cautions.append('RSI is not yet in bullish control')
            if macd >= signal and hist >= 0:
                score += 0.30
                reasons.append('MACD is aligned bullish')
            else:
                cautions.append('MACD momentum is soft')
        elif direction == 'SHORT':
            if 28 <= rsi <= 45:
                score += 0.30
                reasons.append('RSI supports bearish momentum')
            elif rsi < 25:
                cautions.append('RSI is oversold')
            else:
                cautions.append('RSI is not yet in bearish control')
            if macd <= signal and hist <= 0:
                score += 0.30
                reasons.append('MACD is aligned bearish')
            else:
                cautions.append('MACD momentum is soft')
        else:
            blockers.append('momentum direction unresolved')

        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)


class VolatilityReviewer:
    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        score = 0.25
        atr = features.get('atr', 0.0)
        close = max(features.get('close', 1.0), 1e-9)
        bb_width = features.get('bb_width', 0.0)
        spread = max(features.get('spread', 0.0), 0.0)
        spread_ratio = spread / max(atr, 1e-9)
        atr_ratio = atr / close

        if 0.001 <= atr_ratio <= 0.03:
            score += 0.25
            reasons.append('ATR is in a tradable range')
        elif atr_ratio > 0.05:
            cautions.append('ATR is elevated')
        else:
            cautions.append('ATR is compressed')

        if bb_width >= 0.01:
            score += 0.20
            reasons.append('Bollinger band width supports movement')
        else:
            cautions.append('Bollinger bands are tight')

        if spread_ratio <= 0.20:
            score += 0.20
            reasons.append('spread is efficient relative to ATR')
        elif spread_ratio <= 0.35:
            cautions.append('spread cost is acceptable but not ideal')
        else:
            blockers.append('spread is too large relative to ATR')

        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)


class ExecutionReviewer:
    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        score = 0.20
        body_pct = features.get('body_pct', 0.0)
        close_location = features.get('close_location', 0.5)
        spread = features.get('spread', 0.0)
        candle_range = max(features.get('bar_range', 0.0), 1e-9)

        if body_pct >= 0.55:
            score += 0.25
            reasons.append('entry candle has decisive body')
        elif body_pct >= 0.35:
            score += 0.15
            reasons.append('entry candle body is acceptable')
        else:
            cautions.append('entry candle is indecisive')

        if direction == 'LONG' and close_location >= 0.65:
            score += 0.25
            reasons.append('close is near candle high')
        elif direction == 'SHORT' and close_location <= 0.35:
            score += 0.25
            reasons.append('close is near candle low')
        elif direction == 'NO TRADE':
            blockers.append('execution direction unresolved')
        else:
            cautions.append('entry close location is only average')

        if spread / candle_range <= 0.30:
            score += 0.20
            reasons.append('spread cost is reasonable for entry')
        else:
            cautions.append('spread consumes much of the candle range')

        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)


class RiskReviewer:
    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        score = 0.20
        close = features.get('close', 0.0)
        atr = max(features.get('atr', 0.0), 1e-9)
        spread = max(features.get('spread', 0.0), 0.0)
        ema_21 = features.get('ema_21', close)
        bb_upper = features.get('bb_upper', close)
        bb_lower = features.get('bb_lower', close)

        if direction == 'LONG':
            reward = max(bb_upper - close, atr)
            risk = max(close - ema_21, spread, atr * 0.5)
        elif direction == 'SHORT':
            reward = max(close - bb_lower, atr)
            risk = max(ema_21 - close, spread, atr * 0.5)
        else:
            blockers.append('risk cannot be assessed without direction')
            return ReviewResult(score=0.0, reasons=reasons, cautions=cautions, blockers=blockers)

        rr = reward / max(risk, 1e-9)
        if rr >= 2.0:
            score += 0.50
            reasons.append('estimated reward to risk is strong')
        elif rr >= 1.2:
            score += 0.25
            reasons.append('estimated reward to risk is acceptable')
        elif rr >= 1.0:
            cautions.append('reward to risk is marginal')
        else:
            blockers.append('reward to risk is below 1:1')
        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)


class SessionReviewer:
    def __init__(self, now_provider=None):
        self.now_provider = now_provider or utc_now

    def review(self, features: dict[str, float], direction: str) -> ReviewResult:
        reasons: list[str] = []
        cautions: list[str] = []
        blockers: list[str] = []
        now = self.now_provider()
        session = resolve_session(now)
        score = 0.30
        if now.weekday() >= 5:
            blockers.append('weekend trading session')
        elif session in {'london', 'ny'}:
            score += 0.55
            reasons.append(f'{session} session liquidity is favorable')
        elif session in {'tokyo', 'sydney'}:
            score += 0.35
            reasons.append(f'{session} session is active')
            cautions.append('session liquidity may be thinner than London/NY')
        else:
            cautions.append('off-session trading conditions')
        return ReviewResult(score=_clamp(score), reasons=reasons, cautions=cautions, blockers=blockers)
