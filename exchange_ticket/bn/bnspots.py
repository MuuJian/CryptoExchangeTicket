"""Generate a TradingView watchlist for Binance spot markets."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.bn.base_asset_map import BASE_ASSET_MAP
from exchange_ticket.bn.tradfi import is_spot_tradfi, update_tradfi_watchlist
from exchange_ticket.http import default_client
from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_chunked_lines


EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def mapped_symbol(symbol: str) -> str:
    return BASE_ASSET_MAP.get(symbol, symbol)


def get_exchange_info() -> dict:
    return default_client.get_json(EXCHANGE_INFO_URL, timeout=10)


def build_spot_pairs(data: dict) -> tuple[list[str], list[str]]:
    """Split active USDT spot symbols into crypto and TradFi lists."""
    spot_pairs: list[str] = []
    tradfi_pairs: list[str] = []

    for symbol_info in data.get("symbols", []):
        if symbol_info.get("quoteAsset") != "USDT" or symbol_info.get("status") != "TRADING":
            continue

        symbol = symbol_info.get("symbol")
        if not symbol:
            continue

        pair = f"Binance:{mapped_symbol(symbol)}"
        if is_spot_tradfi(symbol_info.get("baseAsset")):
            tradfi_pairs.append(pair)
        else:
            spot_pairs.append(pair)

    return spot_pairs, tradfi_pairs


def get_spot_pairs():
    try:
        data = get_exchange_info()
    except Exception as e:
        print(f"[!] 網路請求失敗: {e}")
        return

    spot_pairs, tradfi_pairs = build_spot_pairs(data)

    spot_paths = save_chunked_lines(
        spot_pairs,
        "binance_usdt_pairs.txt",
        folder=OUTPUT_DIR,
        chunk_size=500,
        empty_message="[-] 沒有找到交易對，或資料為空。",
        success_message="成功將 {count} 個現貨交易對拆成 {files} 個檔案: {path}",
    )
    tradfi_paths = update_tradfi_watchlist(
        tradfi_pairs,
        market="spot",
        folder=OUTPUT_DIR,
        chunk_size=500,
    )
    return [*spot_paths, *tradfi_paths]


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
