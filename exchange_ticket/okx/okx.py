"""Generate a TradingView watchlist for OKX spot markets."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.http import default_client
from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_lines


INSTRUMENTS_URL = "https://www.okx.com/api/v5/public/instruments"
OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def build_spot_pairs(data: list[dict]) -> list[str]:
    return [
        f"okx:{symbol['baseCcy']}{symbol['quoteCcy']}"
        for symbol in data
        if symbol.get("baseCcy")
        and symbol.get("quoteCcy") == "USDT"
        and symbol.get("state") == "live"
    ]


def get_spot_pairs():
    try:
        payload = default_client.get_json(
            INSTRUMENTS_URL,
            params={"instType": "SPOT"},
            timeout=10,
        )
    except Exception as e:
        print(f"OKX spot pairs request failed: {e}")
        return

    return save_lines(
        build_spot_pairs(payload.get("data", [])),
        "okx_spot_pairs.txt",
        folder=OUTPUT_DIR,
        empty_message="No spot pairs found or an error occurred.",
        success_message="Spot pairs have been written to {path}",
    )


GetSpotPairs = get_spot_pairs


def main():
    get_spot_pairs()


if __name__ == "__main__":
    main()
