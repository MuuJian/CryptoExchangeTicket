"""Generate a TradingView watchlist for Bybit linear futures."""

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_lines


OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def build_futures_pairs(instruments: list[dict]) -> list[str]:
    return [
        f"Bybit:{symbol['symbol']}.p"
        for symbol in instruments
        if symbol.get("symbol")
        and symbol.get("quoteCoin") == "USDT"
        and symbol.get("status") == "Trading"
    ]


def get_futures_pairs():
    from pybit.unified_trading import HTTP

    session = HTTP(testnet=False)

    try:
        instruments = session.get_instruments_info(category="linear")["result"]["list"]
    except Exception as e:
        print(f"Bybit futures pairs request failed: {e}")
        return

    return save_lines(
        build_futures_pairs(instruments),
        "bybit_future_pairs.txt",
        folder=OUTPUT_DIR,
        empty_message="No futures pairs found.",
        success_message="Futures pairs have been written to {path}",
    )


GetFuturesPairs = get_futures_pairs


def main():
    get_futures_pairs()


if __name__ == "__main__":
    main()
