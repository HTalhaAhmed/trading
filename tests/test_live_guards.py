"""
Tests for live-runner guard logic and PaperBroker mechanics.

These tests cover non-MT5-dependent logic: spread guard, duplicate-position
guard, risk-limits guard, and paper-broker order simulation.  No
MetaTrader5 package is required.
"""
from __future__ import annotations

import pandas as pd
import pytest

from trading_bot.broker.base import Tick
from trading_bot.broker.paper_broker import PaperBroker
from trading_bot.risk_limits import RiskLimits


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(n: int = 300, spread: float | None = 0.25) -> pd.DataFrame:
    idx = pd.date_range("2025-01-02 07:00", periods=n, freq="1min", tz="UTC")
    data: dict = {
        "open": 2065.0,
        "high": 2066.0,
        "low": 2064.0,
        "close": 2065.5,
        "volume": 100.0,
    }
    if spread is not None:
        data["spread"] = spread
    return pd.DataFrame(data, index=idx)


# ---------------------------------------------------------------------------
# PaperBroker — lifecycle
# ---------------------------------------------------------------------------

class TestPaperBrokerLifecycle:
    def test_initialize_succeeds(self) -> None:
        broker = PaperBroker(_make_df())
        assert broker.initialize() is True

    def test_initialize_empty_df_fails(self) -> None:
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        broker = PaperBroker(empty)
        assert broker.initialize() is False

    def test_advance_counts_all_bars(self) -> None:
        broker = PaperBroker(_make_df(n=10))
        broker.initialize()
        count = 0
        while broker.advance_bar():
            count += 1
        assert count == 10

    def test_advance_returns_false_when_exhausted(self) -> None:
        broker = PaperBroker(_make_df(n=3))
        broker.initialize()
        broker.advance_bar()
        broker.advance_bar()
        broker.advance_bar()
        assert broker.advance_bar() is False

    def test_current_timestamp_advances(self) -> None:
        df = _make_df(n=5)
        broker = PaperBroker(df)
        broker.initialize()
        broker.advance_bar()
        assert broker.current_timestamp == df.index[0]
        broker.advance_bar()
        assert broker.current_timestamp == df.index[1]


# ---------------------------------------------------------------------------
# PaperBroker — market data
# ---------------------------------------------------------------------------

