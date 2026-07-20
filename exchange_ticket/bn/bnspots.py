import requests

from exchange_ticket.bn.symbols import TRADINGVIEW_SYMBOL_MAP
from shared.utils import DEFAULT_OUTPUT_DIR, remove_chunked_files, save_chunked_lines


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"


def generate_watchlists(tradfi_futures_base_assets):
    if not tradfi_futures_base_assets:
        print("无法获取 Binance TradFi 期货名单，跳过现货生成。")
        return False

    tradfi_spot_base_assets = {
        f"{base_asset}B" for base_asset in tradfi_futures_base_assets
    }

    try:
        response = requests.get(EXCHANGE_INFO_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
            raise ValueError("Binance 现货响应格式错误")
        symbols = payload["symbols"]
        if not symbols:
            raise ValueError("Binance 现货响应没有交易对")
    except (requests.RequestException, ValueError) as error:
        print(f"网络请求失败: {error}")
        return False

    spot_pairs = []
    tradfi_spot_pairs = []

    for item in symbols:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT":
            continue

        symbol = item.get("symbol")
        base_asset = item.get("baseAsset")
        if not isinstance(symbol, str) or not symbol:
            continue
        if not isinstance(base_asset, str) or not base_asset:
            continue
        symbol = TRADINGVIEW_SYMBOL_MAP.get(symbol, symbol)
        pair = f"Binance:{symbol}"

        if base_asset in tradfi_spot_base_assets:
            tradfi_spot_pairs.append(pair)
        else:
            spot_pairs.append(pair)

    if not spot_pairs or not tradfi_spot_pairs:
        print("Binance 现货数据不完整，保留原有观察列表。")
        return False

    save_chunked_lines(
        spot_pairs,
        "binance_usdt_pairs.txt",
        folder=DEFAULT_OUTPUT_DIR,
        empty_message="没有找到 Binance 现货交易对。",
        success_message="成功将 {count} 个现货交易对拆成 {files} 个文件: {path}",
    )
    save_chunked_lines(
        tradfi_spot_pairs,
        "binance_tradfi_spot_pairs.txt",
        folder=DEFAULT_OUTPUT_DIR,
        empty_message="没有找到 Binance TradFi 现货交易对。",
        success_message="成功将 {count} 个 TradFi 现货交易对拆成 {files} 个文件: {path}",
    )

    # Remove files generated before TradFi spot and futures were separated.
    remove_chunked_files(DEFAULT_OUTPUT_DIR / "binance_tradfi_pairs.txt")
    remove_chunked_files(DEFAULT_OUTPUT_DIR / "binance_tradifi_pairs.txt")
    return True
