# trading

XAUUSD intraday trading bot research repository.

---

## Overview

A quality-first XAUUSD signal scanner with explainable grading.  
The bot scans multi-timeframe OHLCV data and produces a **LONG / SHORT / NO TRADE**
decision with a grade (**A+, A, B, C, REJECTED**) and plain-English reasons.

**Design goals**
- Deterministic and transparent — same data → same grade, every time
- A+ is meaningfully rare — all six reviewers must individually pass
- Explainable — every decision includes reasons, cautions, and blockers
- Multiple output formats — human report, dashboard card, Telegram alert, JSON

---

## Quick start

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m trading_bot --mode scan
```

---

## Output formats

Choose with `--format`:

| Flag | Use case |
|------|----------|
| `report` (default) | Full human-readable report with reviewer breakdown |
| `compact` | Single-line card for dashboards / log lines |
| `telegram` | Concise plain-text alert for Telegram bots |
| `json` | Machine-readable JSON (stable schema v1) |

### Human report (`--format report`)

```
════════════════════════════════════════════════════════════
  XAUUSD SCAN RESULT  ·  2025-01-15 14:32 UTC
════════════════════════════════════════════════════════════
  Symbol    : XAUUSD
  Session   : London/NY Overlap
  Direction : 📈 LONG
  Grade     : 🏆 A+
  Score     : 91/100
────────────────────────────────────────────────────────────
  ✔  WHY THIS SETUP QUALIFIES
     · M15 full bull EMA stack confirmed (9>21>50>200)
     · M5 bull EMA stack with price above all EMAs
     · M15 higher-highs / higher-lows structure intact
     · M5 RSI 63 in bullish momentum zone (55-70)
     · M5 MACD histogram positive and expanding
     · Strong bull close on M5 (body 74% of range)
     · ATR 14.2 pts — healthy volatility regime
     · Spread 1.5 pts — acceptable
     · Room to target 2.0R — strong potential
     · London/NY overlap session — highest liquidity
     · No imminent high-impact news — safe to trade
  ⚠  CAUTIONS
     · Momentum slightly extended near daily high
────────────────────────────────────────────────────────────
  REVIEWER BREAKDOWN
  ✔ Trend          22/25   (88%)
  ✔ Momentum       17/20   (85%)
  ✔ Volatility     14/15   (93%)
  ✔ Execution      13/15   (87%)
  ✔ Risk           13/15   (87%)
  ✔ Session        10/10  (100%)
────────────────────────────────────────────────────────────
  Entry   : 2345.60
  Stop    : 2330.60  (dist: 15.0 pts)
  Target  : 2375.60  (R:R = 2.0)
════════════════════════════════════════════════════════════
```

### Compact summary (`--format compact`)

```
XAUUSD | LONG | [A+] 91/100 | London/NY Overlap | 2025-01-15 14:32 UTC
  M15 full bull EMA stack confirmed | ⚠ Momentum slightly extended near daily high
```

### Telegram alert (`--format telegram`)

```
📊 XAUUSD SIGNAL
Direction: 📈 LONG
Grade: 🏆 A+   Score: 91/100
Session: London/NY Overlap
Time: 2025-01-15 14:32 UTC

✅ REASONS
· M15 full bull EMA stack confirmed (9>21>50>200)
· M5 bull EMA stack with price above all EMAs
· M15 higher-highs / higher-lows structure intact
· M5 RSI 63 in bullish momentum zone (55-70)
· M5 MACD histogram positive and expanding
  (+6 more)

⚠ CAUTIONS
· Momentum slightly extended near daily high

