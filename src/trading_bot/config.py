from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - fallback used only if PyYAML missing
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'config' / 'default_settings.yaml'


@dataclass(slots=True)
class BrokerConfig:
    mode: str = 'mt5'
    trade_enabled: bool = False
    polling_interval_seconds: int = 5
    watchlist: list[str] = field(default_factory=lambda: ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'XAGUSD'])


@dataclass(slots=True)
class RiskLimitsConfig:
    max_trades_per_symbol_per_day: int = 5
    max_trades_total_per_day: int = 8
    max_trades_per_session: int = 2
    min_minutes_between_trades: int = 20
    max_open_positions_per_symbol: int = 1
    max_open_positions_total: int = 2


@dataclass(slots=True)
class ScannerConfig:
    only_a_plus: bool = True
    top_n_setups: int = 3
    require_trending_market_first: bool = True
    a_plus_min_score: float = 0.85
    a_min_score: float = 0.70
    b_min_score: float = 0.55
    c_min_score: float = 0.40


@dataclass(slots=True)
class AppConfig:
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk_limits: RiskLimitsConfig = field(default_factory=RiskLimitsConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AppConfig':
        return cls(
            broker=BrokerConfig(**data.get('broker', {})),
            risk_limits=RiskLimitsConfig(**data.get('risk_limits', {})),
            scanner=ScannerConfig(**data.get('scanner', {})),
        )


def _strip_inline_comment(line: str) -> str:
    in_quote = False
    quote_char = ''
    for index, char in enumerate(line):
        if char in {'"', "'"}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if char == '#' and not in_quote:
            return line[:index].rstrip()
    return line.rstrip()


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == '':
        return ''
    lowered = value.lower()
    if lowered in {'true', 'false'}:
        return lowered == 'true'
    if lowered in {'null', 'none'}:
        return None
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if ',' in value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return value


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    raw_lines = []
    for original in text.splitlines():
        cleaned = _strip_inline_comment(original)
        if cleaned.strip():
            raw_lines.append(cleaned)

    def parse_dict(start: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        index = start
        while index < len(raw_lines):
            line = raw_lines[index]
            current_indent = len(line) - len(line.lstrip(' '))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f'Invalid indentation near: {line}')
            stripped = line.strip()
            if stripped.startswith('- '):
                raise ValueError('Unexpected list item in mapping context')
            key, _, remainder = stripped.partition(':')
            if not remainder.strip():
                next_index = index + 1
                if next_index >= len(raw_lines):
                    result[key] = {}
                    index += 1
                    continue
                next_line = raw_lines[next_index]
                next_indent = len(next_line) - len(next_line.lstrip(' '))
                if next_indent <= current_indent:
                    result[key] = {}
                    index += 1
                elif next_line.strip().startswith('- '):
                    parsed, index = parse_list(next_index, next_indent)
                    result[key] = parsed
                else:
                    parsed, index = parse_dict(next_index, next_indent)
                    result[key] = parsed
            else:
                result[key] = _parse_scalar(remainder.strip())
                index += 1
        return result, index

    def parse_list(start: int, indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        index = start
        while index < len(raw_lines):
            line = raw_lines[index]
            current_indent = len(line) - len(line.lstrip(' '))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f'Invalid indentation near: {line}')
            stripped = line.strip()
            if not stripped.startswith('- '):
                break
            items.append(_parse_scalar(stripped[2:].strip()))
            index += 1
        return items, index

    parsed, _ = parse_dict(0, 0)
    return parsed


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_value(value: str) -> Any:
    if ',' in value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return _parse_scalar(value)


def _apply_env_overrides(config: dict[str, Any], prefix: str = 'TRADING_BOT') -> dict[str, Any]:
    merged = dict(config)
    marker = f'{prefix}__'
    for key, value in os.environ.items():
        if not key.startswith(marker):
            continue
        path = key[len(marker):].lower().split('__')
        cursor = merged
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = _env_value(value)
    return merged


def load_config(path: str | os.PathLike[str] | None = None, env_prefix: str = 'TRADING_BOT') -> dict[str, Any]:
    config_path = Path(path or os.environ.get(f'{env_prefix}_CONFIG', DEFAULT_CONFIG_PATH)).expanduser()
    text = config_path.read_text(encoding='utf-8')
    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
    else:  # pragma: no cover - only used if PyYAML unavailable
        loaded = _minimal_yaml_load(text)
    return _apply_env_overrides(loaded, env_prefix)


def load_settings(path: str | os.PathLike[str] | None = None, env_prefix: str = 'TRADING_BOT') -> AppConfig:
    return AppConfig.from_dict(load_config(path=path, env_prefix=env_prefix))
