# XAUUSD Intraday Trading Bot Research Scaffold

Research-oriented starter framework for **XAUUSD intraday backtesting**. This repository is for education, experimentation, and paper testing only.

## Overview

The project provides a modular Python scaffold for:
- loading 1m XAUUSD data from CSV
- building aligned 5m/15m bars
- feature engineering (EMA, ATR, ADX, RSI, session VWAP)
- regime-aware strategy routing (trend pullback and range reversion)
- event-driven backtesting with spread/slippage
- basic risk sizing, daily risk limits, and performance reporting

> This is **not** a live trading system and includes no broker integration.

## Repository layout

- `config/` settings and sample news calendar
- `data/` sample 1m XAUUSD CSV
- `src/trading_bot/` core modules
- `tests/` basic unit tests

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

The CLI prints summary metrics and optionally exports:
- `output/trades.csv`
- `output/equity_curve.csv`

## Current strategy scaffold

- **Trend pullback continuation**: EMA alignment + VWAP confirmation in trending regime
- **Range reversion**: RSI extremes around VWAP in ranging regime
- **Router**: dispatches strategy by detected regime

## Reported metrics

- total trades
- win rate
- net PnL
- ending equity
- max drawdown
- profit factor
- average win
- average loss

## Limitations and risk disclaimer

- Intended for research and educational use only.
- Backtests are sensitive to data quality, assumptions, and overfitting risk.
- Spread/slippage handling is simplified and not a substitute for live execution data.
- No profitability is implied or guaranteed.
- Do not trade real funds based solely on this scaffold.
