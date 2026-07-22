"""Persistent OI snapshot loading and serialization."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.binance import is_valid_binance_symbol
from shared.utils import optional_float, write_text_atomic


MAX_SNAPSHOT_FILE_BYTES = 5 * 1024 * 1024


@dataclass(slots=True)
class LoadedSnapshot:
    snapshot: dict[str, dict[str, Any]] = field(default_factory=dict)
    known_symbols: set[str] = field(default_factory=set)
    update_times: dict[str, float] = field(default_factory=dict)


def load_snapshot_file(
    path: Path,
    *,
    max_age_seconds: float,
    clock_skew_seconds: float,
    wall_time: float | None = None,
    monotonic_time: float | None = None,
) -> LoadedSnapshot:
    """Load valid recent baselines while retaining the last known symbol set."""
    if not path.exists():
        return LoadedSnapshot()

    payload = json.loads(_read_snapshot_text(path))
    if not isinstance(payload, dict):
        return LoadedSnapshot()

    known_symbols = _valid_symbols(payload.get("symbols"))
    raw_snapshot = payload.get("snapshot")
    if not isinstance(raw_snapshot, dict):
        return LoadedSnapshot(known_symbols=known_symbols)

    current_wall_time = time.time() if wall_time is None else wall_time
    current_monotonic_time = (
        time.monotonic() if monotonic_time is None else monotonic_time
    )
    snapshot = {}
    update_times = {}

    for symbol, item in raw_snapshot.items():
        if not is_valid_binance_symbol(symbol) or not isinstance(item, dict):
            continue

        oi = optional_float(item.get("oi"))
        if oi is None or oi < 0:
            continue
        known_symbols.add(symbol)

        age = snapshot_age_seconds(item, current_wall_time)
        if (
            age is None
            or age < -clock_skew_seconds
            or age > max_age_seconds
        ):
            continue

        updated_at = item.get("updated_at")
        snapshot[symbol] = {
            "oi": oi,
            "updated_at": updated_at,
        }
        update_times[symbol] = current_monotonic_time - max(age, 0)

    return LoadedSnapshot(
        snapshot=snapshot,
        known_symbols=known_symbols,
        update_times=update_times,
    )


def write_snapshot_file(
    path: Path,
    *,
    snapshot: dict[str, dict[str, Any]],
    symbols: set[str] | list[str],
    saved_at: str,
) -> None:
    """Atomically serialize the stable on-disk snapshot format."""
    payload = {
        "saved_at": saved_at,
        "symbols": sorted(symbols),
        "snapshot": snapshot,
    }
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_SNAPSHOT_FILE_BYTES:
        raise ValueError(
            f"OI snapshot exceeds {MAX_SNAPSHOT_FILE_BYTES} bytes"
        )
    write_text_atomic(path, text)


def snapshot_age_seconds(item: dict[str, Any], now: float | None = None) -> float | None:
    updated_at = item.get("updated_at")
    if not isinstance(updated_at, str):
        return None
    try:
        updated_datetime = datetime.fromisoformat(updated_at)
        if updated_datetime.tzinfo is None:
            return None
        updated_timestamp = updated_datetime.timestamp()
    except (OSError, ValueError, OverflowError):
        return None

    current_timestamp = time.time() if now is None else now
    return current_timestamp - updated_timestamp


def _valid_symbols(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {symbol for symbol in value if is_valid_binance_symbol(symbol)}


def _read_snapshot_text(path: Path) -> str:
    with path.open("rb") as file:
        raw_payload = file.read(MAX_SNAPSHOT_FILE_BYTES + 1)
    if len(raw_payload) > MAX_SNAPSHOT_FILE_BYTES:
        raise ValueError(
            f"OI snapshot exceeds {MAX_SNAPSHOT_FILE_BYTES} bytes"
        )
    return raw_payload.decode("utf-8")
