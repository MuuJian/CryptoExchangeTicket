import argparse
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DAY_MS = 24 * 60 * 60 * 1000
DEFAULT_DB_PATH = DATA_DIR / "ath_atl.db"
DEFAULT_BREAKOUTS_PATH = DATA_DIR / "daily_breakouts.json"
DEFAULT_SNAPSHOT_PATH = DATA_DIR / "ath_atl_snapshot.json"
DEFAULT_STATUS_PATH = DATA_DIR / "scan_status.json"
ATH_ATL_COLUMNS = [
    "market_type",
    "symbol",
    "current_price",
    "ath_price",
    "atl_price",
    "first_kline_open_time",
    "last_kline_open_time",
    "updated_at",
]


@dataclass
class MarketConfig:
    market_type: str
    base_url: str
    exchange_info_path: str
    klines_path: str


@dataclass
class Kline:
    open_time: int
    date: str
    high: float
    low: float
    close: float


MARKETS = {
    "spot": MarketConfig(
        market_type="spot",
        base_url="https://api.binance.com",
        exchange_info_path="/api/v3/exchangeInfo",
        klines_path="/api/v3/klines",
    ),
    "futures": MarketConfig(
        market_type="futures",
        base_url="https://fapi.binance.com",
        exchange_info_path="/fapi/v1/exchangeInfo",
        klines_path="/fapi/v1/klines",
    ),
}


class BinanceClient:
    def __init__(self, request_delay=0.05, retry_attempts=4, retry_backoff=1.0, timeout=20):
        self.session = requests.Session()
        self.request_delay = request_delay
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff = retry_backoff
        self.timeout = timeout

    def clone(self):
        return BinanceClient(
            request_delay=self.request_delay,
            retry_attempts=self.retry_attempts,
            retry_backoff=self.retry_backoff,
            timeout=self.timeout,
        )

    def get_json(self, url, params=None):
        attempts = self.retry_attempts
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                if attempt >= attempts:
                    raise
                sleep_seconds = self.retry_sleep_seconds(attempt, exc)
                print(f"request failed {attempt}/{attempts}: {exc}; retrying in {sleep_seconds:.1f}s")
                time.sleep(sleep_seconds)

    def retry_sleep_seconds(self, attempt, exc):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in {418, 429}:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), self.retry_backoff * attempt)
                except ValueError:
                    pass
            multiplier = 20 if response.status_code == 418 else 5
            return max(5.0, self.retry_backoff * attempt * multiplier)
        return self.retry_backoff * attempt

    def get_usdt_symbols(self, market_type):
        config = MARKETS[market_type]
        data = self.get_json(f"{config.base_url}{config.exchange_info_path}")
        symbols = []

        for item in data.get("symbols", []):
            if item.get("quoteAsset") != "USDT" or item.get("status") != "TRADING":
                continue
            if market_type == "futures" and item.get("contractType") != "PERPETUAL":
                continue
            symbols.append(item["symbol"])

        return symbols

    def iter_daily_klines(self, market_type, symbol, start_time=None, limit=1000):
        config = MARKETS[market_type]
        next_start = start_time

        while True:
            params = {"symbol": symbol, "interval": "1d", "limit": limit}
            if next_start is not None:
                params["startTime"] = next_start

            rows = self.get_json(f"{config.base_url}{config.klines_path}", params=params)
            if not rows:
                break

            for row in rows:
                open_time = int(row[0])
                yield Kline(
                    open_time=open_time,
                    date=timestamp_to_date(open_time),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                )

            last_open_time = int(rows[-1][0])
            next_start = last_open_time + DAY_MS
            if len(rows) < limit:
                break
            time.sleep(self.request_delay)


