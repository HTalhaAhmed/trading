from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from .alerts import format_scan_board as format_alert_board
from .features import compute_features
from .regime import detect_regime
from .scanner import Grade, TradeScanner
from .trade_controls import ControlCheckResult, TradeControlManager, normalize_datetime, utc_now

try:
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:  # pragma: no cover - expected in test environment
    MT5_AVAILABLE = False
    mt5 = None


@dataclass(slots=True)
class SymbolScanResult:
    symbol: str
    direction: str
    grade: str
    score: float
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    is_tradable: bool = False
    control_result: Optional[ControlCheckResult] = None
    regime: str = 'UNKNOWN'
    timestamp: datetime = field(default_factory=utc_now)


class MT5MultiSymbolScanner:
    def __init__(self, config: dict, trade_controls: TradeControlManager = None):
        self.config = config
        self.trade_controls = trade_controls or TradeControlManager(config)
        self.scanner = TradeScanner(config)
        self._connected = False

    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            return False
        self._connected = bool(mt5.initialize())
        return self._connected

    def disconnect(self) -> None:
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False

    def ensure_symbol_selected(self, symbol: str) -> bool:
        if not MT5_AVAILABLE:
            return False
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        if getattr(info, 'visible', False):
            return True
        return bool(mt5.symbol_select(symbol, True))

    def fetch_bars(self, symbol: str, n_bars: int = 200) -> Optional[pd.DataFrame]:
        if not MT5_AVAILABLE:
            return None
        if not self._connected and not self.connect():
            return None
        if not self.ensure_symbol_selected(symbol):
            return None
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, n_bars)
        if rates is None or len(rates) == 0:
            return None
        frame = pd.DataFrame(rates)
        if 'time' in frame.columns:
            frame['time'] = pd.to_datetime(frame['time'], unit='s', utc=True)
        return frame

    def scan_symbol(self, symbol: str, bars: pd.DataFrame = None) -> SymbolScanResult:
        frame = bars if bars is not None else self.fetch_bars(symbol)
        if frame is None or frame.empty:
            return SymbolScanResult(
                symbol=symbol,
                direction='NO TRADE',
                grade=Grade.REJECTED.value,
                score=0.0,
                blockers=['market data unavailable'],
                is_tradable=False,
                control_result=ControlCheckResult(False, 'NO TRADE — market data unavailable', symbol=symbol),
                regime='UNKNOWN',
                timestamp=utc_now(),
            )
        features = compute_features(frame)
        scan_result = self.scanner.scan(symbol, features)
        regime = detect_regime(features).value
        timestamp = utc_now()
        if 'time' in frame.columns:
            raw_time = frame.iloc[-1]['time']
            if hasattr(raw_time, 'to_pydatetime'):
                timestamp = normalize_datetime(raw_time.to_pydatetime())
            elif isinstance(raw_time, datetime):
                timestamp = normalize_datetime(raw_time)
        control_result = self.trade_controls.check(symbol) if self.trade_controls else None
        is_tradable = self.scanner.is_tradable(scan_result) and (control_result.allowed if control_result else True)
        return SymbolScanResult(
            symbol=symbol,
            direction=scan_result.direction,
            grade=scan_result.grade.value,
            score=scan_result.score,
            reasons=scan_result.reasons,
            cautions=scan_result.cautions,
            blockers=scan_result.blockers,
            is_tradable=is_tradable,
            control_result=control_result,
            regime=regime,
            timestamp=timestamp,
        )

    def scan_watchlist(self) -> list[SymbolScanResult]:
        watchlist = self.config.get('broker', {}).get('watchlist', [])
        results = [self.scan_symbol(symbol) for symbol in watchlist]
        return sorted(results, key=lambda result: result.score, reverse=True)

    def get_ranked_opportunities(self, results: list[SymbolScanResult]) -> list[SymbolScanResult]:
        top_n = int(self.config.get('scanner', {}).get('top_n_setups', len(results) or 0))
        tradable = [result for result in results if result.is_tradable]
        return sorted(tradable, key=lambda result: result.score, reverse=True)[:top_n]

    def format_scan_board(self, results: list[SymbolScanResult]) -> str:
        return format_alert_board(results)
