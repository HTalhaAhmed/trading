"""
Abstract broker interface.

All concrete broker implementations (MT5, paper) must subclass
``BrokerBase``.  Implementations must be **import-safe**: any
platform-specific package (e.g. MetaTrader5) must be imported lazily
inside method bodies so that the rest of the project works without
that package installed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class Tick:
    """Current bid/ask snapshot for a symbol."""

    symbol: str
    bid: float
    ask: float

    @property
    def spread(self) -> float:
        """Raw spread in price units (e.g. USD for XAUUSD)."""
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        """Mid-price between bid and ask."""
        return (self.bid + self.ask) / 2.0


@dataclass
class OrderResult:
    """Result returned by ``send_market_order``."""

    success: bool
    ticket: int = 0
    symbol: str = ""
    side: str = ""          # "long" or "short"
    volume: float = 0.0
    entry_price: float = 0.0
    error: str | None = None


class BrokerBase(ABC):
    """
    Abstract interface for broker/platform operations.

    Subclasses implement both market-data access and order execution so
    that the live runner can work with any backend (MT5, paper, etc.)
    through a single interface.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """Connect to the broker/terminal. Return True on success."""

    @abstractmethod
    def shutdown(self) -> None:
        """Disconnect and release resources cleanly."""

    @abstractmethod
    def is_symbol_available(self, symbol: str) -> bool:
        """Return True if the symbol is recognised and tradeable."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """
        Return a DataFrame with columns [open, high, low, close, volume]
        and a timezone-aware DatetimeIndex (UTC), newest bar last.

        ``timeframe`` uses pandas-compatible strings: ``"1min"``,
        ``"5min"``, ``"15min"``, etc.
        """

    @abstractmethod
    def get_tick(self, symbol: str) -> Tick:
        """Return the latest bid/ask tick for the symbol."""

    @abstractmethod
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
        """
        Submit a market order.

        Parameters
        ----------
        symbol : str
            Instrument symbol (e.g. ``"XAUUSD"``).
        side : str
            ``"long"`` for buy, ``"short"`` for sell.
        volume : float
            Lot size.
        sl : float
            Stop-loss as an absolute price level.
        tp : float
            Take-profit as an absolute price level.
        magic : int
            Broker magic number (used to identify bot orders).
        comment : str
            Optional order comment.
        """

    @abstractmethod
    def close_position(self, ticket: int) -> bool:
        """Close an open position by ticket number. Return True on success."""

    @abstractmethod
    def get_open_positions(self, symbol: str) -> list[dict[str, Any]]:
        """
        Return open positions for *symbol*.

        Each dict contains at least:
        ``ticket``, ``symbol``, ``side``, ``volume``, ``price_open``,
        ``sl``, ``tp``, ``magic``.
        """
