import requests

try:
    from bn.base_asset_map import BASE_ASSET_MAP
except ImportError:
    from base_asset_map import BASE_ASSET_MAP

try:
    from utils import save_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_lines


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
OUTPUT_DIR = "ticket"


def mapped_symbol(symbol):
    return BASE_ASSET_MAP.get(symbol, symbol)


def get_exchange_info():
    response = requests.get(EXCHANGE_INFO_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def get_spot_pairs():
    try:
        data = get_exchange_info()
    except Exception as e:
        print(f"[!] 網路請求失敗: {e}")
        return

    usdt_pairs = []
    for symbol_info in data.get("symbols", []):
        if symbol_info.get("quoteAsset") != "USDT" or symbol_info.get("status") != "TRADING":
            continue

        pair_symbol = mapped_symbol(symbol_info.get("symbol"))
        usdt_pairs.append(f"Binance:{pair_symbol}")

    save_lines(
        usdt_pairs,
        "binance_usdt_pairs.txt",
        folder=OUTPUT_DIR,
        empty_message="[-] 沒有找到交易對，或資料為空。",
        success_message="成功將 {count} 個現貨交易對寫入至: {path}",
    )


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
