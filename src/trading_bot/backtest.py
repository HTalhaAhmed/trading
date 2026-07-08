from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .features import compute_features
from .scanner import ScanResult, TradeScanner
from .trade_controls import TradeControlManager


@dataclass(slots=True)
class BacktestReport:
    symbol: str
    total_bars: int
    signals: int
    executed_trades: int
    blocked_trades: int
    results: list[ScanResult] = field(default_factory=list)


class BacktestRunner:
    def __init__(self, config: dict):
        self.config = config
        self.trade_controls = TradeControlManager(config)
        self.scanner = TradeScanner(config)

    def run(self, csv_path: str | Path, symbol: str = 'BACKTEST') -> BacktestReport:
        frame = pd.read_csv(csv_path)
        frame.columns = [str(column).lower() for column in frame.columns]
        if 'time' in frame.columns:
            frame['time'] = pd.to_datetime(frame['time'], utc=True, errors='coerce')
        signals = 0
        executed = 0
        blocked = 0
        scan_results: list[ScanResult] = []

        for index in range(200, len(frame) + 1):
            window = frame.iloc[:index]
            features = compute_features(window)
            current_time = window.iloc[-1]['time'].to_pydatetime() if 'time' in window.columns and pd.notna(window.iloc[-1]['time']) else None
            result = self.scanner.scan(symbol=symbol, features=features)
            if self.scanner.is_tradable(result):
                signals += 1
                guard = self.trade_controls.check(symbol, now=current_time)
                if guard.allowed:
                    self.trade_controls.record_trade(symbol, now=current_time)
                    executed += 1
                else:
                    blocked += 1
            scan_results.append(result)

        return BacktestReport(
            symbol=symbol,
            total_bars=len(frame),
            signals=signals,
            executed_trades=executed,
            blocked_trades=blocked,
            results=scan_results,
        )
