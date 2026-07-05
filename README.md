# XAUUSD Intraday Trading Bot Research Scaffold

Research-oriented starter framework for **XAUUSD intraday backtesting, paper testing, MT5 live/demo execution, and explainable A+ trade scanning**.  
This repository is for education, experimentation, and demo testing only.

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
- **explainable trade scanner** — grades every setup and explains _why_
- **A+ only mode** — surface only top-quality setups with full reasoning

> ⚠️ This is a **research scaffold**. Do not trade real funds without extensive forward-testing and a full understanding of the risks.

## Repository layout

```
config/           settings and sample news calendar
data/             sample 1m XAUUSD CSV
src/trading_bot/
  broker/         broker abstraction + MT5 adapter + paper broker
  scanner/        trade scanner, setup grader, multi-reviewer framework
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

## Trade scanner and setup grading

### How the grading model works

The scanner evaluates every setup through **six internal reviewers**, each
focusing on one aspect of trade quality.  The result is deterministic,
rule-based, and fully transparent — there are no hidden "AI" decisions.

| Reviewer | What it evaluates |
|---|---|
| **TrendReviewer** | EMA alignment, VWAP positioning, higher-timeframe trend |
| **MomentumReviewer** | RSI zone, ADX strength, sustained price pressure |
| **VolatilityReviewer** | ATR range, spread quality, candle body shape |
| **ExecutionReviewer** | Strategy signal presence, volume confirmation, VWAP |
| **RiskReviewer** | Daily loss budget, recent loss streak, cooldown state |
| **SessionReviewer** | Session quality, prime hours, news blackout windows |

Each reviewer returns:
- **points** (0 to max_score) based on rule checks
- **reasons** — positive confluences it found
- **cautions** — concerns that do not block but reduce conviction
- **blockers** — hard-stop conditions that make the trade invalid

The raw points are summed and normalised to a 0–1 score, then converted to a
letter grade:

| Score | Grade |
|---|---|
| ≥ 0.88 | **A+** |
| ≥ 0.75 | **A** |
| ≥ 0.60 | **B** |
| ≥ 0.45 | **C** |
| < 0.45 | **REJECTED** |

Any hard blocker (news blackout, daily stop, excessive spread, active cooldown,
etc.) forces the grade to **REJECTED** regardless of score.

### A+ only mode

When `only_a_plus: true` is set in `config/settings.yaml` or via `--only-a-plus`
on the CLI, only A+ setups are **surfaced** (shown / acted upon).  Lower-grade
setups are still evaluated and their blockers/cautions are still logged, so you
can review why they were suppressed.

```yaml
scanner:
  only_a_plus: true    # suppress all setups below A+
  min_score: 0.60      # additional hard floor
```

### Run the scanner from the CLI

Grade the latest setup in a CSV and print the formatted report:

```bash
PYTHONPATH=src python -m trading_bot --mode scan \
  --data data/sample_xauusd_1m.csv \
  --settings config/settings.yaml \
  --news config/news_calendar.yaml
```

Use `--only-a-plus` to override the config and surface only A+ setups:

```bash
PYTHONPATH=src python -m trading_bot --mode scan --only-a-plus
```

Output the result as machine-readable JSON:

```bash
PYTHONPATH=src python -m trading_bot --mode scan --scan-json
```

### Sample A+ setup output

```
============================================================
  TRADE SCANNER — SETUP GRADE REPORT
============================================================
  Direction   : LONG
  Grade       : A+
  Score       : 0.9100  (18.2 / 20.0 pts)
  Surfaced    : YES — A+ opportunity

  ✅ CONFLUENCES (why this setup qualifies):
     • EMA-20 > EMA-50: short-term bullish structure
     • Price above session VWAP: intraday buyers in control
     • HTF trend UP + EMA structure bullish: multi-timeframe alignment confirmed
     • Price above EMA-50: above medium-term average
     • RSI 61.5 in bullish momentum zone (55–65): healthy uptrend momentum
     • ADX 32.1 ≥ 30.0: strong trending environment
     • 7 consecutive bars above EMA-50: sustained bullish pressure
     • ATR 1.20 in acceptable range [0.3–5.0]: healthy volatility
     • Spread 0.25 pts is tight: low execution cost
     • Candle body/range ratio 0.72: strong directional candle
     • Strategy signal confirmed: entry trigger is present
     • Volume ratio 1.35x average: above-average participation
     • Long signal with price above VWAP: buyers confirmed intraday
     • Daily loss 0.0%: within daily risk budget
     • 0 recent losses: acceptable loss history
     • No active cooldown: trade timing is clear
     • Outside all news blackout windows: safe to trade
     • Session: London — high-liquidity prime session
     • Hour 10:xx UTC is within prime trading window (07–16 UTC)

  REVIEWER BREAKDOWN:
  Reviewer                 Score     Pct
  --------------------------------------
  TrendReviewer           4.0/4.0    100%  [██████████]
  MomentumReviewer        3.5/4.0     88%  [█████████░]
  VolatilityReviewer      3.0/3.0    100%  [██████████]
  ExecutionReviewer       3.0/3.0    100%  [██████████]
  RiskReviewer            3.0/3.0    100%  [██████████]
  SessionReviewer         2.5/3.0     83%  [████████░░]
============================================================
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

The backtest automatically respects `scanner.only_a_plus` — when set, only
A+-graded setups are entered during the replay.

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
(backtest, paper, and scan modes) works without it.

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
live-loop guard logic, and the trade scanner/grader (including A+ filtering).
No MT5 installation is required.

## Limitations and risk disclaimer

- Intended for **research and educational use only**.
- Backtests are sensitive to data quality, assumptions, and overfitting risk.
- Spread/slippage handling is simplified and not a substitute for live execution data.
- **No profitability is implied or guaranteed.**
- The MT5 integration is a starter scaffold — it has not been validated in production.
- Live trading on a real account carries substantial financial risk and is **not recommended** without extensive forward-testing, professional advice, and a full understanding of the risks involved.
- Do not trade real funds based solely on this scaffold.