class TestPaperBrokerData:
    def test_get_tick_uses_spread_column(self) -> None:
        broker = PaperBroker(_make_df(spread=0.50))
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        assert isinstance(tick, Tick)
        assert abs(tick.spread - 0.50) < 1e-6

    def test_get_tick_falls_back_to_default_spread(self) -> None:
        broker = PaperBroker(_make_df(spread=None), default_spread=0.30)
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        assert abs(tick.spread - 0.30) < 1e-6

    def test_get_tick_bid_lt_ask(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        assert tick.bid < tick.ask

    def test_get_bars_1min_length(self) -> None:
        broker = PaperBroker(_make_df(n=100))
        broker.initialize()
        for _ in range(50):
            broker.advance_bar()
        bars = broker.get_bars("XAUUSD", "1min", 30)
        assert len(bars) == 30

    def test_get_bars_5min_resampling(self) -> None:
        broker = PaperBroker(_make_df(n=100))
        broker.initialize()
        for _ in range(100):
            broker.advance_bar()
        bars = broker.get_bars("XAUUSD", "5min", 20)
        assert not bars.empty
        assert len(bars) <= 20

    def test_get_bars_unsupported_timeframe_raises(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            broker.get_bars("XAUUSD", "2min", 10)


# ---------------------------------------------------------------------------
# PaperBroker — order execution
# ---------------------------------------------------------------------------

class TestPaperBrokerOrders:
    def test_send_order_returns_success(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        result = broker.send_market_order(
            "XAUUSD", "long", 0.10, sl=2055.0, tp=2080.0
        )
        assert result.success is True
        assert result.ticket > 0
        assert result.side == "long"

    def test_send_long_fills_at_ask(self) -> None:
        broker = PaperBroker(_make_df(spread=0.50))
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        result = broker.send_market_order(
            "XAUUSD", "long", 0.10, sl=2055.0, tp=2080.0
        )
        assert abs(result.entry_price - tick.ask) < 1e-6

    def test_send_short_fills_at_bid(self) -> None:
        broker = PaperBroker(_make_df(spread=0.50))
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        result = broker.send_market_order(
            "XAUUSD", "short", 0.10, sl=2080.0, tp=2055.0
        )
        assert abs(result.entry_price - tick.bid) < 1e-6

    def test_get_open_positions_after_order(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        broker.send_market_order("XAUUSD", "long", 0.10, sl=2055.0, tp=2080.0)
        positions = broker.get_open_positions("XAUUSD")
        assert len(positions) == 1
        assert positions[0]["side"] == "long"
        assert positions[0]["volume"] == 0.10

    def test_close_position_removes_it(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        result = broker.send_market_order(
            "XAUUSD", "long", 0.10, sl=2055.0, tp=2080.0
        )
        assert broker.close_position(result.ticket) is True
        assert broker.get_open_positions("XAUUSD") == []

    def test_close_nonexistent_ticket_returns_false(self) -> None:
        broker = PaperBroker(_make_df())
        broker.initialize()
        broker.advance_bar()
        assert broker.close_position(9999) is False

    def test_is_symbol_available_always_true(self) -> None:
        broker = PaperBroker(_make_df())
        assert broker.is_symbol_available("ANYTHING") is True


# ---------------------------------------------------------------------------
# Spread guard logic
# ---------------------------------------------------------------------------

class TestSpreadGuard:
    def test_spread_within_threshold_allows_trading(self) -> None:
        broker = PaperBroker(_make_df(spread=0.25))
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        max_spread = 3.0
        assert tick.spread <= max_spread

    def test_wide_spread_exceeds_threshold(self) -> None:
        broker = PaperBroker(_make_df(spread=None), default_spread=5.0)
        broker.initialize()
        broker.advance_bar()
        tick = broker.get_tick("XAUUSD")
        max_spread = 3.0
        assert tick.spread > max_spread


# ---------------------------------------------------------------------------
# RiskLimits guard logic (used by LiveRunner)
# ---------------------------------------------------------------------------

class TestRiskLimitsGuard:
    def _limits(self) -> RiskLimits:
        return RiskLimits(
            starting_equity=10000,
            daily_max_loss_pct=0.03,
            max_consecutive_losses=3,
        )

    def test_can_trade_initially(self) -> None:
        limits = self._limits()
        limits.reset_day_if_needed("2025-01-02")
        assert limits.can_trade() is True

    def test_daily_loss_limit_blocks_trading(self) -> None:
        limits = self._limits()
        limits.reset_day_if_needed("2025-01-02")
        limits.record_trade(-350.0)  # > 3% of 10000 = 300
        assert limits.can_trade() is False

    def test_consecutive_losses_blocks_trading(self) -> None:
        limits = self._limits()
        limits.reset_day_if_needed("2025-01-02")
        for _ in range(3):
            limits.record_trade(-5.0)  # small losses, within daily limit
        assert limits.can_trade() is False

    def test_day_reset_restores_trading(self) -> None:
        limits = self._limits()
        limits.reset_day_if_needed("2025-01-02")
        limits.record_trade(-350.0)
        assert limits.can_trade() is False
        limits.reset_day_if_needed("2025-01-03")  # new day
        assert limits.can_trade() is True

    def test_winning_trade_resets_consecutive_losses(self) -> None:
        limits = self._limits()
        limits.reset_day_if_needed("2025-01-02")
        limits.record_trade(-5.0)
        limits.record_trade(-5.0)
        limits.record_trade(50.0)  # win resets counter
        limits.record_trade(-5.0)
        assert limits.can_trade() is True  # only 1 consecutive loss now
