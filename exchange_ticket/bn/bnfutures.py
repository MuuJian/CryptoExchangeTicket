import requests

from exchange_ticket.bn.symbols import TRADINGVIEW_SYMBOL_MAP
from shared.utils import DEFAULT_OUTPUT_DIR, save_chunked_lines


EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


def generate_watchlists():
    try:
        response = requests.get(EXCHANGE_INFO_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
            raise ValueError("Binance 合约响应格式错误")
        symbols = payload["symbols"]
        if not symbols:
            raise ValueError("Binance 合约响应没有交易对")
    except (requests.RequestException, ValueError) as error:
        print(f"请求失败: {error}")
        return None

    futures_pairs = []
    tradfi_futures_pairs = []
    tradfi_futures_base_assets = set()

    for item in symbols:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT":
            continue

        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            continue
        symbol = TRADINGVIEW_SYMBOL_MAP.get(symbol, symbol)
        pair = f"Binance:{symbol}.p"

        # Binance spells this API enum TRADIFI_PERPETUAL.
        if item.get("contractType") == "TRADIFI_PERPETUAL":
            tradfi_futures_pairs.append(pair)
            base_asset = item.get("baseAsset")
            if isinstance(base_asset, str) and base_asset:
                tradfi_futures_base_assets.add(base_asset)
        elif item.get("contractType") == "PERPETUAL":
            futures_pairs.append(pair)

    if not futures_pairs or not tradfi_futures_base_assets:
        print("Binance 合约数据不完整，保留原有观察列表。")
        return None

    save_chunked_lines(
        futures_pairs,
        "binance_futures_pairs.txt",
        folder=DEFAULT_OUTPUT_DIR,
        empty_message="没有找到 Binance 永续合约交易对。",
        success_message="成功将 {count} 个永续合约交易对拆成 {files} 个文件: {path}",
    )
    save_chunked_lines(
        tradfi_futures_pairs,
        "binance_tradfi_futures_pairs.txt",
        folder=DEFAULT_OUTPUT_DIR,
        empty_message="没有找到 Binance TradFi 合约交易对。",
        success_message="成功将 {count} 个 TradFi 合约交易对拆成 {files} 个文件: {path}",
    )
    return tradfi_futures_base_assets
