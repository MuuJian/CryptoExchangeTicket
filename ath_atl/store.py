import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import ATH_ATL_COLUMNS, DEFAULT_DB_PATH


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
