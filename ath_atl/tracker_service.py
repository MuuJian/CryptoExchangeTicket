import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .client import BinanceClient
from .config import DAY_MS
from .store import ATHATLStore


class ATHATLTracker:
    def __init__(self, client=None, store=None, kline_limit=1000, scan_workers=2):
        self.client = client or BinanceClient()
        self.store = store or ATHATLStore()
        self.kline_limit = kline_limit
        self.scan_workers = max(1, int(scan_workers or 1))
        self.thread_local = threading.local()

    def scan(self, market_types, symbols=None, max_symbols=None):
        breakouts = []
        summary = {}

        for market_type in market_types:
            market_symbols = self.resolve_symbols(market_type, symbols, max_symbols)
            market_breakouts, market_summary = self.scan_market(market_type, market_symbols)
            breakouts.extend(market_breakouts)
            summary[market_type] = market_summary

        return breakouts, summary

    def scan_market(self, market_type, market_symbols):
        breakouts = []
        summary = {
            "symbols": len(market_symbols),
            "processed": 0,
            "breakouts": 0,
            "errors": 0,
            "failed_symbols": [],
        }

        if self.scan_workers <= 1 or len(market_symbols) <= 1:
            for index, symbol in enumerate(market_symbols, 1):
                self.scan_one_symbol(market_type, symbol, breakouts, summary)
                self.print_progress(market_type, index, len(market_symbols))
            return breakouts, summary

        max_workers = min(self.scan_workers, len(market_symbols))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.scan_symbol, market_type, symbol): symbol for symbol in market_symbols}
            for index, future in enumerate(as_completed(futures), 1):
                symbol = futures[future]
                try:
                    symbol_breakouts = future.result()
                except Exception as exc:
                    self.record_symbol_error(market_type, symbol, exc, summary)
                else:
                    self.record_symbol_success(symbol_breakouts, breakouts, summary)
                self.print_progress(market_type, index, len(market_symbols))

        return breakouts, summary

    def scan_one_symbol(self, market_type, symbol, breakouts, summary):
        try:
            symbol_breakouts = self.scan_symbol(market_type, symbol)
        except Exception as exc:
            self.record_symbol_error(market_type, symbol, exc, summary)
        else:
            self.record_symbol_success(symbol_breakouts, breakouts, summary)

    def record_symbol_success(self, symbol_breakouts, breakouts, summary):
        breakouts.extend(symbol_breakouts)
        summary["processed"] += 1
        summary["breakouts"] += len(symbol_breakouts)

    def record_symbol_error(self, market_type, symbol, exc, summary):
        summary["errors"] += 1
        error = str(exc)
        already_saved = any(item["symbol"] == symbol and item["error"] == error for item in summary["failed_symbols"])
        if not already_saved and len(summary["failed_symbols"]) < 20:
            summary["failed_symbols"].append({"symbol": symbol, "error": error})
        print(f"{market_type} {symbol} failed: {exc}")

    def print_progress(self, market_type, index, total):
        if index % 50 == 0 or index == total:
            print(f"{market_type}: {index}/{total} symbols scanned")

    def resolve_symbols(self, market_type, symbols, max_symbols):
        if symbols:
            market_symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        else:
            market_symbols = self.client.get_usdt_symbols(market_type)

        market_symbols = list(dict.fromkeys(market_symbols))

        if max_symbols is not None:
            market_symbols = market_symbols[:max_symbols]

        return market_symbols

    def scan_symbol(self, market_type, symbol):
        record = self.store.get_record(market_type, symbol)
        start_time = self.start_time_for(record)
        klines = list(
            self.worker_client().iter_daily_klines(
                market_type,
                symbol,
                start_time=start_time,
                limit=self.kline_limit,
            )
        )
        if not klines:
            return []

        if record:
            ath_price = float(record["ath_price"])
            atl_price = float(record["atl_price"])
            first_kline_open_time = int(record.get("first_kline_open_time") or 0)
            emit_breakouts = True
        else:
            first = klines[0]
            ath_price = first.high
            atl_price = first.low
            first_kline_open_time = first.open_time
            emit_breakouts = False

        breakouts = []
        current_price = klines[-1].close
        last_kline_open_time = record["last_kline_open_time"] if record else 0

        for kline in klines:
            if not first_kline_open_time or kline.open_time < first_kline_open_time:
                first_kline_open_time = kline.open_time

            if emit_breakouts and kline.high > ath_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_high", kline.high, ath_price))
                ath_price = kline.high
            elif kline.high > ath_price:
                ath_price = kline.high

            if emit_breakouts and kline.low < atl_price:
                breakouts.append(new_breakout(kline, market_type, symbol, "new_low", kline.low, atl_price))
                atl_price = kline.low
            elif kline.low < atl_price:
                atl_price = kline.low

            last_kline_open_time = max(last_kline_open_time, kline.open_time)

        self.store.upsert_record(
            market_type=market_type,
            symbol=symbol,
            current_price=current_price,
            ath_price=ath_price,
            atl_price=atl_price,
            first_kline_open_time=first_kline_open_time,
            last_kline_open_time=last_kline_open_time,
        )
        return breakouts

    def start_time_for(self, record):
        if not record:
            return 0
        if not int(record.get("first_kline_open_time") or 0):
            return 0
        return max(0, int(record["last_kline_open_time"]) - DAY_MS)

    def worker_client(self):
        if self.scan_workers <= 1:
            return self.client

        client = getattr(self.thread_local, "client", None)
        if client is None:
            client = self.client.clone()
            self.thread_local.client = client
        return client


def new_breakout(kline, market_type, symbol, breakout_type, price, previous_price):
    return {
        "date": kline.date,
        "market_type": market_type,
        "symbol": symbol,
        "breakout_type": breakout_type,
        "price": price,
        "previous_price": previous_price,
    }
