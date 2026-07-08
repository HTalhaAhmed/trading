from __future__ import annotations

from datetime import datetime

from .trade_controls import TradeControlManager

try:
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:  # pragma: no cover - expected in tests
    MT5_AVAILABLE = False
    mt5 = None


class MT5Executor:
    def __init__(self, config: dict, trade_controls: TradeControlManager):
        self.trade_controls = trade_controls
        self.config = config

    def place_order(
        self,
        symbol: str,
        direction: str,
        lot_size: float = 0.01,
        sl_pips: float = None,
        tp_pips: float = None,
        now: datetime | None = None,
    ) -> dict:
        """
        Place a trade order with full hard-stop protection.
        """
        now = now or datetime.utcnow()
        guard = self.trade_controls.execution_guard(symbol, now=now)
        if not guard.allowed:
            return {'success': False, 'reason': guard.blocker_reason, 'order_id': None}

        if direction not in {'LONG', 'SHORT'}:
            return {'success': False, 'reason': 'invalid trade direction', 'order_id': None}

        if not self.config.get('broker', {}).get('trade_enabled', False):
            self.trade_controls.record_trade(symbol, now=now)
            return {'success': True, 'reason': 'paper mode — order simulated', 'order_id': None}

        if not MT5_AVAILABLE:
            return {'success': False, 'reason': 'MT5 unavailable', 'order_id': None}
        if not mt5.initialize():
            return {'success': False, 'reason': 'MT5 initialize failed', 'order_id': None}

        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        if tick is None or symbol_info is None:
            mt5.shutdown()
            return {'success': False, 'reason': 'symbol market data unavailable', 'order_id': None}

        point = getattr(symbol_info, 'point', 0.0) or 0.0
        price = tick.ask if direction == 'LONG' else tick.bid
        sl = 0.0
        tp = 0.0
        if sl_pips is not None and point > 0:
            sl = price - sl_pips * point if direction == 'LONG' else price + sl_pips * point
        if tp_pips is not None and point > 0:
            tp = price + tp_pips * point if direction == 'LONG' else price - tp_pips * point

        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': lot_size,
            'type': mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL,
            'price': price,
            'sl': sl,
            'tp': tp,
            'deviation': 20,
            'magic': 20260708,
            'comment': 'trading_bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        mt5.shutdown()
        if result is None or getattr(result, 'retcode', None) != mt5.TRADE_RETCODE_DONE:
            return {'success': False, 'reason': 'MT5 order rejected', 'order_id': None}

        self.trade_controls.record_trade(symbol, now=now)
        return {'success': True, 'reason': 'order placed', 'order_id': getattr(result, 'order', None)}
