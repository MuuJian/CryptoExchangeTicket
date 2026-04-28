import requests

try:
    from utils import save_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_lines


INSTRUMENTS_URL = "https://www.okx.com/api/v5/public/instruments"


def get_spot_pairs():
    params = {"instType": "SPOT"}

    try:
        response = requests.get(INSTRUMENTS_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as e:
        print(f"OKX spot pairs request failed: {e}")
        return

    usdt_pairs = [
        f"okx:{symbol['baseCcy']}{symbol['quoteCcy']}"
        for symbol in data
        if symbol.get("quoteCcy") == "USDT"
    ]

    save_lines(
        usdt_pairs,
        "okx_spot_pairs.txt",
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