class ATHATLStore:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        with self.lock:
            self.conn.execute("PRAGMA busy_timeout = 30000")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.create_ath_atl_table()
            self.migrate_schema()
            self.conn.commit()

    def create_ath_atl_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ath_atl (
                market_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                current_price REAL,
                ath_price REAL NOT NULL,
                atl_price REAL NOT NULL,
                first_kline_open_time INTEGER NOT NULL DEFAULT 0,
                last_kline_open_time INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (market_type, symbol)
            )
            """
        )

    def migrate_schema(self):
        columns = [row["name"] for row in self.conn.execute("PRAGMA table_info(ath_atl)").fetchall()]
        if columns == ATH_ATL_COLUMNS:
            return

        legacy_table = f"ath_atl_legacy_{int(time.time())}"
        self.conn.execute(f"ALTER TABLE ath_atl RENAME TO {legacy_table}")
        self.create_ath_atl_table()
        self.copy_legacy_rows(legacy_table, columns)
        self.conn.execute(f"DROP TABLE {legacy_table}")

    def copy_legacy_rows(self, legacy_table, legacy_columns):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        expressions = {
            "market_type": "market_type" if "market_type" in legacy_columns else "'unknown'",
            "symbol": "symbol",
            "current_price": "current_price" if "current_price" in legacy_columns else "NULL",
            "ath_price": "ath_price",
            "atl_price": "atl_price",
            "first_kline_open_time": (
                "COALESCE(first_kline_open_time, 0)" if "first_kline_open_time" in legacy_columns else "0"
            ),
            "last_kline_open_time": (
                "COALESCE(last_kline_open_time, 0)" if "last_kline_open_time" in legacy_columns else "0"
            ),
            "updated_at": "COALESCE(updated_at, ?)" if "updated_at" in legacy_columns else "?",
        }

        selected = ", ".join(expressions[column] for column in ATH_ATL_COLUMNS)
        self.conn.execute(
            f"""
            INSERT OR REPLACE INTO ath_atl (
                market_type, symbol, current_price, ath_price, atl_price,
                first_kline_open_time, last_kline_open_time, updated_at
            )
            SELECT {selected}
            FROM {legacy_table}
            WHERE symbol IS NOT NULL AND ath_price IS NOT NULL AND atl_price IS NOT NULL
            """,
            (now,),
        )

    def get_record(self, market_type, symbol):
        with self.lock:
            row = self.conn.execute(
                """
                SELECT
                    market_type, symbol, current_price, ath_price, atl_price,
                    first_kline_open_time, last_kline_open_time, updated_at
                FROM ath_atl
                WHERE market_type = ? AND symbol = ?
                """,
                (market_type, symbol),
            ).fetchone()
        return dict(row) if row else None

    def list_records(self):
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT
                    market_type, symbol, current_price, ath_price, atl_price,
                    first_kline_open_time, last_kline_open_time, updated_at
                FROM ath_atl
                ORDER BY market_type, symbol
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_record(
        self,
        market_type,
        symbol,
        current_price,
        ath_price,
        atl_price,
        first_kline_open_time,
        last_kline_open_time,
    ):
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO ath_atl (
                    market_type, symbol, current_price, ath_price, atl_price,
                    first_kline_open_time, last_kline_open_time, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_type, symbol) DO UPDATE SET
                    current_price = excluded.current_price,
                    ath_price = excluded.ath_price,
                    atl_price = excluded.atl_price,
                    first_kline_open_time = excluded.first_kline_open_time,
                    last_kline_open_time = excluded.last_kline_open_time,
                    updated_at = excluded.updated_at
                """,
                (
                    market_type,
                    symbol,
                    current_price,
                    ath_price,
                    atl_price,
                    first_kline_open_time,
                    last_kline_open_time,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()


class ATHATLTracker:
    def __init__(self, client=None, store=None, kline_limit=1000, scan_workers=2):
        self.client = client or BinanceClient()
        self.store = store or ATHATLStore()
        self.kline_limit = kline_limit
        self.scan_workers = max(1, int(scan_workers or 1))
        self.thread_local = threading.local()

    def scan(self, market_types, symbols=None, max_symbols=None):
        breakouts = []
        summary = {}

        for market_type in market_types:
            market_symbols = self.resolve_symbols(market_type, symbols, max_symbols)
            market_breakouts, market_summary = self.scan_market(market_type, market_symbols)
            breakouts.extend(market_breakouts)
            summary[market_type] = market_summary

        return breakouts, summary

    def scan_market(self, market_type, market_symbols):
        breakouts = []
        summary = {
            "symbols": len(market_symbols),
            "processed": 0,
            "breakouts": 0,
            "errors": 0,
            "failed_symbols": [],
        }

        if self.scan_workers <= 1 or len(market_symbols) <= 1:
            for index, symbol in enumerate(market_symbols, 1):
                self.scan_one_symbol(market_type, symbol, breakouts, summary)
                self.print_progress(market_type, index, len(market_symbols))
            return breakouts, summary

        max_workers = min(self.scan_workers, len(market_symbols))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.scan_symbol, market_type, symbol): symbol for symbol in market_symbols}
            for index, future in enumerate(as_completed(futures), 1):
                symbol = futures[future]
                try:
                    symbol_breakouts = future.result()
                except Exception as exc:
                    self.record_symbol_error(market_type, symbol, exc, summary)
                else:
                    self.record_symbol_success(symbol_breakouts, breakouts, summary)
                self.print_progress(market_type, index, len(market_symbols))

        return breakouts, summary

    def scan_one_symbol(self, market_type, symbol, breakouts, summary):
        try:
            symbol_breakouts = self.scan_symbol(market_type, symbol)
        except Exception as exc:
            self.record_symbol_error(market_type, symbol, exc, summary)
        else:
            self.record_symbol_success(symbol_breakouts, breakouts, summary)

    def record_symbol_success(self, symbol_breakouts, breakouts, summary):
        breakouts.extend(symbol_breakouts)
        summary["processed"] += 1
        summary["breakouts"] += len(symbol_breakouts)

    def record_symbol_error(self, market_type, symbol, exc, summary):
        summary["errors"] += 1
        error = str(exc)
        already_saved = any(item["symbol"] == symbol and item["error"] == error for item in summary["failed_symbols"])
        if not already_saved and len(summary["failed_symbols"]) < 20:
            summary["failed_symbols"].append({"symbol": symbol, "error": error})
        print(f"{market_type} {symbol} failed: {exc}")

    def print_progress(self, market_type, index, total):
        if index % 50 == 0 or index == total:
            print(f"{market_type}: {index}/{total} symbols scanned")

    def resolve_symbols(self, market_type, symbols, max_symbols):
        if symbols:
            market_symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        else:
            market_symbols = self.client.get_usdt_symbols(market_type)

        market_symbols = list(dict.fromkeys(market_symbols))

        if max_symbols is not None:
            market_symbols = market_symbols[:max_symbols]

        return market_symbols

    def scan_symbol(self, market_type, symbol):
        record = self.store.get_record(market_type, symbol)
        start_time = self.start_time_for(record)
        klines = list(
            self.worker_client().iter_daily_klines(
                market_type,
                symbol,
                start_time=start_time,
                limit=self.kline_limit,
            )
        )
        if not klines:
            return []

        if record:
            ath_price = float(record["ath_price"])
            atl_price = float(record["atl_price"])
            first_kline_open_time = int(record.get("first_kline_open_time") or 0)
            emit_breakouts = True
        else:
            first = klines[0]
            ath_price = first.high
            atl_price = first.low
            first_kline_open_time = first.open_time
            emit_breakouts = False

        breakouts = []
        current_price = klines[-1].close
        last_kline_open_time = record["last_kline_open_time"] if record else 0

        for kline in klines:
            if not first_kline_open_time or kline.open_time < first_kline_open_time:
                first_kline_open_time = kline.open_time

            if emit_breakouts and kline.high > ath_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_high", kline.high, ath_price))
                ath_price = kline.high
            elif kline.high > ath_price:
                ath_price = kline.high

            if emit_breakouts and kline.low < atl_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_low", kline.low, atl_price))
                atl_price = kline.low
            elif kline.low < atl_price:
                atl_price = kline.low

            last_kline_open_time = max(last_kline_open_time, kline.open_time)

        self.store.upsert_record(
            market_type=market_type,
            symbol=symbol,
            current_price=current_price,
            ath_price=ath_price,
            atl_price=atl_price,
            first_kline_open_time=first_kline_open_time,
            last_kline_open_time=last_kline_open_time,
        )
        return breakouts

    def start_time_for(self, record):
        if not record:
            return 0
        if not int(record.get("first_kline_open_time") or 0):
            return 0
        return max(0, int(record["last_kline_open_time"]) - DAY_MS)

    def worker_client(self):
        if self.scan_workers <= 1:
            return self.client

        client = getattr(self.thread_local, "client", None)
        if client is None:
            client = self.client.clone()
            self.thread_local.client = client
        return client


