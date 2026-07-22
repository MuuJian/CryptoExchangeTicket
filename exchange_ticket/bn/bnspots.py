import requests

from shared.binance import TRADINGVIEW_SYMBOL_MAP, is_valid_binance_symbol
from shared.http import fetch_json
from shared.utils import MINIMUM_WATCHLIST_ITEMS


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"


def generate_watchlists(tradfi_futures_base_assets):
    """Build normalized, size-checked spot lists from TradFi futures bases."""
    if not tradfi_futures_base_assets:
        print("无法获取 Binance TradFi 期货名单，跳过现货生成。")
        return None

    tradfi_spot_base_assets = {
        f"{base_asset}B" for base_asset in tradfi_futures_base_assets
    }

    try:
        payload = fetch_json(
            EXCHANGE_INFO_URL,
            params={"permissions": "SPOT", "symbolStatus": "TRADING"},
            timeout=10,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
            raise ValueError("Binance 现货响应格式错误")
        symbols = payload["symbols"]
        if not symbols:
            raise ValueError("Binance 现货响应没有交易对")
    except (requests.RequestException, ValueError) as error:
        print(f"网络请求失败: {error}")
        return None

    spot_pairs = set()
    tradfi_spot_pairs = set()

    for item in symbols:
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") != "TRADING"
            or item.get("quoteAsset") != "USDT"
            or item.get("isSpotTradingAllowed") is not True
        ):
            continue

        symbol = item.get("symbol")
        base_asset = item.get("baseAsset")
        if not is_valid_binance_symbol(symbol):
            continue
        if not is_valid_binance_symbol(base_asset):
            continue
        symbol = TRADINGVIEW_SYMBOL_MAP.get(symbol, symbol)
        pair = f"Binance:{symbol}"

        if base_asset in tradfi_spot_base_assets:
            tradfi_spot_pairs.add(pair)
        else:
            spot_pairs.add(pair)

    spot_pairs = sorted(spot_pairs)
    tradfi_spot_pairs = sorted(tradfi_spot_pairs)

    if (
        len(spot_pairs) < MINIMUM_WATCHLIST_ITEMS
        or len(tradfi_spot_pairs) < MINIMUM_WATCHLIST_ITEMS
    ):
        print("Binance 现货数据不完整，保留原有观察列表。")
        return None

    return spot_pairs, tradfi_spot_pairs
