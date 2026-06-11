import time

import requests

from .config import DAY_MS
from .models import Kline, MARKETS
from .time_utils import timestamp_to_date


class BinanceClient:
    def __init__(self, request_delay=0.05, retry_attempts=4, retry_backoff=1.0, timeout=20):
        self.session = requests.Session()
        self.request_delay = request_delay
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff = retry_backoff
        self.timeout = timeout

    def clone(self):
        return BinanceClient(
            request_delay=self.request_delay,
            retry_attempts=self.retry_attempts,
            retry_backoff=self.retry_backoff,
            timeout=self.timeout,
        )

    def get_json(self, url, params=None):
        attempts = self.retry_attempts
        for attempt in range(1, attempts + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                if attempt >= attempts:
                    raise
                sleep_seconds = self.retry_sleep_seconds(attempt, exc)
                print(f"request failed {attempt}/{attempts}: {exc}; retrying in {sleep_seconds:.1f}s")
                time.sleep(sleep_seconds)

    def retry_sleep_seconds(self, attempt, exc):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in {418, 429}:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), self.retry_backoff * attempt)
                except ValueError:
                    pass
            multiplier = 20 if response.status_code == 418 else 5
            return max(5.0, self.retry_backoff * attempt * multiplier)
        return self.retry_backoff * attempt

    def get_usdt_symbols(self, market_type):
        config = MARKETS[market_type]
        data = self.get_json(f"{config.base_url}{config.exchange_info_path}")
        symbols = []

        for item in data.get("symbols", []):
            if item.get("quoteAsset") != "USDT" or item.get("status") != "TRADING":
                continue
            if market_type == "futures" and item.get("contractType") != "PERPETUAL":
                continue
            symbols.append(item["symbol"])

        return symbols

    def iter_daily_klines(self, market_type, symbol, start_time=None, limit=1000):
        config = MARKETS[market_type]
        next_start = start_time

        while True:
            params = {"symbol": symbol, "interval": "1d", "limit": limit}
            if next_start is not None:
                params["startTime"] = next_start

            rows = self.get_json(f"{config.base_url}{config.klines_path}", params=params)
            if not rows:
                break

            for row in rows:
                open_time = int(row[0])
                yield Kline(
                    open_time=open_time,
                    date=timestamp_to_date(open_time),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                )

            last_open_time = int(rows[-1][0])
            next_start = last_open_time + DAY_MS
            if len(rows) < limit:
                break
            time.sleep(self.request_delay)
