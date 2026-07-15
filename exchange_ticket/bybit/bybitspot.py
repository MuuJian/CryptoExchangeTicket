"""Generate a TradingView watchlist for Bybit spot markets."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_lines


OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def build_spot_pairs(instruments: list[dict]) -> list[str]:
    return [
        f"Bybit:{symbol['symbol']}"
        for symbol in instruments
        if symbol.get("symbol")
        and symbol.get("quoteCoin") == "USDT"
        and symbol.get("status") == "Trading"
    ]


def get_spot_pairs():
    from pybit.unified_trading import HTTP

    session = HTTP(testnet=False)

    try:
        instruments = session.get_instruments_info(category="spot")["result"]["list"]
    except Exception as e:
        print(f"Bybit spot pairs request failed: {e}")
        return

    return save_lines(
        build_spot_pairs(instruments),
        "bybit_spot_pairs.txt",
        folder=OUTPUT_DIR,
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
