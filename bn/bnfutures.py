import requests

try:
    from bn.base_asset_map import BASE_ASSET_MAP
except ImportError:
    from base_asset_map import BASE_ASSET_MAP

try:
    from utils import save_chunked_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_chunked_lines


EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
OUTPUT_DIR = "ticket"


def mapped_symbol(symbol):
    return BASE_ASSET_MAP.get(symbol, symbol)


def get_exchange_info():
    response = requests.get(EXCHANGE_INFO_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def get_futures_pairs():
    try:
        data = get_exchange_info()
    except Exception as e:
        print(f"請求失敗: {e}")
        return

    tradfi_pairs = []
    futures_pairs = []

    for symbol_info in data.get("symbols", []):
        if symbol_info.get("status") != "TRADING" or symbol_info.get("quoteAsset") != "USDT":
            continue

        pair_symbol = mapped_symbol(symbol_info.get("symbol"))
        symbol_name = f"Binance:{pair_symbol}.p"
        contract_type = symbol_info.get("contractType")

        if contract_type == "TRADIFI_PERPETUAL":
            tradfi_pairs.append(symbol_name)
        elif contract_type == "PERPETUAL":
            futures_pairs.append(symbol_name)

    save_chunked_lines(
        tradfi_pairs,
        "binance_tradfi_pairs.txt",
        folder=OUTPUT_DIR,
        chunk_size=500,
        empty_message="沒有找到 binance_tradfi_pairs.txt 的相關交易對，或發生錯誤。",
        success_message="成功將 {count} 個交易對拆成 {files} 個檔案: {path}",
    )
    save_chunked_lines(
        futures_pairs,
        "binance_futures_pairs.txt",
        folder=OUTPUT_DIR,
        chunk_size=500,
        empty_message="沒有找到 binance_futures_pairs.txt 的相關交易對，或發生錯誤。",
        success_message="成功將 {count} 個交易對拆成 {files} 個檔案: {path}",
    )


def main():
    get_futures_pairs()


if __name__ == "__main__":
    main()
