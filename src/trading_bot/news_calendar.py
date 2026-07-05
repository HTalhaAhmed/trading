from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_news_calendar(path: str | Path) -> pd.DataFrame:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    events = payload.get("events", [])
    if not events:
        return pd.DataFrame(columns=["timestamp", "impact", "title"]).set_index("timestamp")

    df = pd.DataFrame(events)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").set_index("timestamp")


def is_in_news_blackout(
    ts: pd.Timestamp,
    news_df: pd.DataFrame,
    pre_minutes: int,
    post_minutes: int,
    impacts: set[str] | None = None,
) -> bool:
    if news_df.empty:
        return False

    if impacts:
        filtered = news_df[news_df["impact"].str.lower().isin({i.lower() for i in impacts})]
    else:
        filtered = news_df

    if filtered.empty:
        return False

    start = ts - pd.Timedelta(minutes=pre_minutes)
    end = ts + pd.Timedelta(minutes=post_minutes)
    return not filtered.loc[start:end].empty
