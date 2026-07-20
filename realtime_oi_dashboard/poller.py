"""Realtime Binance Futures open-interest polling and cache state."""

from __future__ import annotations

import copy
import json
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from math import isfinite
from pathlib import Path

from shared.http import JsonHttpClient
from shared.utils import optional_float, optional_int, write_text_atomic


DATA_DIR = Path(__file__).resolve().parent / "data"
HOUR_MS = 60 * 60 * 1000
HISTORY_BASELINE_TOLERANCE_MS = 2 * HOUR_MS
SNAPSHOT_BASELINE_MAX_AGE_SECONDS = 15 * 60
SNAPSHOT_CLOCK_SKEW_SECONDS = 60
RECENT_ERROR_SECONDS = 60
PARTIAL_RESPONSE_RETRY_SECONDS = 60
EMPTY_BATCH_ERROR = "本批次没有成功更新任何 OI 数据"


class _PollingStopped(Exception):
    """Internal signal used to cancel HTTP retries during shutdown."""


class OIPoller:
    def __init__(
        self,
        batch_size=25,
        batch_delay=1.0,
        oi_workers=3,
        refresh_symbols_interval=900,
        oi_history_cache_seconds=300,
        ticker_cache_seconds=10,
        funding_cache_seconds=3600,
        snapshot_save_interval=10,
        snapshot_file=None,
        http_client=None,
    ):
        self.batch_size = _positive_int("batch_size", batch_size)
        self.batch_delay = _non_negative_seconds("batch_delay", batch_delay)
        self.oi_workers = _positive_int("oi_workers", oi_workers)
        self.refresh_symbols_interval = _non_negative_seconds(
            "refresh_symbols_interval",
            refresh_symbols_interval,
        )
        self.oi_history_cache_seconds = _non_negative_seconds(
            "oi_history_cache_seconds",
            oi_history_cache_seconds,
        )
        self.ticker_cache_seconds = _non_negative_seconds(
            "ticker_cache_seconds",
            ticker_cache_seconds,
        )
        self.funding_cache_seconds = _non_negative_seconds(
            "funding_cache_seconds",
            funding_cache_seconds,
        )
        self.snapshot_save_interval = _non_negative_seconds(
            "snapshot_save_interval",
            snapshot_save_interval,
        )
        self.base_url = "https://fapi.binance.com"
        self.info_url = f"{self.base_url}/fapi/v1/exchangeInfo"
        self.ticker_24h_url = f"{self.base_url}/fapi/v1/ticker/24hr"
        self.funding_url = f"{self.base_url}/fapi/v1/premiumIndex"
        self.oi_url = f"{self.base_url}/fapi/v1/openInterest"
        self.oi_hist_url = f"{self.base_url}/futures/data/openInterestHist"
        self.snapshot_file = Path(snapshot_file) if snapshot_file else DATA_DIR / "latest_oi.json"
        self.stop_event = threading.Event()
        self.http_client = (
            JsonHttpClient(
                sleep=self._wait_for_retry,
                check_cancelled=self._raise_if_stopped,
            )
            if http_client is None
            else http_client
        )
        self.lock = threading.RLock()
        self.cache_lock = threading.Lock()
        self.save_lock = threading.Lock()
        self.symbols = []
        self.symbol_index = 0
        self.last_symbols_refresh = 0.0
        self.oi_history_cache = {}
        self.ticker_cache = None
        self.ticker_cache_at = 0.0
        self.funding_cache = None
        self.funding_cache_until = 0
        self.error_events = deque(maxlen=10)
        self.last_snapshot_save = 0.0
        self.snapshot = self.load_previous_snapshot()
        self.rows_by_symbol = {}
        self.state = {
            "saved_at": None,
            "total_symbols": 0,
            "error": None,
            "rows": [],
        }

    def load_previous_snapshot(self):
        if not self.snapshot_file.exists():
            return {}

        try:
            payload = json.loads(self.snapshot_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"{timestamp()} failed to load previous OI snapshot: {exc}")
            return {}

        raw_snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if not isinstance(raw_snapshot, dict):
            return {}

        snapshot = {}
        now = time.time()
        now_ms = int(now * 1000)
        for symbol, item in raw_snapshot.items():
            if (
                not isinstance(symbol, str)
                or not symbol.strip()
                or symbol != symbol.strip()
                or not isinstance(item, dict)
            ):
                continue
            oi = optional_float(item.get("oi"))
            if oi is None or oi < 0 or not is_recent_snapshot(item, now):
                continue
            next_funding_time = future_timestamp_ms(item.get("nextFundingTime"), now_ms)
            updated_at = item.get("updated_at")
            snapshot[symbol] = {
                "oi": oi,
                "fundingRatePercent": optional_float(item.get("fundingRatePercent")),
                "nextFundingTime": next_funding_time,
                "updated_at": updated_at if isinstance(updated_at, str) else None,
            }
        return snapshot

    def request_json(self, url, params=None, timeout=10, attempts=3):
        self._raise_if_stopped()
        return self.http_client.get_json(
            url,
            params=params,
            timeout=timeout,
            attempts=attempts,
        )

    def _raise_if_stopped(self):
        if self.stop_event.is_set():
            raise _PollingStopped

    def _wait_for_retry(self, delay):
        if self.stop_event.wait(delay):
            raise _PollingStopped

    def record_symbol_error(self, symbol, exc):
        if self.stop_event.is_set():
            return
        with self.lock:
            if self.stop_event.is_set():
                return
            self.error_events.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "recorded_at": time.monotonic(),
                }
            )
        print(f"{timestamp()} {symbol} update failed: {exc}")

    def recent_errors(self):
        with self.lock:
            cutoff = time.monotonic() - RECENT_ERROR_SECONDS
            while self.error_events and self.error_events[0]["recorded_at"] < cutoff:
                self.error_events.popleft()
            return [
                {"symbol": item["symbol"], "error": item["error"]}
                for item in self.error_events
            ]

    def save_state(self, *, force=False):
        with self.save_lock:
            now = time.monotonic()
            if (
                not force
                and self.snapshot_save_interval > 0
                and now - self.last_snapshot_save < self.snapshot_save_interval
            ):
                return False

            with self.lock:
                snapshot = copy.deepcopy(self.snapshot)
            payload = {
                "saved_at": iso_now(),
                "snapshot": snapshot,
            }
            write_text_atomic(
                self.snapshot_file,
                json.dumps(payload, ensure_ascii=False, allow_nan=False),
            )
            self.last_snapshot_save = time.monotonic()
            return True

    def get_active_symbols(self):
        data = self.request_json(self.info_url, timeout=12)
        if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
            raise ValueError("unexpected exchange-info response")

        symbols = sorted(
            {
                item["symbol"]
                for item in data.get("symbols", [])
                if isinstance(item, dict)
                and isinstance(item.get("symbol"), str)
                and item["symbol"]
                and item.get("quoteAsset") == "USDT"
                and item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
            }
        )
        if not symbols:
            raise ValueError("exchange-info response contains no active symbols")
        return symbols

    def get_market_tickers(self):
        now = time.monotonic()
        with self.lock:
            active_symbols = set(self.symbols)
        with self.cache_lock:
            if (
                self.ticker_cache_seconds > 0
                and self.ticker_cache is not None
                and now - self.ticker_cache_at < self.ticker_cache_seconds
            ):
                return self.ticker_cache

        try:
            response = self.request_json(self.ticker_24h_url, timeout=12)
            tickers = _parse_market_tickers(response, active_symbols)

            missing_symbols = active_symbols - set(tickers)
            if missing_symbols:
                with self.cache_lock:
                    cached = dict(self.ticker_cache or {})
                for symbol in missing_symbols:
                    if symbol in cached:
                        tickers[symbol] = cached[symbol]
                self.record_symbol_error(
                    "ticker24h",
                    ValueError(f"ticker response missing {len(missing_symbols)} active symbols"),
                )
        except _PollingStopped:
            raise
        except Exception as exc:
            with self.cache_lock:
                cached = self.ticker_cache
                if cached is not None and self.ticker_cache_seconds > 0:
                    self.ticker_cache_at = time.monotonic()
            if cached is not None:
                self.record_symbol_error("ticker24h", exc)
                return cached
            raise

        with self.cache_lock:
            self.ticker_cache = tickers
            self.ticker_cache_at = time.monotonic()
        return tickers

    def get_funding_rates(self):
        now = time.time()
        with self.lock:
            active_symbols = set(self.symbols)
        with self.cache_lock:
            if (
                self.funding_cache_seconds > 0
                and self.funding_cache is not None
                and now < self.funding_cache_until
            ):
                return self.funding_cache

        try:
            response = self.request_json(self.funding_url, timeout=12)
            now = time.time()
            now_ms = int(now * 1000)
            funding_rates, next_funding_times = _parse_funding_rates(
                response,
                active_symbols,
                now_ms,
            )

            missing_symbols = active_symbols - set(funding_rates)
            if missing_symbols:
                with self.cache_lock:
                    cached = dict(self.funding_cache or {})
                for symbol in missing_symbols:
                    if symbol in cached:
                        cached_funding = cached[symbol]
                        funding_rates[symbol] = cached_funding
                        cached_next_time = future_timestamp_ms(
                            cached_funding.get("nextFundingTime"),
                            now_ms,
                        )
                        if cached_next_time is not None:
                            next_funding_times.append(cached_next_time)
                self.record_symbol_error(
                    "funding",
                    ValueError(
                        f"funding-rate response missing {len(missing_symbols)} active symbols"
                    ),
                )
        except _PollingStopped:
            raise
        except Exception as exc:
            failure_time = time.time()
            with self.cache_lock:
                cached = self.funding_cache if self.funding_cache is not None else {}
                self.funding_cache = cached
                retry_seconds = min(
                    self.funding_cache_seconds,
                    PARTIAL_RESPONSE_RETRY_SECONDS,
                )
                self.funding_cache_until = failure_time + retry_seconds
            self.record_symbol_error("funding", exc)
            return cached

        with self.cache_lock:
            self.funding_cache = funding_rates
            refresh_at = self.next_funding_refresh_at(now, next_funding_times)
            if missing_symbols:
                refresh_at = min(refresh_at, now + PARTIAL_RESPONSE_RETRY_SECONDS)
            self.funding_cache_until = refresh_at
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

    def get_open_interest(self, symbol):
        data = self.request_json(self.oi_url, params={"symbol": symbol}, timeout=8)
        value = optional_float(data.get("openInterest")) if isinstance(data, dict) else None
        if value is None or value < 0:
            raise ValueError("unexpected open-interest response")
        return value

    def calculate_change_percent(self, current_oi, past_oi):
        if past_oi is None or past_oi <= 0:
            return None
        change_percent = (current_oi - past_oi) / past_oi * 100
        return change_percent if isfinite(change_percent) else None

    def get_oi_history_changes(self, symbol, current_oi):
        now = time.monotonic()
        with self.cache_lock:
            cached = self.oi_history_cache.get(symbol)
        if (
            self.oi_history_cache_seconds > 0
            and cached
            and now - cached["cached_at"] < self.oi_history_cache_seconds
        ):
            past_24h_oi = cached["past_24h_oi"]
            past_7d_oi = cached["past_7d_oi"]
        else:
            try:
                history = self.request_json(
                    self.oi_hist_url,
                    params={"symbol": symbol, "period": "1h", "limit": 169},
                    timeout=10,
                )
                history_points = _parse_oi_history_points(history)
                if not history_points and cached and any(
                    cached[key] is not None for key in ("past_24h_oi", "past_7d_oi")
                ):
                    raise ValueError("OI history response contains no valid points")

                now_ms = int(time.time() * 1000)
                past_24h_oi = self.history_open_interest(
                    history_points,
                    now_ms - 24 * HOUR_MS,
                    "24h",
                )
                past_7d_oi = self.history_open_interest(
                    history_points,
                    now_ms - 7 * 24 * HOUR_MS,
                    "7d",
                )
            except _PollingStopped:
                raise
            except Exception as exc:
                self.record_symbol_error(symbol, exc)
                if cached:
                    past_24h_oi = cached["past_24h_oi"]
                    past_7d_oi = cached["past_7d_oi"]
                else:
                    past_24h_oi = None
                    past_7d_oi = None
            else:
                if self.oi_history_cache_seconds > 0:
                    with self.cache_lock:
                        self.oi_history_cache[symbol] = {
                            "cached_at": time.monotonic(),
                            "past_24h_oi": past_24h_oi,
                            "past_7d_oi": past_7d_oi,
                        }

        return {
            "oi24hChangePercent": self.calculate_change_percent(current_oi, past_24h_oi),
            "oi7dChangePercent": self.calculate_change_percent(current_oi, past_7d_oi),
        }

    def history_open_interest(self, history_points, target_timestamp_ms, label):
        saw_invalid_value = False
        for timestamp_ms, item in reversed(history_points):
            if timestamp_ms > target_timestamp_ms:
                continue
            if target_timestamp_ms - timestamp_ms > HISTORY_BASELINE_TOLERANCE_MS:
                break

            open_interest = optional_float(item.get("sumOpenInterest"))
            if open_interest is None or open_interest < 0:
                saw_invalid_value = True
                continue
            return open_interest

        if saw_invalid_value:
            raise ValueError(f"invalid {label} OI history")
        return None

    def refresh_symbols_if_needed(self):
        now = time.monotonic()
        if self.symbols and now - self.last_symbols_refresh < self.refresh_symbols_interval:
            return

        symbols = self.get_active_symbols()
        with self.lock:
            if self.stop_event.is_set():
                return
            symbols_changed = symbols != self.symbols
            has_new_symbols = bool(set(symbols) - set(self.symbols))
            self.symbols = symbols
            self.last_symbols_refresh = time.monotonic()
            if symbols_changed or self.symbol_index >= len(self.symbols):
                self.symbol_index = 0
            self.prune_inactive_symbols(reset_market_caches=has_new_symbols)

    def prune_inactive_symbols(self, *, reset_market_caches=False):
        active = set(self.symbols)
        for mapping in (self.snapshot, self.rows_by_symbol):
            for symbol in set(mapping) - active:
                del mapping[symbol]
        with self.cache_lock:
            self.oi_history_cache = {
                symbol: item
                for symbol, item in self.oi_history_cache.items()
                if symbol in active
            }
            if reset_market_caches:
                self.ticker_cache = None
                self.ticker_cache_at = 0.0
                self.funding_cache = None
                self.funding_cache_until = 0
                return

            if self.ticker_cache is not None:
                self.ticker_cache = {
                    symbol: item
                    for symbol, item in self.ticker_cache.items()
                    if symbol in active
                }
                if not self.ticker_cache:
                    self.ticker_cache = None
                    self.ticker_cache_at = 0.0
            if self.funding_cache is not None:
                self.funding_cache = {
                    symbol: item
                    for symbol, item in self.funding_cache.items()
                    if symbol in active
                }
                if not self.funding_cache:
                    self.funding_cache = None
                    self.funding_cache_until = 0

    def next_batch(self):
        if not self.symbols:
            return []

        batch = []
        for _ in range(min(self.batch_size, len(self.symbols))):
            batch.append(self.symbols[self.symbol_index])
            self.symbol_index = (self.symbol_index + 1) % len(self.symbols)
        return batch

    def update_batch(self, executor=None):
        if self.stop_event.is_set():
            return

        self.refresh_symbols_if_needed()
        if self.stop_event.is_set():
            return
        batch = self.next_batch()
        if not batch:
            return

        tickers = self.get_market_tickers()
        if self.stop_event.is_set():
            return
        funding_rates = self.get_funding_rates()
        if self.stop_event.is_set():
            return
        results = self.update_symbols(batch, tickers, funding_rates, executor=executor)

        with self.lock:
            if self.stop_event.is_set():
                return
            updated_count = 0
            for result in results:
                if result is None:
                    continue
                symbol, snapshot_item, row = result
                self.snapshot[symbol] = snapshot_item
                self.rows_by_symbol[symbol] = row
                updated_count += 1

            rows = [dict(item) for item in self.rows_by_symbol.values()]
            if updated_count == 0:
                self.state = {
                    "saved_at": self.state["saved_at"],
                    "total_symbols": len(self.symbols),
                    "error": EMPTY_BATCH_ERROR,
                    "rows": rows,
                }
                return

            self.state = {
                "saved_at": iso_now(),
                "total_symbols": len(self.symbols),
                "error": None,
                "rows": rows,
            }
        self.save_state()

    def update_symbols(self, batch, tickers, funding_rates, executor=None):
        if self.oi_workers <= 1 or len(batch) <= 1:
            results = []
            for symbol in batch:
                if self.stop_event.is_set():
                    break
                try:
                    results.append(self.build_symbol_update(symbol, tickers, funding_rates))
                except _PollingStopped:
                    break
                except Exception as exc:
                    self.record_symbol_error(symbol, exc)
                    results.append(None)
            return results

        if executor is not None:
            return self._update_symbols_parallel(batch, tickers, funding_rates, executor)

        max_workers = min(self.oi_workers, len(batch))
        with ThreadPoolExecutor(max_workers=max_workers) as temporary_executor:
            return self._update_symbols_parallel(
                batch,
                tickers,
                funding_rates,
                temporary_executor,
            )

    def _update_symbols_parallel(self, batch, tickers, funding_rates, executor):
        futures = {
            executor.submit(self.build_symbol_update, symbol, tickers, funding_rates): symbol
            for symbol in batch
        }
        results_by_symbol = {symbol: None for symbol in batch}
        for future in as_completed(futures):
            if self.stop_event.is_set():
                for pending in futures:
                    pending.cancel()
                break
            symbol = futures[future]
            try:
                results_by_symbol[symbol] = future.result()
            except _PollingStopped:
                for pending in futures:
                    pending.cancel()
                break
            except Exception as exc:
                self.record_symbol_error(symbol, exc)
        return [results_by_symbol[symbol] for symbol in batch]

    def build_symbol_update(self, symbol, tickers, funding_rates):
        if self.stop_event.is_set():
            return None

        ticker = tickers.get(symbol)
        if not ticker:
            raise ValueError("ticker data unavailable")
        price = ticker["price"]
        volume_24h = ticker["volume24h"]

        current_oi = self.get_open_interest(symbol)
        if self.stop_event.is_set():
            return None
        current_oi_value = current_oi * price
        if not isfinite(current_oi_value):
            raise ValueError("open-interest value is not finite")

        now = time.time()
        previous = self.snapshot.get(symbol)
        if previous and not is_recent_snapshot(previous, now):
            previous = None
        previous_oi = previous.get("oi", 0) if previous else 0
        funding = funding_rates.get(symbol, {})
        funding_rate_percent = funding.get("fundingRatePercent")
        now_ms = int(now * 1000)
        next_funding_time = future_timestamp_ms(funding.get("nextFundingTime"), now_ms)
        if previous:
            if funding_rate_percent is None:
                funding_rate_percent = previous.get("fundingRatePercent")
            if next_funding_time is None:
                next_funding_time = future_timestamp_ms(previous.get("nextFundingTime"), now_ms)

        change_percent = self.calculate_change_percent(current_oi, previous_oi)

        oi_history = self.get_oi_history_changes(symbol, current_oi)

        snapshot_item = {
            "oi": current_oi,
            "fundingRatePercent": funding_rate_percent,
            "nextFundingTime": next_funding_time,
            "updated_at": iso_now(),
        }
        row = {
            "symbol": symbol,
            "price": price,
            "volume24h": volume_24h,
            "currentOi": current_oi,
            "currentOiValue": current_oi_value,
            "changePercent": change_percent,
            "priceChangePercent": ticker.get("priceChangePercent"),
            "fundingRatePercent": funding_rate_percent,
            "nextFundingTime": next_funding_time,
            **oi_history,
        }
        return symbol, snapshot_item, row

    def run_forever(self):
        if self.stop_event.is_set():
            return

        executor = (
            ThreadPoolExecutor(max_workers=self.oi_workers, thread_name_prefix="oi-worker")
            if self.oi_workers > 1
            else None
        )
        try:
            while not self.stop_event.is_set():
                try:
                    self.update_batch(executor=executor)
                except _PollingStopped:
                    break
                except Exception as exc:
                    if self.stop_event.is_set():
                        break
                    print(f"{timestamp()} batch update failed: {exc}")
                    with self.lock:
                        self.state["total_symbols"] = len(self.symbols)
                        self.state["rows"] = [
                            dict(item) for item in self.rows_by_symbol.values()
                        ]
                        self.state["error"] = str(exc)

                self.stop_event.wait(self.batch_delay)
        finally:
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)

    def stop(self):
        with self.lock:
            self.stop_event.set()

    def get_state(self):
        with self.lock:
            state = copy.deepcopy(self.state)
            state["recent_errors"] = self.recent_errors()
            return state


