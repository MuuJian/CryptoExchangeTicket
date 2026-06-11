from dataclasses import dataclass


@dataclass
class MarketConfig:
    market_type: str
    base_url: str
    exchange_info_path: str
    klines_path: str


@dataclass
class Kline:
    open_time: int
    date: str
    high: float
    low: float
    close: float


MARKETS = {
    "spot": MarketConfig(
        market_type="spot",
        base_url="https://api.binance.com",
        exchange_info_path="/api/v3/exchangeInfo",
        klines_path="/api/v3/klines",
    ),
    "futures": MarketConfig(
        market_type="futures",
        base_url="https://fapi.binance.com",
        exchange_info_path="/fapi/v1/exchangeInfo",
        klines_path="/fapi/v1/klines",
    ),
}
