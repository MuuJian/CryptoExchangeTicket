import requests

from shared.binance import TRADINGVIEW_SYMBOL_MAP, is_valid_binance_symbol
from shared.http import fetch_json
from shared.utils import MINIMUM_WATCHLIST_ITEMS


EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


def generate_watchlists():
    """Fetch, normalize, and size-check futures watchlists without writing."""
    try:
        payload = fetch_json(EXCHANGE_INFO_URL, timeout=10)
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
            raise ValueError("Binance 合约响应格式错误")
        symbols = payload["symbols"]
        if not symbols:
            raise ValueError("Binance 合约响应没有交易对")
    except (requests.RequestException, ValueError) as error:
        print(f"请求失败: {error}")
        return None

    futures_pairs = set()
    tradfi_futures_pairs = set()
    tradfi_futures_base_assets = set()

    for item in symbols:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT":
            continue

        symbol = item.get("symbol")
        if not is_valid_binance_symbol(symbol):
            continue
        symbol = TRADINGVIEW_SYMBOL_MAP.get(symbol, symbol)
        pair = f"Binance:{symbol}.p"

        # Binance spells this API enum TRADIFI_PERPETUAL.
        if item.get("contractType") == "TRADIFI_PERPETUAL":
            base_asset = item.get("baseAsset")
            if not is_valid_binance_symbol(base_asset):
                continue
            tradfi_futures_pairs.add(pair)
            tradfi_futures_base_assets.add(base_asset)
        elif item.get("contractType") == "PERPETUAL":
            futures_pairs.add(pair)

    futures_pairs = sorted(futures_pairs)
    tradfi_futures_pairs = sorted(tradfi_futures_pairs)

    if (
        len(futures_pairs) < MINIMUM_WATCHLIST_ITEMS
        or len(tradfi_futures_pairs) < MINIMUM_WATCHLIST_ITEMS
    ):
        print("Binance 合约数据不完整，保留原有观察列表。")
        return None

    return (
        futures_pairs,
        tradfi_futures_pairs,
        tradfi_futures_base_assets,
    )
