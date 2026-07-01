"""
Live and paper trading loop for XAUUSD.

This module drives the execution pipeline in real-time (``mt5`` mode)
or as a bar-by-bar replay (``paper`` mode).  In both cases it:

1. Fetches new 1-minute bars from the broker.
2. Rebuilds aligned 5-minute and 15-minute feature views.
3. Classifies the market regime and routes to the appropriate strategy.
4. Checks all risk limits and kill-switch guards.
5. Submits orders through the broker when ``trade_enabled=true``.

SAFETY NOTES
============
* ``trade_enabled`` **defaults to False**.  Signals are logged but no
  orders are placed unless you explicitly set ``broker.trade_enabled``
  to ``true`` in ``config/settings.yaml``.
* The loop implements multiple kill-switches (stale data, wide spread,
  failed MT5 init, symbol unavailability, duplicate position).
* This is a **research/educational starter** — it does not guarantee
  profitability and has not been validated for production use.
* **Test on a DEMO account only** before considering any other use.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from .broker.base import BrokerBase
from .cost_model import apply_execution_costs
from .features import add_features
from .news_calendar import is_in_news_blackout
from .regime import classify_regime
from .resampling import resample_ohlcv
from .risk_limits import RiskLimits
from .risk_sizing import position_size_from_risk
from .strategy_router import route_signal

logger = logging.getLogger(__name__)

# Minimum bars required before attempting feature computation.
_MIN_BARS = 60


class LiveRunner:
    """
    Drives the live or paper trading loop.

    Parameters
    ----------
    settings : dict
        Full settings dict loaded by :func:`~trading_bot.config_loader.load_settings`.
    broker : BrokerBase
        An **already-initialized** broker (MT5Adapter or PaperBroker).
    news_df : pd.DataFrame, optional
        News calendar DataFrame.  Pass an empty DataFrame to disable
        news filtering.
    """

    def __init__(
        self,
        settings: dict[str, Any],
        broker: BrokerBase,
        news_df: pd.DataFrame | None = None,
    ) -> None:
        self._settings = settings
        self._broker = broker
        self._news_df = news_df if news_df is not None else pd.DataFrame()

        broker_cfg = settings.get("broker", {})
        self._symbol: str = broker_cfg.get("mt5_symbol", settings["project"]["symbol"])
        self._poll_interval: float = float(
            broker_cfg.get("polling_interval_seconds", 60)
        )
        self._max_spread: float = float(broker_cfg.get("max_spread_points", 3.0))
        self._magic: int = int(broker_cfg.get("magic_number", 234000))
        self._trade_enabled: bool = bool(broker_cfg.get("trade_enabled", False))

        self._limits = RiskLimits(
            starting_equity=float(settings["project"].get("starting_equity", 10000)),
            daily_max_loss_pct=float(settings["risk"]["daily_max_loss_pct"]),
            max_consecutive_losses=int(settings["risk"]["max_consecutive_losses"]),
        )
        self._last_bar_ts: pd.Timestamp | None = None

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run_mt5_loop(self) -> None:
        """
        Poll MT5 for new 1-minute bars and manage trades indefinitely.

        Exits on ``KeyboardInterrupt`` or a fatal kill-switch.
        The broker is shut down cleanly in either case.
        """
        self._log_trade_warning()
        logger.info(
            "Starting live MT5 loop — symbol=%s  interval=%.0fs  trade_enabled=%s",
            self._symbol,
            self._poll_interval,
            self._trade_enabled,
        )

        if not self._broker.is_symbol_available(self._symbol):
            logger.error(
                "KILL-SWITCH: Symbol %s unavailable in MT5. Aborting.",
                self._symbol,
            )
            return

        try:
            while True:
                self._poll_once(self._broker, check_staleness=True)
                time.sleep(self._poll_interval)
        except KeyboardInterrupt:
            logger.info("Live loop interrupted by user.")
        finally:
            self._broker.shutdown()

    def run_paper_replay(self, paper_broker: Any) -> None:
        """
        Replay a :class:`~trading_bot.broker.paper_broker.PaperBroker`
        bar-by-bar without real-time sleeping.

        ``paper_broker`` must already be initialized (``initialize()``
        called) before passing it here.
        """
        self._log_trade_warning()
        logger.info("Starting paper replay — symbol=%s", self._symbol)

        while paper_broker.advance_bar():
            ts = paper_broker.current_timestamp
            if ts is None:
                break
            self._limits.reset_day_if_needed(str(ts.date()))
            self._poll_once(paper_broker, check_staleness=False)

        logger.info("Paper replay complete.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_trade_warning(self) -> None:
        if not self._trade_enabled:
            logger.warning(
                "trade_enabled=False — signals will be logged but NO orders placed. "
                "Set broker.trade_enabled=true in settings to enable (DEMO only)."
            )

    def _poll_once(self, broker: BrokerBase, *, check_staleness: bool) -> None:
        """Execute one polling cycle against *broker*."""

        # --- Fetch bars -----------------------------------------------
        try:
            bars_1m = broker.get_bars(self._symbol, "1min", 300)
        except Exception as exc:
            logger.error("KILL-SWITCH: Failed to fetch bars — %s", exc)
            return

        if bars_1m.empty or len(bars_1m) < _MIN_BARS:
            logger.warning(
                "KILL-SWITCH: Insufficient bar data (%d bars) — skipping.",
                len(bars_1m),
            )
            return

        latest_ts: pd.Timestamp = bars_1m.index[-1]

        # --- Stale-data guard (live mode only) ------------------------
        if check_staleness:
            if self._last_bar_ts is not None and latest_ts <= self._last_bar_ts:
                logger.debug("No new bar yet (last=%s) — waiting.", self._last_bar_ts)
                return
            self._last_bar_ts = latest_ts

        # --- Spread guard ---------------------------------------------
        try:
            tick = broker.get_tick(self._symbol)
        except Exception as exc:
            logger.warning("Could not fetch tick: %s — skipping bar.", exc)
            return

        if tick.spread > self._max_spread:
            logger.warning(
                "KILL-SWITCH: Spread %.3f > max %.3f for %s — skipping.",
                tick.spread,
                self._max_spread,
                self._symbol,
            )
            return

        # --- Duplicate-position guard ---------------------------------
        open_positions = broker.get_open_positions(self._symbol)
        if open_positions:
            logger.debug(
                "Open position already exists for %s — skipping signal.", self._symbol
            )
            return

        # --- Feature engineering --------------------------------------
        try:
            f1 = add_features(bars_1m)
            f5 = add_features(resample_ohlcv(bars_1m, "5min"))
            f15 = add_features(resample_ohlcv(bars_1m, "15min"))
        except Exception as exc:
            logger.warning("Feature computation failed: %s — skipping.", exc)
            return

        row_dict = f1.iloc[-1].to_dict()
        if not f5.empty:
            row_dict.update({f"5m_{k}": v for k, v in f5.iloc[-1].to_dict().items()})
        if not f15.empty:
            row_dict.update({f"15m_{k}": v for k, v in f15.iloc[-1].to_dict().items()})

        bar_ts: pd.Timestamp = f1.index[-1]
        self._limits.reset_day_if_needed(str(bar_ts.date()))

        # --- Session hours guard --------------------------------------
        if not self._in_trading_hours(bar_ts):
            logger.debug("Outside trading hours (%s UTC) — skipping.", bar_ts)
            return

        # --- Risk-limits guard ----------------------------------------
        if not self._limits.can_trade():
            logger.warning("Risk limits breached — no trading until next reset.")
            return

        # --- News blackout guard --------------------------------------
        if self._settings["news"].get("enabled", False):
            impacts = set(self._settings["news"].get("impacts", []))
            if is_in_news_blackout(
                bar_ts,
                self._news_df,
                int(self._settings["news"]["blackout_pre_minutes"]),
                int(self._settings["news"]["blackout_post_minutes"]),
                impacts,
            ):
                logger.debug("News blackout at %s — skipping.", bar_ts)
                return

        # --- Regime + strategy signal ---------------------------------
        regime = classify_regime(row_dict, self._settings)
        signal = route_signal(regime, row_dict, self._settings)
        if not signal:
            logger.debug("No signal at %s (regime=%s).", bar_ts, regime)
            return

        atr_val = float(row_dict.get("atr_14", 0.0))
        if atr_val <= 0:
            logger.debug("ATR is zero at %s — cannot size position.", bar_ts)
            return

        # --- Position sizing ------------------------------------------
        side: str = signal["side"]
        price = tick.ask if side == "long" else tick.bid
        stop_dist = atr_val * float(signal["stop_atr_mult"])
        direction = 1 if side == "long" else -1
        stop = price - stop_dist * direction
        tp_price = price + stop_dist * float(signal["take_profit_r"]) * direction

        entry_price, _ = apply_execution_costs(
            price,
            tp_price,
            side,
            tick.spread,
            float(self._settings["execution"]["slippage_points"]),
        )

        size = position_size_from_risk(
            equity=self._limits.starting_equity,
            risk_pct=float(self._settings["risk"]["risk_per_trade"]),
            entry=entry_price,
            stop=stop,
            contract_value_per_point=float(
                self._settings["risk"].get("contract_value_per_point", 1.0)
            ),
        )
        if size <= 0:
            logger.debug("Calculated size <= 0 at %s — skipping.", bar_ts)
            return

        logger.info(
            "SIGNAL  %s %s @ %.5f  stop=%.5f  tp=%.5f  size=%.2f  trade_enabled=%s",
            side.upper(),
            self._symbol,
            entry_price,
            stop,
            tp_price,
            size,
            self._trade_enabled,
        )

        # --- Order submission -----------------------------------------
        if self._trade_enabled:
            result = broker.send_market_order(
                symbol=self._symbol,
                side=side,
                volume=size,
                sl=stop,
                tp=tp_price,
                magic=self._magic,
                comment="xauusd_bot",
            )
            if result.success:
                logger.info(
                    "Order submitted: ticket=%d  entry=%.5f",
                    result.ticket,
                    result.entry_price,
                )
            else:
                logger.error("Order submission failed: %s", result.error)
        else:
            logger.info(
                "(trade_enabled=False) Would place %s order  size=%.2f",
                side,
                size,
            )

    def _in_trading_hours(self, ts: pd.Timestamp) -> bool:
        start, end = self._settings["sessions"]["trade_hours_utc"]
        return start <= ts.hour < end
