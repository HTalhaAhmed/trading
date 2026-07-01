# XAUUSD Intraday Trading Bot Research Scaffold

Research-oriented starter framework for **XAUUSD intraday backtesting, paper testing, and MT5 live/demo execution**. This repository is for education, experimentation, and demo testing only.

## Overview

The project provides a modular Python scaffold for:
- loading 1m XAUUSD data from CSV
- building aligned 5m/15m bars
- feature engineering (EMA, ATR, ADX, RSI, session VWAP)
- regime-aware strategy routing (trend pullback and range reversion)
- event-driven backtesting with spread/slippage
- basic risk sizing, daily risk limits, and performance reporting
- **MT5 live/demo execution** via a broker abstraction layer
- **paper replay mode** — simulated fills, no broker required

> ⚠️ This is a **research scaffold**. Do not trade real funds without extensive forward-testing and a full understanding of the risks.

## Repository layout

```
config/           settings and sample news calendar
data/             sample 1m XAUUSD CSV
src/trading_bot/
  broker/         broker abstraction + MT5 adapter + paper broker
  live_runner.py  live/paper trading loop
  ...             core research engine modules
tests/            unit tests (no MT5 required)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Expected CSV schema

Required columns:
- `timestamp` (ISO8601 recommended, UTC)
- `open`, `high`, `low`, `close`, `volume`

Optional:
- `spread` (points, per-bar average or observed spread)

Example row:

```csv
timestamp,open,high,low,close,volume,spread
2025-01-02T07:00:00Z,2065.0,2065.6,2064.9,2065.4,120,0.25
```

## Run a backtest

```bash
PYTHONPATH=src python -m trading_bot \
  --data data/sample_xauusd_1m.csv \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml \
  --output-dir output
```

Or explicitly:

```bash
PYTHONPATH=src python -m trading_bot --mode backtest \
  --data data/sample_xauusd_1m.csv \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml
```

The CLI prints summary metrics and optionally exports:
- `output/trades.csv`
- `output/equity_curve.csv`

## Run in paper mode (CSV replay, no MT5 needed)

Paper mode replays your CSV bar-by-bar through a simulated broker that
records fills without sending real orders.

```bash
PYTHONPATH=src python -m trading_bot --mode paper \
  --data data/sample_xauusd_1m.csv \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml
```

This is the recommended first step after backtesting.

## MT5 live/demo execution

### Install the MetaTrader5 Python package

The `MetaTrader5` Python package is **Windows-only** and requires the
MetaTrader 5 terminal to be installed and running.

```bash
pip install MetaTrader5
```

On macOS/Linux the package is not available; the rest of the project
(backtest and paper modes) works without it.

### Connect to a demo account

1. Open MetaTrader 5 and log in to a **demo account** (create one via
   your broker if needed).
2. Make sure `XAUUSD` (or your broker's equivalent, e.g. `XAUUSDm`) is
   visible in the Market Watch panel.
3. Keep the terminal running before starting the bot.

### Set credentials via environment variables

**Never hard-code credentials in source files.**

```bash
export MT5_LOGIN=12345678
export MT5_PASSWORD=your_demo_password
export MT5_SERVER=YourBroker-Demo
```

Or set them in `.env` and load with `dotenv` (not committed to git).

### Enable paper signals in MT5 mode (no real orders)

In `config/settings.yaml`, ensure:

```yaml
broker:
  mode: mt5
  mt5_symbol: XAUUSD   # adjust for your broker's suffix if needed
  trade_enabled: false  # signals logged, no orders sent
```

Then run:

```bash
PYTHONPATH=src python -m trading_bot --mode mt5 \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml
```

Watch the log output for `SIGNAL` lines. Only when you are satisfied
with the signal quality on demo should you consider enabling orders.

### Enable demo order placement

**Only do this on a DEMO account after thorough paper testing.**

```yaml
broker:
  trade_enabled: true   # enables actual MT5 order submission
```

```bash
PYTHONPATH=src python -m trading_bot --mode mt5 \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml
```

Press `Ctrl-C` to stop the loop gracefully.

### How MT5 market data is read

The `MT5Adapter.get_bars()` method calls `mt5.copy_rates_from_pos()` to
fetch the most recent N closed 1-minute bars for the configured symbol.
These are converted to a pandas DataFrame and fed through the same
feature-engineering pipeline used in backtesting.

### How orders are submitted to MT5

`MT5Adapter.send_market_order()` constructs an `ORDER_TYPE_BUY` or
`ORDER_TYPE_SELL` request with stop-loss, take-profit, and magic number,
then calls `mt5.order_send()`. The result is checked for
`TRADE_RETCODE_DONE`; any failure is logged with the MT5 error code and
no retry is attempted.

### Kill-switch behaviour

The live loop aborts or skips the current bar when:

| Condition | Behaviour |
|-----------|-----------|
| MT5 `initialize()` fails | Fatal abort |
| Symbol unavailable in MT5 | Fatal abort |
| Spread > `max_spread_points` | Skip bar |
| Open position already exists | Skip signal |
| `can_trade()` returns False | Skip signal |
| News blackout window | Skip signal |
| Stale / no new bar | Skip poll cycle |
| Feature computation error | Skip bar |

## Current strategy scaffold

- **Trend pullback continuation**: EMA alignment + VWAP confirmation in trending regime
- **Range reversion**: RSI extremes around VWAP in ranging regime
- **Router**: dispatches strategy by detected regime

## Reported metrics (backtest mode)

- total trades
- win rate
- net PnL
- ending equity
- max drawdown
- profit factor
- average win
- average loss

## Run tests

```bash
pytest -q
```

Tests cover indicators, features, risk sizing, broker config parsing,
and live-loop guard logic. No MT5 installation is required.

## Limitations and risk disclaimer

- Intended for **research and educational use only**.
- Backtests are sensitive to data quality, assumptions, and overfitting risk.
- Spread/slippage handling is simplified and not a substitute for live execution data.
- **No profitability is implied or guaranteed.**
- The MT5 integration is a starter scaffold — it has not been validated in production.
- Live trading on a real account carries substantial financial risk and is **not recommended** without extensive forward-testing, professional advice, and a full understanding of the risks involved.
- Do not trade real funds based solely on this scaffold.
