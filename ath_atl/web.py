import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from .config import (
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        ROOT_DIR,
    )
    from .files import write_json
    from .models import MARKETS
    from .web_data import load_breakouts, load_records, load_status
    from .web_scanner import BackgroundScanner
    from .web_status import default_status
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from ath_atl.config import (
        DEFAULT_BREAKOUTS_PATH,
        DEFAULT_DB_PATH,
        DEFAULT_SNAPSHOT_PATH,
        DEFAULT_STATUS_PATH,
        ROOT_DIR,
    )
    from ath_atl.files import write_json
    from ath_atl.models import MARKETS
    from ath_atl.web_data import load_breakouts, load_records, load_status
    from ath_atl.web_scanner import BackgroundScanner
    from ath_atl.web_status import default_status


TEMPLATE_PATH = ROOT_DIR / "templates" / "index.html"
STATIC_DIR = ROOT_DIR / "static"


class ATHATLHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH
    breakouts_path = DEFAULT_BREAKOUTS_PATH
    status_path = DEFAULT_STATUS_PATH
    scanner = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            return self.send_file(TEMPLATE_PATH, "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self.send_static(path)
        if path == "/api/ath-atl":
            params = parse_qs(parsed.query)
            return self.send_json({"records": load_records(self.db_path, params)})
        if path == "/api/breakouts":
            return self.send_json(load_breakouts(self.breakouts_path, self.db_path))
        if path == "/api/status":
            return self.send_json(load_status(self.status_path, self.scanner))

        self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        return

    def send_static(self, request_path):
        relative_path = request_path.removeprefix("/static/")
        file_path = (STATIC_DIR / relative_path).resolve()
        static_root = STATIC_DIR.resolve()

        if not str(file_path).startswith(str(static_root) + "/"):
            self.send_error(404, "Not found")
            return

        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"

        self.send_file(file_path, content_type)

    def send_file(self, path, content_type):
        path = Path(path)
        if not path.exists() or not path.is_file():
            self.send_error(404, "Not found")
            return

        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Serve ATH/ATL records and daily breakouts")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8788, help="bind port")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--breakouts-path", default=str(DEFAULT_BREAKOUTS_PATH), help="daily breakouts JSON path")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="ATH/ATL snapshot JSON path")
    parser.add_argument("--status-path", default=str(DEFAULT_STATUS_PATH), help="scan status JSON path")
    parser.add_argument(
        "--market-types",
        nargs="+",
        choices=sorted(MARKETS),
        default=["spot", "futures"],
        help="markets to scan in the background, default: spot futures",
    )
    parser.add_argument("--symbols", help="comma-separated symbols for targeted background scans")
    parser.add_argument("--max-symbols", type=int, help="limit symbols per market for testing")
    parser.add_argument("--request-delay", type=float, default=0.05, help="seconds between paginated kline requests")
    parser.add_argument("--retry-attempts", type=int, default=4, help="request retry attempts, default: 4")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="seconds multiplied by retry count")
    parser.add_argument("--request-timeout", type=float, default=20, help="request timeout seconds")
    parser.add_argument("--kline-limit", type=int, default=1000, help="Binance kline page size")
    parser.add_argument("--scan-workers", type=int, default=2, help="parallel symbols to scan, default: 2")
    parser.add_argument("--scan-interval-hours", type=float, default=4.0, help="background scan interval")
    parser.add_argument("--no-auto-scan", action="store_true", help="serve pages without starting background scans")
    return parser.parse_args()


def main():
    args = parse_args()
    handler = ATHATLHandler
    handler.db_path = Path(args.db_path)
    handler.breakouts_path = Path(args.breakouts_path)
    handler.status_path = Path(args.status_path)

    scanner = None
    if not args.no_auto_scan:
        symbols = args.symbols.split(",") if args.symbols else None
        scanner = BackgroundScanner(
            db_path=args.db_path,
            breakouts_path=args.breakouts_path,
            snapshot_path=args.snapshot_path,
            status_path=args.status_path,
            market_types=args.market_types,
            symbols=symbols,
            max_symbols=args.max_symbols,
            request_delay=args.request_delay,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            request_timeout=args.request_timeout,
            kline_limit=args.kline_limit,
            scan_workers=args.scan_workers,
            interval_hours=args.scan_interval_hours,
        )
        handler.scanner = scanner
    else:
        handler.scanner = None
        write_json(args.status_path, default_status(auto_scan=False))

    server = ThreadingHTTPServer((args.host, args.port), handler)
    if scanner:
        scanner.start()
    print(f"ATH/ATL page: http://{args.host}:{args.port}/")
    if scanner:
        print("Background ATH/ATL scan: enabled")
    else:
        print("Background ATH/ATL scan: disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ATH/ATL web server")
    finally:
        if scanner:
            scanner.stop()
        server.server_close()


if __name__ == "__main__":
    main()
