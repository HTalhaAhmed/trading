from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings(path: str | Path) -> dict[str, Any]:
    settings = load_yaml(path)
    for key in ("project", "risk", "strategy"):
        if key not in settings:
            raise ValueError(f"Missing required settings section: {key}")
    return settings