def _parse_market_tickers(response, active_symbols):
    if not isinstance(response, list):
        raise ValueError("unexpected ticker response")

    tickers = {}
    for item in response:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        price = optional_float(item.get("lastPrice"))
        if not isinstance(symbol, str) or not symbol or price is None or price <= 0:
            continue
        if active_symbols and symbol not in active_symbols:
            continue

        volume_24h = optional_float(item.get("quoteVolume"))
        if volume_24h is not None and volume_24h < 0:
            volume_24h = None
        tickers[symbol] = {
            "price": price,
            "volume24h": volume_24h,
            "priceChangePercent": optional_float(item.get("priceChangePercent")),
        }

    if not tickers:
        raise ValueError("ticker response contains no valid symbols")
    return tickers


def _parse_funding_rates(response, active_symbols, now_ms):
    if isinstance(response, dict):
        response = [response]
    if not isinstance(response, list):
        raise ValueError("unexpected funding-rate response")

    funding_rates = {}
    next_funding_times = []
    for item in response:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        if active_symbols and symbol not in active_symbols:
            continue

        funding_rate_percent = optional_float(
            item.get("lastFundingRate"),
            multiplier=100,
        )
        next_funding_time = future_timestamp_ms(item.get("nextFundingTime"), now_ms)
        if funding_rate_percent is None and next_funding_time is None:
            continue
        if next_funding_time is not None:
            next_funding_times.append(next_funding_time)

        funding_rates[symbol] = {
            "fundingRatePercent": funding_rate_percent,
            "nextFundingTime": next_funding_time,
        }

    if not funding_rates:
        raise ValueError("funding-rate response contains no valid symbols")
    return funding_rates, next_funding_times


