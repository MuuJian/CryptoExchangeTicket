import json
from pathlib import Path

from .store import ATHATLStore
from .time_utils import today_utc
from .web_status import default_status


def load_records(db_path, params=None):
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    store = ATHATLStore(db_path)
    try:
        records = store.list_records()
    finally:
        store.close()

    params = params or {}
    market = first_param(params, "market_type")
    symbol = first_param(params, "symbol")

    if market:
        records = [row for row in records if row["market_type"] == market]
    if symbol:
        symbol = symbol.upper()
        records = [row for row in records if symbol in row["symbol"]]

    return dedupe_records_by_symbol(records)


def dedupe_records_by_symbol(records):
    selected = {}
    for row in records:
        symbol = row["symbol"]
        current = selected.get(symbol)
        if current is None or record_sort_key(row) < record_sort_key(current):
            selected[symbol] = normalized_record(row)
    return sorted(selected.values(), key=lambda item: item["symbol"])


def normalized_record(row):
    return dict(row)


def record_sort_key(row):
    first_open_time = int(row.get("first_kline_open_time") or 0)
    if first_open_time > 0:
        start_key = first_open_time
    else:
        start_key = 9999999999999

    # If the historical start is identical, prefer spot for a stable display.
    market_priority = 0 if row.get("market_type") == "spot" else 1
    return (start_key, market_priority)


def load_breakouts(path, db_path=None):
    path = Path(path)
    if not path.exists():
        return {"generated_at": None, "date": None, "summary": {}, "breakouts": []}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"generated_at": None, "date": None, "summary": {}, "breakouts": []}

    if payload.get("date") != today_utc():
        return {
            "generated_at": payload.get("generated_at"),
            "date": payload.get("date"),
            "summary": {},
            "all_breakouts_count": 0,
            "breakouts": [],
        }

    breakouts = dedupe_breakouts(payload.get("breakouts", []), db_path)
    payload["all_breakouts_count"] = len(breakouts)
    payload["breakouts"] = filter_today_breakouts(breakouts)
    return payload


def filter_today_breakouts(breakouts):
    today = today_utc()
    return [row for row in breakouts if row.get("date") == today]


def dedupe_breakouts(breakouts, db_path=None):
    preferred_market = {}
    if db_path:
        preferred_market = {row["symbol"]: row.get("market_type") for row in load_records(db_path)}

    selected = {}
    for row in breakouts:
        key = (row.get("date"), row.get("symbol"), row.get("breakout_type"))
        current = selected.get(key)
        if current is None:
            selected[key] = row
            continue

        symbol = row.get("symbol")
        market = preferred_market.get(symbol)
        if market and row.get("market_type") == market and current.get("market_type") != market:
            selected[key] = row

    return sorted(
        selected.values(),
        key=lambda item: (item.get("date") or "", item.get("symbol") or "", item.get("breakout_type") or ""),
        reverse=True,
    )


def load_status(path, scanner=None):
    if scanner is not None:
        return scanner.get_status()

    path = Path(path)
    if not path.exists():
        return default_status(auto_scan=False)

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        status = default_status(auto_scan=False)
        status["error"] = "scan_status.json is not valid JSON"
        return status


def first_param(params, key):
    values = params.get(key) or []
    return values[0] if values else None
