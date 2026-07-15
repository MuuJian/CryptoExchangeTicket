"""Realtime Binance Futures open-interest poller and local dashboard."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    from exchange_ticket.http import JsonHttpClient
    from exchange_ticket.utils import optional_float, optional_int
    from exchange_ticket.web import DashboardRequestHandler
except ModuleNotFoundError as exc:
    if exc.name != "exchange_ticket":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from exchange_ticket.http import JsonHttpClient
    from exchange_ticket.utils import optional_float, optional_int
    from exchange_ticket.web import DashboardRequestHandler


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
INDEX_FILE = ROOT_DIR / "index.html"
STATIC_DIR = ROOT_DIR / "static"
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
        funding_cache_seconds=3600,
        snapshot_save_interval=10,
        snapshot_file=None,
        http_client=None,
    ):
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.oi_workers = oi_workers
        self.refresh_symbols_interval = refresh_symbols_interval
        self.oi_24h_cache_seconds = oi_24h_cache_seconds
        self.ticker_cache_seconds = ticker_cache_seconds
        self.funding_cache_seconds = funding_cache_seconds
        self.snapshot_save_interval = snapshot_save_interval
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.ticker_24h_url = f"{self.base_url}/fapi/v1/ticker/24hr"
        self.funding_url = f"{self.base_url}/fapi/v1/premiumIndex"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"
        self.oi_hist_url = f"{self.base_url}/futures/data/openInterestHist"
        self.snapshot_file = Path(snapshot_file) if snapshot_file else DATA_DIR / "latest_oi.json"
        self.http_client = http_client or JsonHttpClient()
        self.lock = threading.RLock()
        self.cache_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.symbols = []
        self.symbol_index = 0
        self.last_symbols_refresh = 0
        self.oi_24h_cache = {}
        self.ticker_cache = None
        self.ticker_cache_at = 0
        self.funding_cache = None
        self.funding_cache_until = 0
        self.error_counts = {}
        self.last_snapshot_save = 0.0
        previous_state = self.load_previous_state()
        self.snapshot = previous_state.get("snapshot", {})
        if not isinstance(self.snapshot, dict):
            self.snapshot = {}
        self.rows_by_symbol = {}
        self.state = {
            "saved_at": None,
            "batch_size": batch_size,
            "batch_delay": batch_delay,
            "oi_workers": oi_workers,
            "ticker_cache_seconds": ticker_cache_seconds,
            "funding_cache_seconds": funding_cache_seconds,
            "snapshot_save_interval": snapshot_save_interval,
            "funding_next_refresh_at": None,
            "updated_symbols": 0,
            "total_symbols": 0,
            "error": None,
            "recent_errors": [],
            "baseline": bool(self.snapshot),
            "rows": [],
        }

    def load_previous_state(self):
        if not self.snapshot_file.exists():
            return {}

        try:
            payload = json.loads(self.snapshot_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError) as exc:
            print(f"{timestamp()} failed to load previous OI snapshot: {exc}")
            return {}

    def request_json(self, url, params=None, timeout=10, attempts=3):
        return self.http_client.get_json(
            url,
            params=params,
            timeout=timeout,
            attempts=attempts,
        )

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

    def save_state(self, *, force=False):
        now = time.monotonic()
        if (
            not force
            and self.snapshot_save_interval > 0
            and now - self.last_snapshot_save < self.snapshot_save_interval
        ):
            return False

        self.snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            snapshot = copy.deepcopy(self.snapshot)
        payload = {
            "saved_at": iso_now(),
            "batch_size": self.batch_size,
            "batch_delay": self.batch_delay,
            "oi_workers": self.oi_workers,
            "ticker_cache_seconds": self.ticker_cache_seconds,
            "funding_cache_seconds": self.funding_cache_seconds,
            "snapshot_save_interval": self.snapshot_save_interval,
            "funding_next_refresh_at": self.funding_next_refresh_iso(),
            "snapshot": snapshot,
        }
        temp_file = self.snapshot_file.with_suffix(f"{self.snapshot_file.suffix}.tmp")
        temp_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp_file.replace(self.snapshot_file)
        self.last_snapshot_save = now
        return True

    def get_active_symbols(self):
        data = self.request_json(self.info_url, timeout=12)
        return sorted(
            {
                item["symbol"]
                for item in data.get("symbols", [])
                if item.get("symbol")
                and item.get("quoteAsset") == "USDT"
                and item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
            }
        )

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

    def get_funding_rates(self):
        now = time.time()
        with self.cache_lock:
            if (
                self.funding_cache_seconds > 0
                and self.funding_cache is not None
                and now < self.funding_cache_until
            ):
                return self.funding_cache

        try:
            response = self.request_json(self.funding_url, timeout=12)
            if isinstance(response, dict):
                response = [response]

            funding_rates = {}
            next_funding_times = []
            now_ms = int(now * 1000)

            for item in response:
                symbol = item.get("symbol")
                if not symbol:
                    continue

                next_funding_time = optional_int(item.get("nextFundingTime"))
                if next_funding_time is not None and next_funding_time > now_ms:
                    next_funding_times.append(next_funding_time)

                funding_rates[symbol] = {
                    "fundingRatePercent": optional_float(item.get("lastFundingRate"), multiplier=100),
                    "nextFundingTime": next_funding_time,
                }
        except Exception as exc:
            with self.cache_lock:
                cached = self.funding_cache
            self.record_symbol_error("funding", exc)
            return cached if cached is not None else {}

        with self.cache_lock:
            self.funding_cache = funding_rates
            self.funding_cache_until = self.next_funding_refresh_at(now, next_funding_times)
        return funding_rates

    def next_funding_refresh_at(self, now, next_funding_times):
        if self.funding_cache_seconds <= 0:
            return now

        future_times = [
            timestamp_ms / 1000
            for timestamp_ms in next_funding_times
            if timestamp_ms and timestamp_ms / 1000 > now
        ]
        if future_times:
            return min(future_times) + 5

        return now + self.funding_cache_seconds

    def funding_next_refresh_iso(self):
        with self.cache_lock:
            refresh_at = self.funding_cache_until
        if not refresh_at:
            return None
        return datetime.fromtimestamp(refresh_at).astimezone().isoformat(timespec="seconds")

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
        self.prune_inactive_symbols()

    def prune_inactive_symbols(self):
        active = set(self.symbols)
        for mapping in (self.snapshot, self.rows_by_symbol):
            for symbol in set(mapping) - active:
                del mapping[symbol]
        with self.cache_lock:
            for symbol in set(self.oi_24h_cache) - active:
                del self.oi_24h_cache[symbol]

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
        funding_rates = self.get_funding_rates()
        results = self.update_symbols(batch, tickers, funding_rates)
        updated_symbols = 0

        with self.lock:
            for result in results:
                if result is None:
                    continue
                symbol, snapshot_item, row = result
                self.snapshot[symbol] = snapshot_item
                self.rows_by_symbol[symbol] = row
                updated_symbols += 1

            rows = self.sorted_rows()
            self.state = {
                "saved_at": iso_now(),
                "batch_size": self.batch_size,
                "batch_delay": self.batch_delay,
                "oi_workers": self.oi_workers,
                "ticker_cache_seconds": self.ticker_cache_seconds,
                "funding_cache_seconds": self.funding_cache_seconds,
                "snapshot_save_interval": self.snapshot_save_interval,
                "funding_next_refresh_at": self.funding_next_refresh_iso(),
                "updated_symbols": updated_symbols,
                "total_symbols": len(self.symbols),
                "error": None,
                "recent_errors": self.recent_errors(),
                "baseline": bool(self.snapshot),
                "rows": rows,
            }
        self.save_state()

    def update_symbols(self, batch, tickers, funding_rates):
        if self.oi_workers <= 1 or len(batch) <= 1:
            results = []
            for symbol in batch:
                try:
                    results.append(self.build_symbol_update(symbol, tickers, funding_rates))
                except Exception as exc:
                    self.record_symbol_error(symbol, exc)
                    results.append(None)
            return results

        results = []
        max_workers = min(self.oi_workers, len(batch))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.build_symbol_update, symbol, tickers, funding_rates): symbol
                for symbol in batch
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    self.record_symbol_error(symbol, exc)
                    results.append(None)
        return results

    def build_symbol_update(self, symbol, tickers, funding_rates):
        ticker = tickers.get(symbol)
        if not ticker:
            return None
        price = ticker["price"]
        volume_24h = ticker["volume24h"]

        current_oi = self.get_open_interest(symbol)

        previous = self.snapshot.get(symbol)
        previous_oi = previous.get("oi", 0) if previous else 0
        funding = funding_rates.get(symbol, {})
        funding_rate_percent = funding.get("fundingRatePercent")
        next_funding_time = funding.get("nextFundingTime")
        if previous:
            if funding_rate_percent is None:
                funding_rate_percent = previous.get("fundingRatePercent")
            if next_funding_time is None:
                next_funding_time = previous.get("nextFundingTime")

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
            "fundingRatePercent": funding_rate_percent,
            "nextFundingTime": next_funding_time,
            "updated_at": iso_now(),
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
            "fundingRatePercent": funding_rate_percent,
            "nextFundingTime": next_funding_time,
            **oi_history,
        }
        return symbol, snapshot_item, row

    def sorted_rows(self):
        rows = [dict(item) for item in self.rows_by_symbol.values()]
        rows.sort(key=lambda item: item.get("absChangePercent") or 0, reverse=True)
        for rank, item in enumerate(rows, 1):
            item["rank"] = rank
        return rows

    def run_forever(self):
        while not self.stop_event.is_set():
            try:
                self.update_batch()
            except Exception as exc:
                print(f"{timestamp()} batch update failed: {exc}")
                with self.lock:
                    self.state["error"] = str(exc)
                    self.state["recent_errors"] = self.recent_errors()

            self.stop_event.wait(self.batch_delay)

    def stop(self):
        self.stop_event.set()

    def get_state(self):
        with self.lock:
            return copy.deepcopy(self.state)


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


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


def positive_float(value):
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_float(value):
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return parsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Realtime price + batched OI dashboard")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=positive_int, default=PORT)
    parser.add_argument("--oi-batch-size", type=positive_int, default=25, help="symbols per batch")
    parser.add_argument("--oi-batch-delay", type=positive_float, default=1.0, help="seconds between batches")
    parser.add_argument("--oi-workers", type=positive_int, default=3, help="parallel OI requests")
    parser.add_argument(
        "--oi-24h-cache-seconds",
        type=non_negative_float,
        default=300,
        help="seconds to cache 24h/7d OI history; 0 disables the cache",
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
        oi_24h_cache_seconds=args.oi_24h_cache_seconds,
        ticker_cache_seconds=args.ticker_cache_seconds,
        funding_cache_seconds=args.funding_cache_seconds,
        snapshot_save_interval=args.snapshot_save_interval,
    )
    DashboardHandler.poller = poller

    thread = threading.Thread(target=poller.run_forever, name="oi-poller", daemon=True)
    thread.start()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
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
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
