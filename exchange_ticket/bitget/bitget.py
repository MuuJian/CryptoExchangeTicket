"""Generate a TradingView watchlist for Bitget spot markets."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.http import default_client
from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_lines


SYMBOLS_URL = "https://api.bitget.com/api/v2/spot/public/symbols"
OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def build_spot_pairs(data: dict) -> list[str]:
    return [
        f"Bitget:{symbol['symbol']}"
        for symbol in data.get("data", [])
        if symbol.get("symbol")
        and symbol.get("quoteCoin") == "USDT"
        and symbol.get("status") == "online"
    ]


def get_spot_pairs():
    try:
        data = default_client.get_json(SYMBOLS_URL, timeout=10)
    except Exception as e:
        print(f"Bitget spot pairs request failed: {e}")
        return

    return save_lines(
        build_spot_pairs(data),
        "bitget_spot_pairs.txt",
        folder=OUTPUT_DIR,
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
