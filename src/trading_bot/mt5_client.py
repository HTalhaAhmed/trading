from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd


_TIMEFRAME_MAP = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}


class MT5Client:
    def __init__(self, mock: bool = False, mock_data: dict[str, Any] | None = None):
        self.mock = mock
        self.mock_data = mock_data or {}
        self._connected = False
        self._mt5 = None
        self._cache: dict[str, pd.DataFrame] = {}

        if not self.mock:
            try:
                import MetaTrader5 as mt5  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "MetaTrader5 is not installed. Install it on a supported MT5 host or run with mock=True."
                ) from exc
            self._mt5 = mt5

    def connect(self) -> bool:
        if self.mock:
            self._connected = True
            return True
        self._connected = bool(self._mt5.initialize())
        return self._connected

    def disconnect(self):
        if self.mock:
            self._connected = False
            return
        if self._mt5 is not None:
            self._mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_symbols(self) -> list[str]:
        if self.mock:
            return list(self.mock_data.keys()) or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "XAGUSD"]
        symbols = self._mt5.symbols_get() or []
        return [item.name for item in symbols]

    def select_symbol(self, symbol: str) -> bool:
        if self.mock:
            return symbol in self.get_symbols()
        return bool(self._mt5.symbol_select(symbol, True))

    def _base_price_for_symbol(self, symbol: str) -> float:
        if symbol == "XAUUSD":
            return 2350.0
        if symbol == "XAGUSD":
            return 30.0
        if symbol.endswith("JPY"):
            return 155.0
        return 1.1000

    def _digits_for_symbol(self, symbol: str) -> int:
        if symbol in {"XAUUSD", "XAGUSD"}:
            return 2
        if symbol.endswith("JPY"):
            return 3
        return 5

    def _point_for_digits(self, digits: int) -> float:
        return 10 ** (-digits)

    def _generate_mock_bars(self, symbol: str, count: int = 500) -> pd.DataFrame:
        if symbol in self._cache and len(self._cache[symbol]) >= count:
            return self._cache[symbol].tail(count).copy()

        seed = 1000 + sum(ord(char) for char in symbol)
        rng = np.random.default_rng(seed)
        n = max(500, count)
        base_price = self._base_price_for_symbol(symbol)
        digits = self._digits_for_symbol(symbol)
        point = self._point_for_digits(digits)
        drift = 0.02 if digits <= 2 else point * 2.0
        noise = 0.12 if digits <= 2 else point * 12.0

        times = [datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc) + timedelta(minutes=i) for i in range(n)]
        closes = base_price + np.cumsum(rng.normal(drift, noise, n))
        opens = np.roll(closes, 1)
        opens[0] = base_price
        highs = np.maximum(opens, closes) + np.abs(rng.normal(noise / 2, noise / 3, n))
        lows = np.minimum(opens, closes) - np.abs(rng.normal(noise / 2, noise / 3, n))
        volumes = rng.integers(100, 1000, n).astype(float)

        df = pd.DataFrame(
            {
                "time": pd.to_datetime(times, utc=True),
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )
        self._cache[symbol] = df
        return df.tail(count).copy()

    def _resample(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        if timeframe == "M1":
            return df.copy()
        freq = _TIMEFRAME_MAP.get(timeframe)
        if freq is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        indexed = df.copy()
        indexed["time"] = pd.to_datetime(indexed["time"], utc=True)
        indexed = indexed.set_index("time").sort_index()
        resampled = (
            indexed.resample(freq)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
            .reset_index()
        )
        return resampled

    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        try:
            if self.mock:
                source = self.mock_data.get(symbol)
                if source is None or len(source) == 0:
                    source = self._generate_mock_bars(symbol, max(count, 500))
                df = pd.DataFrame(source).copy()
                df["time"] = pd.to_datetime(df["time"], utc=True)
                df = df.sort_values("time")
                result = self._resample(df, timeframe)
                return result.tail(count).reset_index(drop=True)

            timeframe_enum = {
                "M1": self._mt5.TIMEFRAME_M1,
                "M5": self._mt5.TIMEFRAME_M5,
                "M15": self._mt5.TIMEFRAME_M15,
                "H1": self._mt5.TIMEFRAME_H1,
                "H4": self._mt5.TIMEFRAME_H4,
                "D1": self._mt5.TIMEFRAME_D1,
            }.get(timeframe)
            if timeframe_enum is None:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
            rates = self._mt5.copy_rates_from_pos(symbol, timeframe_enum, 0, count)
            if rates is None or len(rates) == 0:
                return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            volume_col = "tick_volume" if "tick_volume" in df.columns else "real_volume"
            df = df.rename(columns={volume_col: "volume"})
            return df[["time", "open", "high", "low", "close", "volume"]].copy()
        except Exception:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    def get_symbol_info(self, symbol: str) -> dict[str, float | int]:
        if self.mock:
            digits = self._digits_for_symbol(symbol)
            point = self._point_for_digits(digits)
            spread_points = 10
            spread = spread_points * point
            df = self.mock_data.get(symbol)
            if df is None or len(df) == 0:
                df = self._generate_mock_bars(symbol, 1)
            price = float(pd.DataFrame(df)["close"].iloc[-1])
            bid = round(price - (spread / 2), digits)
            ask = round(price + (spread / 2), digits)
            return {"spread": round(ask - bid, digits), "point": point, "digits": digits, "ask": ask, "bid": bid}

        info = self._mt5.symbol_info(symbol)
        tick = self._mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return {"spread": 0.0, "point": 0.0, "digits": 5, "ask": 0.0, "bid": 0.0}
        spread = float(info.spread) * float(info.point)
        return {
            "spread": spread,
            "point": float(info.point),
            "digits": int(info.digits),
            "ask": float(tick.ask),
            "bid": float(tick.bid),
        }

    def get_open_positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if self.mock:
            return []

        positions = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        if not positions:
            return []
        result = []
        for position in positions:
            result.append(
                {
                    "symbol": position.symbol,
                    "type": position.type,
                    "volume": position.volume,
                    "price_open": position.price_open,
                    "sl": position.sl,
                    "tp": position.tp,
                    "profit": position.profit,
                }
            )
        return result

    def place_order(self, *args, **kwargs):
        raise RuntimeError("place_order is disabled in alert-only mode")
