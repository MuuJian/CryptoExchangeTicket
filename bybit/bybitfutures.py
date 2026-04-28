from pybit.unified_trading import HTTP

try:
    from utils import save_lines
except ImportError:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import save_lines


def get_futures_pairs():
    session = HTTP(testnet=False)

    try:
        instruments = session.get_instruments_info(category="linear")["result"]["list"]
    except Exception as e:
        print(f"Bybit futures pairs request failed: {e}")
        return

    futures_pairs = [
        f"Bybit:{symbol['symbol']}.p"
        for symbol in instruments
        if symbol.get("quoteCoin") == "USDT"
    ]

    save_lines(
        futures_pairs,
        "bybit_future_pairs.txt",
        empty_message="No futures pairs found.",
        success_message="Futures pairs have been written to {path}",
    )


GetFuturesPairs = get_futures_pairs


def main():
    get_futures_pairs()


if __name__ == "__main__":
    main()
