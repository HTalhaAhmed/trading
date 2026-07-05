"""
Paper trading broker — simulates order execution against a replay of
historical 1m OHLCV data.

This broker is useful for:
* Forward-walk paper testing without a MetaTrader5 installation.
* Automated testing of the live-runner loop logic.

⚠️  Paper results do **not** account for real-world latency, partial
    fills, or dynamic spread variation.  Always validate strategies on a
    true demo account before considering live use.

Usage example
-------------
::

    from trading_bot.broker.paper_broker import PaperBroker
    from trading_bot.data_loader import load_ohlcv_csv

    df = load_ohlcv_csv("data/sample_xauusd_1m.csv")
    broker = PaperBroker(df, default_spread=0.25)
    broker.initialize()

    while broker.advance_bar():
        tick = broker.get_tick("XAUUSD")
        bars = broker.get_bars("XAUUSD", "1min", 200)
        # ... run strategy logic ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .base import BrokerBase, OrderResult, Tick

logger = logging.getLogger(__name__)

_RESAMPLE_RULES: dict[str, str] = {
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
}


@dataclass
class _PaperPosition:
    ticket: int
    symbol: str
    side: str
    volume: float
    price_open: float
    sl: float
    tp: float
    magic: int


class PaperBroker(BrokerBase):
    """
    Broker that replays a 1-minute DataFrame for paper trading.

    Bars are consumed one at a time via :meth:`advance_bar`.  All data
    methods (``get_bars``, ``get_tick``) operate relative to the current
    bar index so the live runner sees only "past" data at each step.

    Parameters
    ----------
    df_1m : pd.DataFrame
        1-minute OHLCV DataFrame with a UTC-aware DatetimeIndex.
    default_spread : float
        Fallback spread in price points used when no ``spread`` column
        exists in *df_1m*.
    """

    def __init__(self, df_1m: pd.DataFrame, default_spread: float = 0.25) -> None:
        self._df = df_1m.copy()
        self._default_half_spread: float = default_spread / 2.0
        self._current_idx: int = -1
        self._positions: dict[int, _PaperPosition] = {}
        self._ticket_counter: int = 1
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        if self._df.empty:
            logger.error("PaperBroker: DataFrame is empty — cannot initialize.")
            return False
        self._current_idx = -1
        self._initialized = True
        logger.info("PaperBroker initialized with %d bars.", len(self._df))
        return True

    def shutdown(self) -> None:
        self._initialized = False
        logger.info("PaperBroker shutdown.")

    # ------------------------------------------------------------------
    # Replay control
    # ------------------------------------------------------------------

    def advance_bar(self) -> bool:
        """
        Advance the internal cursor by one bar.

        Returns ``False`` when all bars have been consumed, signalling
        that the replay loop should stop.
        """
        self._current_idx += 1
        return self._current_idx < len(self._df)

    @property
    def current_timestamp(self) -> pd.Timestamp | None:
        """Timestamp of the current (most recent) bar, or ``None``."""
        if 0 <= self._current_idx < len(self._df):
            return self._df.index[self._current_idx]
        return None

    @property
    def bars_remaining(self) -> int:
        """Number of bars not yet consumed."""
        return max(0, len(self._df) - self._current_idx - 1)

    # ------------------------------------------------------------------
    # Symbol / market data
    # ------------------------------------------------------------------

    def is_symbol_available(self, symbol: str) -> bool:
        return True  # paper broker accepts any symbol name

    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """
        Return up to *count* bars up to and including the current bar.

        Supports resampling to "5min" and "15min" in addition to "1min".
        """
        end = self._current_idx + 1
        start = max(0, end - count)
        slice_ = self._df.iloc[start:end]

        if timeframe == "1min":
            return slice_

        if timeframe not in _RESAMPLE_RULES:
            raise ValueError(
                f"Unsupported timeframe {timeframe!r}. "
                f"Supported: {list(_RESAMPLE_RULES)}"
            )

        rule = _RESAMPLE_RULES[timeframe]
        agg: dict[str, str] = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        if "spread" in slice_.columns:
            agg["spread"] = "mean"
        result = slice_.resample(rule).agg(agg).dropna(subset=["close"])
        return result.tail(count)

    def get_tick(self, symbol: str) -> Tick:
        """Return a simulated tick for the current bar."""
        if not (0 <= self._current_idx < len(self._df)):
            raise RuntimeError(
                "PaperBroker: No current bar — "
                "call initialize() then advance_bar() first."
            )
        row = self._df.iloc[self._current_idx]
        mid = float(row["close"])
        spread = float(row.get("spread", self._default_half_spread * 2))
        half = spread / 2.0
        return Tick(
            symbol=symbol,
            bid=round(mid - half, 5),
            ask=round(mid + half, 5),
        )

    # ------------------------------------------------------------------
    # Order execution (simulated)
    # ------------------------------------------------------------------

    def send_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float,
        tp: float,
        magic: int = 0,
        comment: str = "",
    ) -> OrderResult:
        """Simulate an instant market fill at the current bar's bid/ask."""
        tick = self.get_tick(symbol)
        fill_price = tick.ask if side == "long" else tick.bid
        ticket = self._ticket_counter
        self._ticket_counter += 1
        self._positions[ticket] = _PaperPosition(
            ticket=ticket,
            symbol=symbol,
            side=side,
            volume=volume,
            price_open=fill_price,
            sl=sl,
            tp=tp,
            magic=magic,
        )
        logger.info(
            "PAPER FILL  ticket=%d  %s %s  %.2f lots @ %.5f  sl=%.5f  tp=%.5f",
            ticket,
            side.upper(),
            symbol,
            volume,
            fill_price,
            sl,
            tp,
        )
        return OrderResult(
            success=True,
            ticket=ticket,
            symbol=symbol,
            side=side,
            volume=volume,
            entry_price=fill_price,
        )

    def close_position(self, ticket: int) -> bool:
        """Simulate closing an open position at the current bar's bid/ask."""
        if ticket not in self._positions:
            logger.warning("PaperBroker: No open position with ticket=%d", ticket)
            return False

        pos = self._positions.pop(ticket)
        tick = self.get_tick(pos.symbol)
        close_price = tick.bid if pos.side == "long" else tick.ask
        direction = 1 if pos.side == "long" else -1
        pnl = (close_price - pos.price_open) * direction * pos.volume
        logger.info(
            "PAPER CLOSE ticket=%d  %s %s @ %.5f  PnL=%.2f",
            ticket,
            pos.side.upper(),
            pos.symbol,
            close_price,
            pnl,
        )
        return True

    def get_open_positions(self, symbol: str) -> list[dict[str, Any]]:
        """Return simulated open positions for *symbol*."""
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "side": p.side,
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "magic": p.magic,
            }
            for p in self._positions.values()
            if p.symbol == symbol
        ]
