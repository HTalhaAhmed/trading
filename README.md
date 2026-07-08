# trading

MT5-focused multi-symbol trading bot and scanner for intraday FX and metals workflows. The project separates signal scanning, hard-stop trade controls, alerts, execution, and backtesting. It is designed to run without promising profitability and without requiring MetaTrader5 during local testing.

## Overview

- Multi-symbol scanner ranks setups across a configurable MT5 watchlist.
- Feature pipeline computes EMA, ADX, ATR, RSI, MACD, Bollinger Bands, and spread from raw OHLCV bars.
- Six deterministic reviewers score each setup and assign a transparent grade (`A+`, `A`, `B`, `C`, or `REJECTED`).
- Execution includes a hard-stop guard so blocked trades cannot be sent to MT5.
- Backtesting reuses the same scanner and trade controls against CSV data.

## Watchlist configuration

Edit `config/default_settings.yaml` and use the exact symbol names exposed by your broker. Brokers often append suffixes such as `.a`, `m`, or `.pro`.

```yaml
broker:
  mode: mt5
  trade_enabled: false
  watchlist:
    - XAUUSD
    - EURUSD.a
    - GBPUSD.a
    - USDJPYm
    - XAGUSD.pro
```

## Cap and cooldown behavior

Trade controls are enforced in both scanning diagnostics and the execution layer:

- Daily symbol cap blocks the next trade after the configured per-symbol limit.
- Total daily cap blocks all further trades once the global limit is hit.
- Cooldown blocks repeat entries on the same symbol for the configured number of minutes.
- Session cap blocks additional trades for the same symbol in the same trading session.
- `execution_guard()` is the final hard-stop check before any MT5 order can be sent.

Example blocked alerts:

```text
❌ NO TRADE — daily symbol cap reached (5/5) — XAUUSD
⏸ NO TRADE — cooldown active (12m remaining) — GBPUSD
🚫 NO TRADE — session cap reached (2/2 in london) — USDJPY
```

## Running the scanner

Install dependencies and run tests:

```bash
pip install -r requirements.txt
PYTHONPATH=src pytest -q
```

Scan the configured watchlist:

```bash
PYTHONPATH=src python -m trading_bot --mode scan
```

Scan a single symbol:

```bash
PYTHONPATH=src python -m trading_bot --mode scan --symbol XAUUSD
```

Override watchlist symbols from the CLI:

```bash
PYTHONPATH=src python -m trading_bot --mode paper --watchlist XAUUSD EURUSD GBPUSD
```

Run a CSV backtest:

```bash
PYTHONPATH=src python -m trading_bot --mode backtest --data data/sample.csv --symbol XAUUSD --format json
```