Entry: 2345.60  Stop: 2330.60  Target: 2375.60  R:R 2.0
```

### JSON output (`--format json`)

```json
{
  "schema_version": 1,
  "symbol": "XAUUSD",
  "timestamp_utc": "2025-01-15T14:32:00+00:00",
  "session": "London/NY Overlap",
  "direction": "LONG",
  "grade": "A+",
  "score": 91,
  "max_score": 100,
  "is_a_plus": true,
  "is_tradeable": true,
  "entry": 2345.6,
  "stop": 2330.6,
  "target": 2375.6,
  "rr": 2.0,
  "stop_distance": 15.0,
  "reasons": ["M15 full bull EMA stack confirmed (9>21>50>200)", "..."],
  "cautions": ["Momentum slightly extended near daily high"],
  "blockers": [],
  "a_plus_gap": [],
  "reviewer_scores": {
    "Trend":      {"score": 22, "max_score": 25, "passed": true},
    "Momentum":   {"score": 17, "max_score": 20, "passed": true},
    "Volatility": {"score": 14, "max_score": 15, "passed": true},
    "Execution":  {"score": 13, "max_score": 15, "passed": true},
    "Risk":       {"score": 13, "max_score": 15, "passed": true},
    "Session":    {"score": 10, "max_score": 10, "passed": true}
  }
}
```

---

## A+ selectivity

A+ is intentionally strict. Three conditions must **all** be true simultaneously:

1. **Raw score >= 90/100** — aggregate of all six reviewers
2. **Every reviewer individually passes its minimum** — no weak link
3. **No hard blockers** — spread, news, R:R, and room-to-target gates must all clear

### Per-reviewer A+ minimums (config defaults)

| Reviewer | Max pts | A+ minimum | % required |
|----------|---------|------------|------------|
| Trend | 25 | 20 | 80% |
| Momentum | 20 | 15 | 75% |
| Volatility | 15 | 11 | 73% |
| Execution | 15 | 11 | 73% |
| Risk | 15 | 11 | 73% |
| Session | 10 | 7 | 70% |

A setup graded **A** (score 80–89) but failing the Trend minimum will
stay at **A** — not promoted to **A+**. The report's `WHY NOT A+` section will
explain exactly which reviewer fell short.

### Hard blockers (force REJECTED regardless of score)

- Spread above `max_spread_points` (default 3.0 pts)
- ATR spike > 2.5x its 20-bar average
- Room to target < 1.0R
- R:R ratio < 1.2
- High-impact news window active or < 5 minutes away

### Example: why a setup is C not A+

```
  ℹ  WHY NOT A+
     · Score 60/100 below A+ threshold 90 (need 30 more points)
     · Trend reviewer: 9/25 (need 20 for A+)
     · Momentum reviewer: 6/20 (need 15 for A+)
     · Session reviewer: 6/10 (need 7 for A+)
```

---

## CLI reference

```bash
# Default human report
PYTHONPATH=src python -m trading_bot --mode scan

# Only emit A+ setups (suppress everything else)
PYTHONPATH=src python -m trading_bot --mode scan --only-a-plus

# Dashboard-friendly one-liner
PYTHONPATH=src python -m trading_bot --mode scan --format compact

# Telegram bot integration
PYTHONPATH=src python -m trading_bot --mode scan --format telegram

# Machine-readable JSON for external dashboard
PYTHONPATH=src python -m trading_bot --mode scan --format json

# Backtest with custom data
PYTHONPATH=src python -m trading_bot --mode backtest \
    --data path/to/xauusd_m1.csv \
    --settings path/to/settings.json \
    --news path/to/news.csv
```

---

## Running tests

```bash
PYTHONPATH=src pytest -q
```

---

## Grading model

Six independent reviewers, each scoring a different quality dimension:

| Reviewer | Max | What it checks |
|----------|-----|----------------|
| Trend | 25 | M15/M5 EMA stack, price structure |
| Momentum | 20 | RSI, MACD histogram, candle body, volume |
| Volatility | 15 | ATR health range, spike detection |
| Execution | 15 | Spread, room to target, entry timing |
| Risk | 15 | R:R ratio, stop placement vs ATR |
| Session | 10 | London/NY session, news blackout |

Grade thresholds:

| Grade | Score | Extra requirements |
|-------|-------|--------------------|
| **A+** | >= 90 | All per-reviewer minimums + no blockers |
| **A** | >= 80 | No hard blockers |
| **B** | >= 70 | No hard blockers |
| **C** | >= 60 | No hard blockers |
| **REJECTED** | < 60 | Or any hard blocker |

---

## Important notes

- This is a **research and paper-trading tool**. It does not guarantee profitability.
- Always run on a **demo account** first.
- Never risk more than you can afford to lose.
- Past performance of any signal does not guarantee future results.
