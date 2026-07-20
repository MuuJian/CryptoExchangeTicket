"""Local HTTP server and command-line entry for the realtime OI dashboard."""

from __future__ import annotations

import argparse
import sys
import threading
from http.server import ThreadingHTTPServer
from math import isfinite
from pathlib import Path
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realtime_oi_dashboard.poller import OIPoller, timestamp
from shared.web import DashboardRequestHandler


ROOT_DIR = Path(__file__).resolve().parent
INDEX_FILE = ROOT_DIR / "index.html"
STATIC_DIR = ROOT_DIR / "static"
HOST = "127.0.0.1"
PORT = 8777


class DashboardHandler(DashboardRequestHandler):
    poller = None
    index_file = INDEX_FILE
    static_dir = STATIC_DIR

    def do_GET(self):
        parsed = urlparse(self.path)
        if self.send_dashboard_asset(parsed.path):
            return
        if parsed.path == "/api/oi":
            self.send_json(self.poller.get_state())
            return
        self.send_error(404)


def positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def port_number(value):
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return parsed


def positive_float(value):
    parsed = float(value)
    if not isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_float(value):
    parsed = float(value)
    if not isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return parsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Realtime price + batched OI dashboard")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=port_number, default=PORT)
    parser.add_argument("--oi-batch-size", type=positive_int, default=25, help="symbols per batch")
    parser.add_argument(
        "--oi-batch-delay",
        type=positive_float,
        default=1.0,
        help="seconds between batches",
    )
    parser.add_argument("--oi-workers", type=positive_int, default=3, help="parallel OI requests")
    parser.add_argument(
        "--oi-history-cache-seconds",
        "--oi-24h-cache-seconds",
        dest="oi_history_cache_seconds",
        type=non_negative_float,
        default=300,
        help="seconds to cache 24h/7d OI baselines; 0 disables the cache",
    )
    parser.add_argument(
        "--ticker-cache-seconds",
        type=non_negative_float,
        default=10,
        help="seconds to cache futures 24h ticker",
    )
    parser.add_argument(
        "--funding-cache-seconds",
        type=non_negative_float,
        default=3600,
        help="fallback funding-rate cache duration",
    )
    parser.add_argument(
        "--snapshot-save-interval",
        type=non_negative_float,
        default=10,
        help="seconds between atomic snapshot writes; 0 writes every batch",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    poller = OIPoller(
        batch_size=args.oi_batch_size,
        batch_delay=args.oi_batch_delay,
        oi_workers=args.oi_workers,
        oi_history_cache_seconds=args.oi_history_cache_seconds,
        ticker_cache_seconds=args.ticker_cache_seconds,
        funding_cache_seconds=args.funding_cache_seconds,
        snapshot_save_interval=args.snapshot_save_interval,
    )
    DashboardHandler.poller = poller

    try:
        server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    except OSError as exc:
        print(f"无法启动面板: {exc}")
        return 1
    thread = threading.Thread(target=poller.run_forever, name="oi-poller", daemon=True)
    thread.start()

    print(f"Dashboard running at http://{args.host}:{args.port}")
    print("Price uses Binance futures WebSocket in the browser.")
    print(
        f"OI updates {args.oi_batch_size} symbols every {args.oi_batch_delay} seconds "
        f"with {args.oi_workers} workers."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        poller.stop()
        thread.join(timeout=15)
        if thread.is_alive():
            print(f"{timestamp()} OI poller did not stop within 15 seconds")
        try:
            poller.save_state(force=True)
        except (OSError, TypeError, ValueError) as exc:
            print(f"{timestamp()} failed to save final OI snapshot: {exc}")
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
