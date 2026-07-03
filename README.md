# trading

XAUUSD intraday trading bot research starter with **selective signal quality controls** and defensive execution architecture.

## Core principles

- Optimize for **signal quality and risk control**, not vanity win-rate claims.
- `trade_enabled` is `false` by default.
- MT5 live mode requires explicit opt-in.
- No profitability is promised; this is a research-to-paper/live starter.

## Modes

- `backtest`: virtual execution for research.
- `paper`: simulated fills without MT5.
- `mt5`: live terminal execution via `MetaTrader5` Python package (optional dependency).

If `MetaTrader5` is not installed, imports remain safe and MT5 mode raises a clear runtime error only when used.

## A+ setup filtering and quality scoring

Signal assessment is configuration-driven and includes:

- Higher-timeframe alignment
- Session eligibility
- Volatility normalization
- Spread cap
- Recent-loss cooldown
- Minimum room-to-target
- News blackout / stabilization period
- Oversized trigger candle guard

Each setup receives a score and grade (`A+`, `A`, `B`, `C`). Enable `only_a_plus` to reject all non-`A+` setups, and use stricter live score thresholds in MT5 mode.

## Performance gating before scaling/live

Scaling/live eligibility is blocked unless all gates pass:

- Minimum forward trade count
- Maximum drawdown threshold
- Minimum profit factor threshold
- Minimum expectancy threshold
- Optional disablement after recent underperformance

This is defensive gating, not aggressive compounding logic.

## CLI (single-run demo)

```bash
python -m trading.cli run --mode backtest
python -m trading.cli run --mode paper --trade-enabled
python -m trading.cli run --mode mt5 --trade-enabled
```

The CLI prints:

- signal quality grade distribution
- blocked trade reasons
- performance gate status
