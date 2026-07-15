"""Generate TradingView watchlists for Binance USD-M futures."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.bn.base_asset_map import BASE_ASSET_MAP
from exchange_ticket.bn.tradfi import update_tradfi_watchlist
from exchange_ticket.http import default_client
from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_chunked_lines


EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def mapped_symbol(symbol: str) -> str:
    return BASE_ASSET_MAP.get(symbol, symbol)


def get_exchange_info() -> dict:
    return default_client.get_json(EXCHANGE_INFO_URL, timeout=10)


def build_futures_pairs(data: dict) -> tuple[list[str], list[str]]:
    """Split active USDT perpetual contracts into TradFi and crypto lists."""
    tradfi_pairs: list[str] = []
    futures_pairs: list[str] = []

    for symbol_info in data.get("symbols", []):
        if symbol_info.get("status") != "TRADING" or symbol_info.get("quoteAsset") != "USDT":
            continue

        symbol = symbol_info.get("symbol")
        if not symbol:
            continue
        symbol_name = f"Binance:{mapped_symbol(symbol)}.p"

        if symbol_info.get("contractType") == "TRADIFI_PERPETUAL":
            tradfi_pairs.append(symbol_name)
        elif symbol_info.get("contractType") == "PERPETUAL":
            futures_pairs.append(symbol_name)

    return tradfi_pairs, futures_pairs


def get_futures_pairs():
    try:
        data = get_exchange_info()
    except Exception as e:
        print(f"請求失敗: {e}")
        return

    tradfi_pairs, futures_pairs = build_futures_pairs(data)

    tradfi_paths = update_tradfi_watchlist(
        tradfi_pairs,
        market="futures",
        folder=OUTPUT_DIR,
        chunk_size=500,
    )
    futures_paths = save_chunked_lines(
        futures_pairs,
        "binance_futures_pairs.txt",
        folder=OUTPUT_DIR,
        chunk_size=500,
        empty_message="沒有找到 binance_futures_pairs.txt 的相關交易對，或發生錯誤。",
        success_message="成功將 {count} 個交易對拆成 {files} 個檔案: {path}",
    )
    return [*tradfi_paths, *futures_paths]


def main():
    get_futures_pairs()


if __name__ == "__main__":
    main()
