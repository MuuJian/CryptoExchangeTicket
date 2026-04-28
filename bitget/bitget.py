import requests

try:
    from utils import save_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_lines


SYMBOLS_URL = "https://api.bitget.com/api/v2/spot/public/symbols"


def get_spot_pairs():
    try:
        response = requests.get(SYMBOLS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Bitget spot pairs request failed: {e}")
        return

    usdt_pairs = [
        f"Bitget:{symbol['symbol']}"
        for symbol in data.get("data", [])
        if symbol.get("quoteCoin") == "USDT" and symbol.get("status") == "online"
    ]

    save_lines(
        usdt_pairs,
        "bitget_spot_pairs.txt",
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
