from pybit.unified_trading import HTTP

try:
    from utils import save_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_lines


def get_spot_pairs():
    session = HTTP(testnet=False)

    try:
        instruments = session.get_instruments_info(category="spot")["result"]["list"]
    except Exception as e:
        print(f"Bybit spot pairs request failed: {e}")
        return

    usdt_pairs = [
        f"Bybit:{symbol['symbol']}"
        for symbol in instruments
        if symbol.get("quoteCoin") == "USDT"
    ]

    save_lines(
        usdt_pairs,
        "bybit_spot_pairs.txt",
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
