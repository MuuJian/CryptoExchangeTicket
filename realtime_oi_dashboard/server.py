import argparse
import json
import mimetypes
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
INDEX_FILE = os.path.join(ROOT_DIR, "index.html")
STATIC_DIR = os.path.join(ROOT_DIR, "static")
HOST = "127.0.0.1"
PORT = 8777


class OIPoller:
    def __init__(
        self,
        batch_size=10,
        batch_delay=2.0,
        oi_workers=3,
        refresh_symbols_interval=900,
        oi_24h_cache_seconds=300,
        ticker_cache_seconds=10,
    ):
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.oi_workers = oi_workers
        self.refresh_symbols_interval = refresh_symbols_interval
        self.oi_24h_cache_seconds = oi_24h_cache_seconds
        self.ticker_cache_seconds = ticker_cache_seconds
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.ticker_24h_url = f"{self.base_url}/fapi/v1/ticker/24hr"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"
        self.oi_hist_url = f"{self.base_url}/futures/data/openInterestHist"
        self.snapshot_file = os.path.join(DATA_DIR, "latest_oi.json")
        self.session = requests.Session()
        self.thread_local = threading.local()
        self.lock = threading.RLock()
        self.cache_lock = threading.Lock()
        self.symbols = []
        self.symbol_index = 0
        self.last_symbols_refresh = 0
        self.oi_24h_cache = {}
        self.ticker_cache = None
        self.ticker_cache_at = 0
        self.error_counts = {}
        self.snapshot = self.load_previous_snapshot()
        self.rows_by_symbol = {}
        self.state = {
            "saved_at": None,
            "batch_size": batch_size,
            "batch_delay": batch_delay,
            "oi_workers": oi_workers,
            "ticker_cache_seconds": ticker_cache_seconds,
            "updated_symbols": 0,
            "total_symbols": 0,
            "error": None,
            "recent_errors": [],
            "rows": [],
        }
        self.restore_rows_from_snapshot()

    def load_previous_snapshot(self):
        if not os.path.exists(self.snapshot_file):
            return {}

        try:
            with open(self.snapshot_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            snapshot = payload.get("snapshot", {})
            return snapshot if isinstance(snapshot, dict) else {}
        except Exception as exc:
            print(f"{timestamp()} failed to load previous OI snapshot: {exc}")
            return {}

    def request_json(self, url, params=None, timeout=10, attempts=3):
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
        return 1.0 * attempt

    def record_symbol_error(self, symbol, exc):
        key = str(exc)
        with self.lock:
            self.error_counts[(symbol, key)] = self.error_counts.get((symbol, key), 0) + 1
        print(f"{timestamp()} {symbol} update failed: {exc}")

    def recent_errors(self, limit=10):
        with self.lock:
            items = [
                {"symbol": symbol, "error": error, "count": count}
                for (symbol, error), count in self.error_counts.items()
            ]
        items.sort(key=lambda item: item["count"], reverse=True)
        return items[:limit]

    def save_state(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "batch_size": self.batch_size,
            "batch_delay": self.batch_delay,
            "oi_workers": self.oi_workers,
            "ticker_cache_seconds": self.ticker_cache_seconds,
            "snapshot": self.snapshot,
            "rows": self.sorted_rows(),
        }
        temp_file = f"{self.snapshot_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(temp_file, self.snapshot_file)

    def restore_rows_from_snapshot(self):
        for symbol, item in self.snapshot.items():
            oi = item.get("oi")
            price = item.get("price")
            if oi is None or price is None:
                continue
            self.rows_by_symbol[symbol] = {
                "symbol": symbol,
                "rank": 0,
                "price": price,
                "volume24h": item.get("volume24h"),
                "price24hAgo": None,
                "priceChangePercent": None,
                "currentOi": oi,
                "currentOiValue": oi * price,
                "changeAmount": None,
                "changePercent": None,
                "absChangePercent": 0,
                "changeValue": None,
                "oi24hChangeAmount": None,
                "oi24hChangePercent": None,
                "oi24hChangeValue": None,
                "oi7dChangeAmount": None,
                "oi7dChangePercent": None,
                "oi7dChangeValue": None,
            }

    def get_active_symbols(self):
        data = self.request_json(self.info_url, timeout=12)
        return [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
        ]

    def get_market_tickers(self):
        now = time.time()
        with self.cache_lock:
            if (
                self.ticker_cache_seconds > 0
                and self.ticker_cache is not None
                and now - self.ticker_cache_at < self.ticker_cache_seconds
            ):
                return self.ticker_cache

        try:
            tickers = {
                item["symbol"]: {
                    "price": float(item["lastPrice"]),
                    "volume24h": float(item.get("quoteVolume", 0)),
                    "priceChangePercent": float(item["priceChangePercent"])
                    if item.get("priceChangePercent") is not None
                    else None,
                }
                for item in self.request_json(self.ticker_24h_url, timeout=12)
                if "symbol" in item and "lastPrice" in item
            }
        except Exception as exc:
            with self.cache_lock:
                cached = self.ticker_cache
            if cached is not None:
                self.record_symbol_error("ticker24h", exc)
                return cached
            raise

        with self.cache_lock:
            self.ticker_cache = tickers
            self.ticker_cache_at = now
        return tickers

    def get_open_interest(self, symbol):
        data = self.request_json(self.oi_url, params={"symbol": symbol}, timeout=8)
        return float(data["openInterest"])

    def build_oi_change(self, current_oi, past_oi, price, prefix):
        if past_oi <= 0:
            return {
                f"{prefix}ChangeAmount": None,
                f"{prefix}ChangePercent": None,
                f"{prefix}ChangeValue": None,
            }

        amount = current_oi - past_oi
        return {
            f"{prefix}ChangeAmount": amount,
            f"{prefix}ChangePercent": amount / past_oi * 100,
            f"{prefix}ChangeValue": amount * price,
        }

    def get_oi_history_changes(self, symbol, current_oi, price):
        with self.cache_lock:
            cached = self.oi_24h_cache.get(symbol)
        if (
            self.oi_24h_cache_seconds > 0
            and cached
            and time.time() - cached["cached_at"] < self.oi_24h_cache_seconds
        ):
            return cached["data"]

        data = {
            "oi24hChangeAmount": None,
            "oi24hChangePercent": None,
            "oi24hChangeValue": None,
            "oi7dChangeAmount": None,
            "oi7dChangePercent": None,
            "oi7dChangeValue": None,
        }

        try:
            history = self.request_json(
                self.oi_hist_url,
                params={"symbol": symbol, "period": "1h", "limit": 169},
                timeout=10,
            )
            if isinstance(history, list) and history:
                history.sort(key=lambda item: item.get("timestamp", 0))
                if len(history) >= 25:
                    past_24h_oi = float(history[-25]["sumOpenInterest"])
                    data.update(self.build_oi_change(current_oi, past_24h_oi, price, "oi24h"))
                if len(history) >= 169:
                    past_7d_oi = float(history[0]["sumOpenInterest"])
                    data.update(self.build_oi_change(current_oi, past_7d_oi, price, "oi7d"))
        except Exception as exc:
            self.record_symbol_error(symbol, exc)

        with self.cache_lock:
            self.oi_24h_cache[symbol] = {"cached_at": time.time(), "data": data}
        return data

    def refresh_symbols_if_needed(self):
        if self.symbols and time.time() - self.last_symbols_refresh < self.refresh_symbols_interval:
            return

        self.symbols = self.get_active_symbols()
        self.last_symbols_refresh = time.time()
        if self.symbol_index >= len(self.symbols):
            self.symbol_index = 0

    def next_batch(self):
        if not self.symbols:
            return []

        batch = []
        for _ in range(min(self.batch_size, len(self.symbols))):
            batch.append(self.symbols[self.symbol_index])
            self.symbol_index = (self.symbol_index + 1) % len(self.symbols)
        return batch

    def update_batch(self):
        self.refresh_symbols_if_needed()
        batch = self.next_batch()
        if not batch:
            return

        tickers = self.get_market_tickers()
        results = self.update_symbols(batch, tickers)
        updated_symbols = 0

        for result in results:
            if result is None:
                continue
            symbol, snapshot_item, row = result
            self.snapshot[symbol] = snapshot_item
            self.rows_by_symbol[symbol] = row
            updated_symbols += 1

        rows = self.sorted_rows()
        self.save_state()

        with self.lock:
            self.state = {
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "batch_size": self.batch_size,
                "batch_delay": self.batch_delay,
                "oi_workers": self.oi_workers,
                "ticker_cache_seconds": self.ticker_cache_seconds,
                "updated_symbols": updated_symbols,
                "total_symbols": len(self.symbols),
                "error": None,
                "recent_errors": self.recent_errors(),
                "rows": rows,
            }

    def update_symbols(self, batch, tickers):
        if self.oi_workers <= 1 or len(batch) <= 1:
            results = []
            for symbol in batch:
                try:
                    results.append(self.build_symbol_update(symbol, tickers))
                except Exception as exc:
                    self.record_symbol_error(symbol, exc)
                    results.append(None)
            return results

        results = []
        max_workers = min(self.oi_workers, len(batch))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.build_symbol_update, symbol, tickers): symbol for symbol in batch}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    self.record_symbol_error(symbol, exc)
                    results.append(None)
        return results

    def build_symbol_update(self, symbol, tickers):
        ticker = tickers.get(symbol)
        if not ticker:
            return None
        price = ticker["price"]
        volume_24h = ticker["volume24h"]

        current_oi = self.get_open_interest(symbol)

        previous = self.snapshot.get(symbol)
        previous_oi = previous.get("oi", 0) if previous else 0

        change_percent = None
        change_amount = None
        change_value = None

        if previous_oi > 0:
            change_amount = current_oi - previous_oi
            change_percent = change_amount / previous_oi * 100
            change_value = change_amount * price

        oi_history = self.get_oi_history_changes(symbol, current_oi, price)

        snapshot_item = {
            "oi": current_oi,
            "price": price,
            "volume24h": volume_24h,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        row = {
            "symbol": symbol,
            "rank": 0,
            "price": price,
            "volume24h": volume_24h,
            "currentOi": current_oi,
            "currentOiValue": current_oi * price,
            "changeAmount": change_amount,
            "changePercent": change_percent,
            "absChangePercent": abs(change_percent or 0),
            "changeValue": change_value,
            "price24hAgo": None,
            "priceChangePercent": ticker.get("priceChangePercent"),
            **oi_history,
        }
        return symbol, snapshot_item, row

    def sorted_rows(self):
        rows = list(self.rows_by_symbol.values())
        rows.sort(key=lambda item: item["absChangePercent"], reverse=True)
        for rank, item in enumerate(rows, 1):
            item["rank"] = rank
        return rows

    def run_forever(self):
        while True:
            try:
                self.update_batch()
            except Exception as exc:
                print(f"{timestamp()} batch update failed: {exc}")
                with self.lock:
                    self.state["error"] = str(exc)
                    self.state["recent_errors"] = self.recent_errors()

            time.sleep(self.batch_delay)

    def get_state(self):
        with self.lock:
            return json.loads(json.dumps(self.state))


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DashboardHandler(BaseHTTPRequestHandler):
    poller = None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(INDEX_FILE, "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self.send_static(path)
        if path == "/api/oi":
            return self.send_json(self.poller.get_state())
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
    parser = argparse.ArgumentParser(description="Realtime price + batched OI dashboard")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--oi-batch-size", type=int, default=10, help="symbols to update per batch")
    parser.add_argument("--oi-batch-delay", type=float, default=2.0, help="seconds between batches")
    parser.add_argument("--oi-workers", type=int, default=3, help="parallel OI requests per batch")
    parser.add_argument("--oi-24h-cache-seconds", type=float, default=300, help="seconds to cache 24h/7d OI history; 0 means query every update")
    parser.add_argument("--ticker-cache-seconds", type=float, default=10, help="seconds to cache futures 24h ticker")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.oi_batch_size <= 0:
        raise ValueError("--oi-batch-size must be greater than 0")
    if args.oi_batch_delay <= 0:
        raise ValueError("--oi-batch-delay must be greater than 0")
    if args.oi_workers <= 0:
        raise ValueError("--oi-workers must be greater than 0")
    if args.oi_24h_cache_seconds < 0:
        raise ValueError("--oi-24h-cache-seconds must be 0 or greater")
    if args.ticker_cache_seconds < 0:
        raise ValueError("--ticker-cache-seconds must be 0 or greater")

    poller = OIPoller(
        batch_size=args.oi_batch_size,
        batch_delay=args.oi_batch_delay,
        oi_workers=args.oi_workers,
        oi_24h_cache_seconds=args.oi_24h_cache_seconds,
        ticker_cache_seconds=args.ticker_cache_seconds,
    )
    DashboardHandler.poller = poller

    thread = threading.Thread(target=poller.run_forever, daemon=True)
    thread.start()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    print("Price uses Binance futures WebSocket in the browser.")
    print(
        f"OI updates {args.oi_batch_size} symbols every {args.oi_batch_delay} seconds "
        f"with {args.oi_workers} workers."
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
