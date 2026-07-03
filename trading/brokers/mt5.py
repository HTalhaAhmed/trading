from __future__ import annotations

from .base import Broker
from ..models import ExecutionResult, OrderRequest


class MT5UnavailableError(RuntimeError):
    pass


def _get_mt5_module():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise MT5UnavailableError(
            "MetaTrader5 package is not installed. Use backtest/paper mode or install MetaTrader5."
        ) from exc
    return mt5


class MT5Broker(Broker):
    def __init__(self, *, login: int | None = None, password: str | None = None, server: str | None = None):
        self._mt5 = _get_mt5_module()
        self._connected = False
        self._login = login
        self._password = password
        self._server = server

    def connect(self) -> None:
        kwargs = {
            "login": self._login,
            "password": self._password,
            "server": self._server,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        ok = self._mt5.initialize(**kwargs)
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {self._mt5.last_error()}")
        self._connected = True

    def shutdown(self) -> None:
        if self._connected:
            self._mt5.shutdown()
            self._connected = False

    def submit_order(self, order: OrderRequest) -> ExecutionResult:
        if not self._connected:
            return ExecutionResult(False, "mt5_not_connected")

        tick = self._mt5.symbol_info_tick(order.symbol)
        if tick is None:
            return ExecutionResult(False, "tick_unavailable")

        side = order.side.lower()
        order_type = self._mt5.ORDER_TYPE_BUY if side == "buy" else self._mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "buy" else tick.bid

        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.volume,
            "type": order_type,
            "price": price,
            "sl": order.stop_loss,
            "tp": order.take_profit,
            "deviation": 20,
            "comment": "trading-research-starter",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        result = self._mt5.order_send(request)
        if result is None:
            return ExecutionResult(False, "order_send_failed")

        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            return ExecutionResult(False, f"mt5_retcode_{result.retcode}")

        return ExecutionResult(True, "order_filled", str(result.order))
