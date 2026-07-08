import argparse
import errno
import json
import mimetypes
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import requests


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(ROOT_DIR, "index.html")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
HOST = "127.0.0.1"
PORT = 8788


class IndexConstituentsScanner:
    def __init__(self, workers=12):
        self.workers = workers
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.constituents_url = f"{self.base_url}/fapi/v1/constituents"
        self.thread_local = threading.local()
        self.lock = threading.RLock()
        self.scan_thread = None
        self.state = self.empty_state()

    def empty_state(self):
        return {
            "scan_status": "idle",
            "scan_started_at": None,
            "scanned_at": None,
            "duration_seconds": 0,
            "total_symbols": 0,
            "scanned_symbols": 0,
            "symbols_with_constituents": 0,
            "rows": [],
            "error_count": 0,
            "errors": [],
        }

    def request_json(self, url, params=None, timeout=8, attempts=2):
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session_for_thread().get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                time.sleep(self.retry_delay(attempt, exc))
        raise last_exc

    def session_for_thread(self):
        session = getattr(self.thread_local, "session", None)
        if session is None:
            session = requests.Session()
            self.thread_local.session = session
        return session

    def retry_delay(self, attempt, exc):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in {418, 429}:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 2.0 * attempt)
                except ValueError:
                    pass
            return 10.0 * attempt
        return 0.6 * attempt

    def get_active_symbols(self):
        data = self.request_json(self.info_url, timeout=12)
        return [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
        ]

    def get_state(self, refresh=False):
        if refresh:
            self.start_scan()

        with self.lock:
            return json.loads(json.dumps(self.state))

    def start_scan(self):
        with self.lock:
            if self.scan_thread and self.scan_thread.is_alive():
                return

            self.state = self.empty_state()
            self.state["scan_status"] = "running"
            self.state["scan_started_at"] = datetime.now().isoformat(timespec="seconds")

            thread = threading.Thread(target=self.scan_forever_once, daemon=True)
            self.scan_thread = thread
            thread.start()

    def scan_forever_once(self):
        started_at = time.time()
        rows = []
        errors = []

        try:
            symbols = self.get_active_symbols()
        except Exception as exc:
            with self.lock:
                self.state["scan_status"] = "error"
                self.state["scanned_at"] = datetime.now().isoformat(timespec="seconds")
                self.state["duration_seconds"] = round(time.time() - started_at, 2)
                self.state["error_count"] = 1
                self.state["errors"] = [{"symbol": "exchangeInfo", "error": str(exc)}]
            return

        with self.lock:
            self.state["total_symbols"] = len(symbols)

        if symbols:
            max_workers = max(1, min(self.workers, len(symbols)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.fetch_symbol_constituents, symbol): symbol
                    for symbol in symbols
                }
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        rows.extend(future.result())
                    except Exception as exc:
                        errors.append({"symbol": symbol, "error": str(exc)})

                    self.publish_progress(started_at, rows, errors)

        with self.lock:
            self.state["scan_status"] = "complete"
            self.state["scanned_at"] = datetime.now().isoformat(timespec="seconds")
            self.state["duration_seconds"] = round(time.time() - started_at, 2)
            self.state["rows"] = sorted_constituent_rows(rows)
            self.state["symbols_with_constituents"] = len({item["symbol"] for item in rows})
            self.state["error_count"] = len(errors)
            self.state["errors"] = errors[:80]

    def publish_progress(self, started_at, rows, errors):
        with self.lock:
            self.state["scanned_symbols"] += 1
            self.state["duration_seconds"] = round(time.time() - started_at, 2)
            self.state["rows"] = sorted_constituent_rows(rows)
            self.state["symbols_with_constituents"] = len({item["symbol"] for item in rows})
            self.state["error_count"] = len(errors)
            self.state["errors"] = errors[:80]

    def fetch_symbol_constituents(self, symbol):
        payload = self.request_json(
            self.constituents_url,
            params={"symbol": symbol},
            timeout=8,
            attempts=2,
        )
        if not isinstance(payload, dict):
            return []

        payload_symbol = payload.get("symbol") or symbol
        payload_time = parse_optional_int(payload.get("time"))
        rows = []
        for item in payload.get("constituents", []) or []:
            weight = parse_optional_float(item.get("weight"))
            rows.append(
                {
                    "symbol": payload_symbol,
                    "exchange": item.get("exchange") or "",
                    "constituentSymbol": item.get("symbol") or "",
                    "price": parse_optional_float(item.get("price")),
                    "weight": weight,
                    "weightPercent": weight * 100 if weight is not None else None,
                    "time": payload_time,
                }
            )
        return rows


def sorted_constituent_rows(rows):
    return sorted(
        rows,
        key=lambda item: (
            item.get("symbol") or "",
            item.get("exchange") or "",
            item.get("constituentSymbol") or "",
        ),
    )


def parse_optional_float(value, multiplier=1):
    if value is None:
        return None
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return None


def parse_optional_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class IndexConstituentsHandler(BaseHTTPRequestHandler):
    scanner = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            return self.send_file(INDEX_FILE, "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self.send_static(path)
        if path == "/api/index-constituents":
            query = parse_qs(parsed.query)
            refresh = (query.get("refresh") or ["0"])[0].lower() in {"1", "true", "yes"}
            return self.send_json(self.scanner.get_state(refresh=refresh))
        self.send_error(404)

    def send_static(self, request_path):
        relative_path = request_path.removeprefix("/static/")
        file_path = os.path.abspath(os.path.join(STATIC_DIR, relative_path))
        static_root = os.path.abspath(STATIC_DIR)

        if not file_path.startswith(static_root + os.sep):
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        if file_path.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"

        self.send_file(file_path, content_type)

    def send_file(self, path, content_type):
        if not os.path.exists(path):
            self.send_error(404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def parse_args():
    parser = argparse.ArgumentParser(description="Binance Futures index constituents dashboard")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--workers", type=int, default=12, help="parallel constituents requests")
    return parser.parse_args()


def browser_host(host):
    if host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def dashboard_url(host, port):
    return f"http://{browser_host(host)}:{port}"


def existing_dashboard_is_available(host, port):
    try:
        with urlopen(f"{dashboard_url(host, port)}/api/index-constituents", timeout=1.5) as resp:
            return resp.status == 200
    except (OSError, URLError, ValueError):
        return False


def main():
    args = parse_args()
    if args.workers <= 0:
        raise ValueError("--workers must be greater than 0")

    IndexConstituentsHandler.scanner = IndexConstituentsScanner(workers=args.workers)
    try:
        server = ThreadingHTTPServer((args.host, args.port), IndexConstituentsHandler)
    except OSError as exc:
        if exc.errno in {errno.EADDRINUSE, 48}:
            url = dashboard_url(args.host, args.port)
            if existing_dashboard_is_available(args.host, args.port):
                print(f"Index constituents dashboard running at {url}")
                return
            raise SystemExit(
                f"Port {args.port} is already in use. Open {url} if the dashboard is already running, "
                "or stop the existing process and start it again."
            ) from exc
        raise

    print(f"Index constituents dashboard running at {dashboard_url(args.host, args.port)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
