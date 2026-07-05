"""
MetaTrader 5 broker adapter.

⚠️  STARTER IMPLEMENTATION — must be tested on a DEMO account before
    any other use.  Live trading on a real account carries substantial
    financial risk.

Requirements
------------
* MetaTrader 5 terminal installed and running on Windows.
* ``MetaTrader5`` Python package::

    pip install MetaTrader5

  MetaTrader5 is only available on Windows; importing this module on
  other platforms is safe but calling any method will raise
  ``RuntimeError``.

Credentials
-----------
Do **not** hard-code credentials.  Supply them via environment variables
or pass them explicitly to ``__init__``::

    export MT5_LOGIN=12345678
    export MT5_PASSWORD=your_demo_password
    export MT5_SERVER=BrokerName-Demo

"""
from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from .base import BrokerBase, OrderResult, Tick

logger = logging.getLogger(__name__)

# Lazily populated map from our timeframe strings → MT5 constants.
_TF_MAP: dict[str, int] | None = None


def _resolve_tf_map() -> dict[str, int]:
    global _TF_MAP
    if _TF_MAP is not None:
        return _TF_MAP
    try:
        import MetaTrader5 as mt5  # noqa: PLC0415
    except ImportError:
        raise RuntimeError(
            "MetaTrader5 package is not installed. "
            "Install with: pip install MetaTrader5\n"
            "Note: the package is only available on Windows."
        ) from None
    _TF_MAP = {
        "1min": mt5.TIMEFRAME_M1,
        "5min": mt5.TIMEFRAME_M5,
        "15min": mt5.TIMEFRAME_M15,
        "30min": mt5.TIMEFRAME_M30,
        "1H": mt5.TIMEFRAME_H1,
        "4H": mt5.TIMEFRAME_H4,
        "1D": mt5.TIMEFRAME_D1,
    }
    return _TF_MAP


def _mt5_timeframe(timeframe: str) -> int:
    tf_map = _resolve_tf_map()
    if timeframe not in tf_map:
        raise ValueError(
            f"Unsupported timeframe {timeframe!r}. "
            f"Supported values: {list(tf_map)}"
        )
    return tf_map[timeframe]


class MT5Adapter(BrokerBase):
    """
    MetaTrader 5 broker adapter.

    ⚠️  STARTER IMPLEMENTATION — test on DEMO only.

    Parameters
    ----------
    login : int, optional
        MT5 account login.  Falls back to ``MT5_LOGIN`` env var.
    password : str, optional
        MT5 account password.  Falls back to ``MT5_PASSWORD`` env var.
    server : str, optional
        MT5 broker server name.  Falls back to ``MT5_SERVER`` env var.
    """

    def __init__(
        self,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> None:
        self._login: int = login or int(os.environ.get("MT5_LOGIN", "0") or "0")
        self._password: str = password or os.environ.get("MT5_PASSWORD", "")
        self._server: str = server or os.environ.get("MT5_SERVER", "")
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """Connect to the MT5 terminal. Returns True on success."""
        try:
            import MetaTrader5 as mt5  # noqa: PLC0415
        except ImportError:
            logger.error(
                "MetaTrader5 package not found. Install with: pip install MetaTrader5"
            )
            return False

        kwargs: dict[str, Any] = {}
        if self._login:
            kwargs["login"] = self._login
        if self._password:
            kwargs["password"] = self._password
        if self._server:
            kwargs["server"] = self._server

        if not mt5.initialize(**kwargs):
            logger.error("MT5 initialize() failed: %s", mt5.last_error())
            return False

        info = mt5.account_info()
        if info is None:
            logger.error("MT5 account_info() returned None after initialize()")
            mt5.shutdown()
            return False

        logger.info(
            "MT5 connected — account=%s server=%s balance=%.2f",
            info.login,
            info.server,
            info.balance,
        )
        self._initialized = True
        return True

    def shutdown(self) -> None:
        """Disconnect from the MT5 terminal."""
        if self._initialized:
            try:
                import MetaTrader5 as mt5  # noqa: PLC0415

                mt5.shutdown()
                logger.info("MT5 connection closed.")
            except ImportError:
                pass
            self._initialized = False

    # ------------------------------------------------------------------
    # Symbol / market data
    # ------------------------------------------------------------------

    def is_symbol_available(self, symbol: str) -> bool:
        """Return True if *symbol* is available and visible in Market Watch."""
        try:
            import MetaTrader5 as mt5  # noqa: PLC0415
        except ImportError:
            return False

        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning("Symbol %s not found in MT5.", symbol)
            return False
        if not info.visible:
            # Attempt to add symbol to Market Watch
            mt5.symbol_select(symbol, True)
        return True

    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """
        Fetch the most recent *count* bars for *symbol* at *timeframe*.

        Returns a DataFrame indexed by UTC timestamp with columns:
        open, high, low, close, volume.
        """
        import MetaTrader5 as mt5  # noqa: PLC0415

        tf = _mt5_timeframe(timeframe)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"MT5 copy_rates_from_pos failed for {symbol}: {mt5.last_error()}"
            )

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"time": "timestamp", "tick_volume": "volume"})
        df = df.set_index("timestamp").sort_index()
        return df[["open", "high", "low", "close", "volume"]]

    def get_tick(self, symbol: str) -> Tick:
        """Return the latest bid/ask tick for *symbol*."""
        import MetaTrader5 as mt5  # noqa: PLC0415

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(
                f"MT5 symbol_info_tick failed for {symbol}: {mt5.last_error()}"
            )
        return Tick(symbol=symbol, bid=tick.bid, ask=tick.ask)

    # ------------------------------------------------------------------
    # Order execution
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
        """
        Submit a market order to MT5.

        ⚠️  Only call this on a DEMO account until the strategy has
            been extensively validated.
        """
        import MetaTrader5 as mt5  # noqa: PLC0415

        order_type = mt5.ORDER_TYPE_BUY if side == "long" else mt5.ORDER_TYPE_SELL
        tick = self.get_tick(symbol)
        price = tick.ask if side == "long" else tick.bid

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 10,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = getattr(result, "comment", None) or str(mt5.last_error())
            logger.error(
                "MT5 order_send failed: retcode=%s err=%s",
                getattr(result, "retcode", None),
                err,
            )
            return OrderResult(success=False, error=err)

        return OrderResult(
            success=True,
            ticket=result.order,
            symbol=symbol,
            side=side,
            volume=volume,
            entry_price=result.price,
        )

    def close_position(self, ticket: int) -> bool:
        """Close an open position identified by *ticket*."""
        import MetaTrader5 as mt5  # noqa: PLC0415

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning("No open position found with ticket=%s", ticket)
            return False

        pos = positions[0]
        side = "long" if pos.type == mt5.POSITION_TYPE_BUY else "short"
        close_type = mt5.ORDER_TYPE_SELL if side == "long" else mt5.ORDER_TYPE_BUY
        tick = self.get_tick(pos.symbol)
        price = tick.bid if side == "long" else tick.ask

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 10,
            "magic": pos.magic,
            "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = getattr(result, "comment", None) or str(mt5.last_error())
            logger.error("MT5 close_position failed: ticket=%s err=%s", ticket, err)
            return False
        return True

    def get_open_positions(self, symbol: str) -> list[dict[str, Any]]:
        """Return all open positions for *symbol*."""
        import MetaTrader5 as mt5  # noqa: PLC0415

        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "side": "long" if p.type == mt5.POSITION_TYPE_BUY else "short",
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "magic": p.magic,
            }
            for p in positions
        ]
