import argparse
import json
import sqlite3
import time
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
    def __init__(self, request_delay=0.05):
        self.session = requests.Session()
        self.request_delay = request_delay

    def get_usdt_symbols(self, market_type):
        config = MARKETS[market_type]
        resp = self.session.get(f"{config.base_url}{config.exchange_info_path}", timeout=15)
        resp.raise_for_status()
        data = resp.json()
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

            resp = self.session.get(f"{config.base_url}{config.klines_path}", params=params, timeout=15)
            resp.raise_for_status()
            rows = resp.json()
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
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ath_atl (
                market_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                current_price REAL,
                ath_price REAL NOT NULL,
                atl_price REAL NOT NULL,
                ath_date TEXT,
                atl_date TEXT,
                first_kline_open_time INTEGER NOT NULL DEFAULT 0,
                first_kline_date TEXT,
                last_kline_open_time INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (market_type, symbol)
            )
            """
        )
        self.ensure_columns()
        self.conn.commit()

    def ensure_columns(self):
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(ath_atl)").fetchall()}
        if "current_price" not in columns:
            self.add_column_if_missing("current_price", "ALTER TABLE ath_atl ADD COLUMN current_price REAL")
        if "first_kline_open_time" not in columns:
            self.add_column_if_missing(
                "first_kline_open_time",
                "ALTER TABLE ath_atl ADD COLUMN first_kline_open_time INTEGER NOT NULL DEFAULT 0",
            )
        if "first_kline_date" not in columns:
            self.add_column_if_missing("first_kline_date", "ALTER TABLE ath_atl ADD COLUMN first_kline_date TEXT")

    def add_column_if_missing(self, column_name, sql):
        try:
            self.conn.execute(sql)
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise

    def get_record(self, market_type, symbol):
        row = self.conn.execute(
            """
            SELECT
                market_type, symbol, current_price, ath_price, atl_price, ath_date, atl_date,
                first_kline_open_time, first_kline_date, last_kline_open_time, updated_at
            FROM ath_atl
            WHERE market_type = ? AND symbol = ?
            """,
            (market_type, symbol),
        ).fetchone()
        return dict(row) if row else None

    def list_records(self):
        rows = self.conn.execute(
            """
            SELECT
                market_type, symbol, current_price, ath_price, atl_price, ath_date, atl_date,
                first_kline_open_time, first_kline_date, last_kline_open_time, updated_at
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
        ath_date,
        atl_date,
        first_kline_open_time,
        first_kline_date,
        last_kline_open_time,
    ):
        self.conn.execute(
            """
            INSERT INTO ath_atl (
                market_type, symbol, current_price, ath_price, atl_price, ath_date, atl_date,
                first_kline_open_time, first_kline_date, last_kline_open_time, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_type, symbol) DO UPDATE SET
                current_price = excluded.current_price,
                ath_price = excluded.ath_price,
                atl_price = excluded.atl_price,
                ath_date = excluded.ath_date,
                atl_date = excluded.atl_date,
                first_kline_open_time = excluded.first_kline_open_time,
                first_kline_date = excluded.first_kline_date,
                last_kline_open_time = excluded.last_kline_open_time,
                updated_at = excluded.updated_at
            """,
            (
                market_type,
                symbol,
                current_price,
                ath_price,
                atl_price,
                ath_date,
                atl_date,
                first_kline_open_time,
                first_kline_date,
                last_kline_open_time,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


class ATHATLTracker:
    def __init__(self, client=None, store=None, kline_limit=1000):
        self.client = client or BinanceClient()
        self.store = store or ATHATLStore()
        self.kline_limit = kline_limit

    def scan(self, market_types, symbols=None, max_symbols=None):
        breakouts = []
        summary = {}

        for market_type in market_types:
            market_symbols = self.resolve_symbols(market_type, symbols, max_symbols)
            summary[market_type] = {"symbols": len(market_symbols), "processed": 0, "breakouts": 0}

            for index, symbol in enumerate(market_symbols, 1):
                symbol_breakouts = self.scan_symbol(market_type, symbol)
                breakouts.extend(symbol_breakouts)
                summary[market_type]["processed"] += 1
                summary[market_type]["breakouts"] += len(symbol_breakouts)

                if index % 50 == 0:
                    print(f"{market_type}: {index}/{len(market_symbols)} symbols processed")

        return breakouts, summary

    def resolve_symbols(self, market_type, symbols, max_symbols):
        if symbols:
            market_symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        else:
            market_symbols = self.client.get_usdt_symbols(market_type)

        if max_symbols is not None:
            market_symbols = market_symbols[:max_symbols]

        return market_symbols

    def scan_symbol(self, market_type, symbol):
        record = self.store.get_record(market_type, symbol)
        start_time = self.start_time_for(record)
        klines = list(self.client.iter_daily_klines(market_type, symbol, start_time=start_time, limit=self.kline_limit))
        if not klines:
            return []

        if record:
            ath_price = float(record["ath_price"])
            atl_price = float(record["atl_price"])
            ath_date = record["ath_date"]
            atl_date = record["atl_date"]
            first_kline_open_time = int(record.get("first_kline_open_time") or 0)
            first_kline_date = record.get("first_kline_date")
            emit_breakouts = True
        else:
            first = klines[0]
            ath_price = first.high
            atl_price = first.low
            ath_date = first.date
            atl_date = first.date
            first_kline_open_time = first.open_time
            first_kline_date = first.date
            emit_breakouts = False

        breakouts = []
        current_price = klines[-1].close
        last_kline_open_time = record["last_kline_open_time"] if record else 0

        for kline in klines:
            if not first_kline_open_time or kline.open_time < first_kline_open_time:
                first_kline_open_time = kline.open_time
                first_kline_date = kline.date

            if emit_breakouts and kline.high > ath_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_high", kline.high, ath_price))
                ath_price = kline.high
                ath_date = kline.date
            elif kline.high > ath_price:
                ath_price = kline.high
                ath_date = kline.date

            if emit_breakouts and kline.low < atl_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_low", kline.low, atl_price))
                atl_price = kline.low
                atl_date = kline.date
            elif kline.low < atl_price:
                atl_price = kline.low
                atl_date = kline.date

            last_kline_open_time = max(last_kline_open_time, kline.open_time)

        self.store.upsert_record(
            market_type=market_type,
            symbol=symbol,
            current_price=current_price,
            ath_price=ath_price,
            atl_price=atl_price,
            ath_date=ath_date,
            atl_date=atl_date,
            first_kline_open_time=first_kline_open_time,
            first_kline_date=first_kline_date,
            last_kline_open_time=last_kline_open_time,
        )
        return breakouts

    def start_time_for(self, record):
        if not record:
            return 0
        if not int(record.get("first_kline_open_time") or 0):
            return 0
        return max(0, int(record["last_kline_open_time"]) - DAY_MS)


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
    parser.add_argument("--kline-limit", type=int, default=1000, help="Binance kline page size")
    return parser.parse_args()


def main():
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    symbols = args.symbols.split(",") if args.symbols else None
    store = ATHATLStore(args.db_path)
    client = BinanceClient(request_delay=args.request_delay)
    tracker = ATHATLTracker(client=client, store=store, kline_limit=args.kline_limit)

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