def _parse_oi_history_points(response):
    if not isinstance(response, list):
        raise ValueError("unexpected OI history response")

    history_points = []
    for item in response:
        if not isinstance(item, dict):
            continue
        timestamp_ms = optional_int(item.get("timestamp"))
        if timestamp_ms is None or timestamp_ms <= 0:
            continue
        history_points.append((timestamp_ms, item))
    history_points.sort(key=lambda point: point[0])
    return history_points


def _positive_int(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _non_negative_seconds(name, value):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite non-negative number")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite non-negative number") from exc
    if not isfinite(parsed) or parsed < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return parsed


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def future_timestamp_ms(value, now_ms=None):
    parsed = optional_int(value)
    if parsed is None:
        return None
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return parsed if parsed > current_ms else None


def is_recent_snapshot(item, now=None):
    updated_at = item.get("updated_at") if isinstance(item, dict) else None
    if not isinstance(updated_at, str):
        return False
    try:
        updated_datetime = datetime.fromisoformat(updated_at)
        if updated_datetime.tzinfo is None:
            return False
        updated_timestamp = updated_datetime.timestamp()
    except (OSError, ValueError, OverflowError):
        return False

    current_timestamp = time.time() if now is None else now
    age = current_timestamp - updated_timestamp
    return -SNAPSHOT_CLOCK_SKEW_SECONDS <= age <= SNAPSHOT_BASELINE_MAX_AGE_SECONDS
