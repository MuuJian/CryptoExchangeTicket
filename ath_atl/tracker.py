import argparse
from pathlib import Path

try:
    from .client import BinanceClient
    from .config import (
        DATA_DIR,
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        LOG_DIR,
    )
    from .files import write_breakouts_json, write_json, write_snapshot_json
    from .models import Kline, MARKETS, MarketConfig
    from .store import ATHATLStore
    from .time_utils import timestamp_to_date
    from .tracker_service import ATHATLTracker, new_breakout
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from ath_atl.client import BinanceClient
    from ath_atl.config import (
        DATA_DIR,
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        LOG_DIR,
    )
    from ath_atl.files import write_breakouts_json, write_json, write_snapshot_json
    from ath_atl.models import Kline, MARKETS, MarketConfig
    from ath_atl.store import ATHATLStore
    from ath_atl.time_utils import timestamp_to_date
    from ath_atl.tracker_service import ATHATLTracker, new_breakout


__all__ = [
    "ATHATLStore",
    "ATHATLTracker",
    "BinanceClient",
    "DATA_DIR",
    "DEFAULT_BREAKOUTS_PATH",
    "DEFAULT_DB_PATH",
    "DEFAULT_SNAPSHOT_PATH",
    "DEFAULT_STATUS_PATH",
    "Kline",
    "LOG_DIR",
    "MARKETS",
    "MarketConfig",
    "new_breakout",
    "timestamp_to_date",
    "write_breakouts_json",
    "write_json",
    "write_snapshot_json",
]


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