def new_breakout(kline, market_type, symbol, breakout_type, price, previous_price):
    return {
        "date": kline.date,
        "market_type": market_type,
        "symbol": symbol,
        "breakout_type": breakout_type,
        "price": price,
        "previous_price": previous_price,
    }


def timestamp_to_date(timestamp_ms):
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date().isoformat()


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_breakouts_json(path, breakouts, summary):
    return write_json(
        path,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "date": datetime.now(timezone.utc).date().isoformat(),
            "summary": summary,
            "breakouts": breakouts,
        },
    )


def write_snapshot_json(path, records):
    return write_json(
        path,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": records,
        },
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Track Binance USDT ATH/ATL values and daily breakouts")
    parser.add_argument(
        "--market-types",
        nargs="+",
        choices=sorted(MARKETS),
        default=["spot", "futures"],
        help="markets to scan, default: spot futures",
    )
    parser.add_argument("--symbols", help="comma-separated symbols for targeted runs, e.g. BTCUSDT,ETHUSDT")
    parser.add_argument("--max-symbols", type=int, help="limit symbols per market for testing")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--breakouts-output", default=str(DEFAULT_BREAKOUTS_PATH), help="daily breakouts JSON path")
    parser.add_argument("--snapshot-output", default=str(DEFAULT_SNAPSHOT_PATH), help="ATH/ATL snapshot JSON path")
    parser.add_argument("--request-delay", type=float, default=0.05, help="seconds between paginated kline requests")
    parser.add_argument("--retry-attempts", type=int, default=4, help="request retry attempts, default: 4")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="seconds multiplied by retry count")
    parser.add_argument("--request-timeout", type=float, default=20, help="request timeout seconds")
    parser.add_argument("--kline-limit", type=int, default=1000, help="Binance kline page size")
    parser.add_argument("--scan-workers", type=int, default=2, help="parallel symbols to scan, default: 2")
    return parser.parse_args()


def main():
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    symbols = args.symbols.split(",") if args.symbols else None
    store = ATHATLStore(args.db_path)
    client = BinanceClient(
        request_delay=args.request_delay,
        retry_attempts=args.retry_attempts,
        retry_backoff=args.retry_backoff,
        timeout=args.request_timeout,
    )
    tracker = ATHATLTracker(client=client, store=store, kline_limit=args.kline_limit, scan_workers=args.scan_workers)

    try:
        breakouts, summary = tracker.scan(
            market_types=args.market_types,
            symbols=symbols,
            max_symbols=args.max_symbols,
        )
        breakouts_path = write_breakouts_json(args.breakouts_output, breakouts, summary)
        snapshot_path = write_snapshot_json(args.snapshot_output, store.list_records())
        print(f"Saved {len(breakouts)} breakouts to {breakouts_path}")
        print(f"Saved ATH/ATL snapshot to {snapshot_path}")
        print(f"SQLite database: {store.db_path}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
