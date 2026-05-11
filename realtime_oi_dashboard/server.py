import argparse
import json
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
INDEX_FILE = os.path.join(ROOT_DIR, "index.html")
HOST = "127.0.0.1"
PORT = 8777


class OIPoller:
    def __init__(
        self,
        batch_size=25,
        batch_delay=1.0,
        refresh_symbols_interval=900,
        oi_24h_cache_seconds=30,
    ):
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.refresh_symbols_interval = refresh_symbols_interval
        self.oi_24h_cache_seconds = oi_24h_cache_seconds
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.ticker_24h_url = f"{self.base_url}/fapi/v1/ticker/24hr"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"
        self.oi_hist_url = f"{self.base_url}/futures/data/openInterestHist"
        self.kline_url = f"{self.base_url}/fapi/v1/klines"
        self.snapshot_file = os.path.join(DATA_DIR, "latest_oi.json")
        self.session = requests.Session()
        self.lock = threading.Lock()
        self.symbols = []
        self.symbol_index = 0
        self.last_symbols_refresh = 0
        self.oi_24h_cache = {}
        self.snapshot = self.load_previous_snapshot()
        self.rows_by_symbol = {}
        self.state = {
            "saved_at": None,
            "batch_size": batch_size,
            "batch_delay": batch_delay,
            "updated_symbols": 0,
            "total_symbols": 0,
            "error": None,
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
        except Exception:
            return {}

    def save_state(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "batch_size": self.batch_size,
            "batch_delay": self.batch_delay,
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
            }

    def get_active_symbols(self):
        resp = self.session.get(self.info_url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        return [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
        ]

    def get_market_tickers(self):
        resp = self.session.get(self.ticker_24h_url, timeout=12)
        resp.raise_for_status()
        return {
            item["symbol"]: {
                "price": float(item["lastPrice"]),
                "volume24h": float(item.get("quoteVolume", 0)),
            }
            for item in resp.json()
            if "symbol" in item and "lastPrice" in item
        }

    def get_open_interest(self, symbol):
        resp = self.session.get(self.oi_url, params={"symbol": symbol}, timeout=8)
        resp.raise_for_status()
        return float(resp.json()["openInterest"])

    def get_oi_24h_change(self, symbol, current_oi, price):
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
        }

        try:
            resp = self.session.get(
                self.oi_hist_url,
                params={"symbol": symbol, "period": "1h", "limit": 25},
                timeout=10,
            )
            resp.raise_for_status()
            history = resp.json()
            if isinstance(history, list) and history:
                history.sort(key=lambda item: item.get("timestamp", 0))
                past_oi = float(history[0]["sumOpenInterest"])
                if past_oi > 0:
                    amount = current_oi - past_oi
                    data = {
                        "oi24hChangeAmount": amount,
                        "oi24hChangePercent": amount / past_oi * 100,
                        "oi24hChangeValue": amount * price,
                    }
        except Exception:
            pass

        self.oi_24h_cache[symbol] = {"cached_at": time.time(), "data": data}
        return data

    def get_price_24h_change(self, symbol, current_price):
        data = {
            "price24hAgo": None,
            "priceChangePercent": None,
        }

        try:
            resp = self.session.get(
                self.kline_url,
                params={"symbol": symbol, "interval": "1h", "limit": 25},
                timeout=10,
            )
            resp.raise_for_status()
            history = resp.json()
            if isinstance(history, list) and history:
                history.sort(key=lambda item: item[0])
                past_price = float(history[0][4])
                if past_price > 0:
                    data = {
                        "price24hAgo": past_price,
                        "priceChangePercent": (current_price - past_price) / past_price * 100,
                    }
        except Exception:
            pass

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
        updated_symbols = 0

        for symbol in batch:
            ticker = tickers.get(symbol)
            if not ticker:
                continue
            price = ticker["price"]
            volume_24h = ticker["volume24h"]

            try:
                current_oi = self.get_open_interest(symbol)
            except Exception:
                continue

            previous = self.snapshot.get(symbol)
            previous_oi = previous.get("oi", 0) if previous else 0

            change_percent = None
            change_amount = None
            change_value = None

            if previous_oi > 0:
                change_amount = current_oi - previous_oi
                change_percent = change_amount / previous_oi * 100
                change_value = change_amount * price

            oi_24h = self.get_oi_24h_change(symbol, current_oi, price)
            price_24h = self.get_price_24h_change(symbol, price)

            self.snapshot[symbol] = {
                "oi": current_oi,
                "price": price,
                "volume24h": volume_24h,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            self.rows_by_symbol[symbol] = {
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
                **price_24h,
                **oi_24h,
            }
            updated_symbols += 1
            time.sleep(0.02)

        rows = self.sorted_rows()
        self.save_state()

        with self.lock:
            self.state = {
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "batch_size": self.batch_size,
                "batch_delay": self.batch_delay,
                "updated_symbols": updated_symbols,
                "total_symbols": len(self.symbols),
                "error": None,
                "rows": rows,
            }

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
        if path == "/api/oi":
            return self.send_json(self.poller.get_state())
        self.send_error(404)

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
    parser.add_argument("--oi-batch-size", type=int, default=25, help="symbols to update per batch")
    parser.add_argument("--oi-batch-delay", type=float, default=1.0, help="seconds between batches")
    parser.add_argument("--oi-24h-cache-seconds", type=float, default=30, help="seconds to cache 24h OI history; 0 means query every update")
    return parser.parse_args()


def main():
    args = parse_args()
    poller = OIPoller(
        batch_size=args.oi_batch_size,
        batch_delay=args.oi_batch_delay,
        oi_24h_cache_seconds=args.oi_24h_cache_seconds,
    )
    DashboardHandler.poller = poller

    thread = threading.Thread(target=poller.run_forever, daemon=True)
    thread.start()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    print("Price uses Binance futures WebSocket in the browser.")
    print(f"OI updates {args.oi_batch_size} symbols every {args.oi_batch_delay} seconds.")
    server.serve_forever()


if __name__ == "__main__":
    main()
