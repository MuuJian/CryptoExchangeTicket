from exchange_ticket.bn import bnfutures, bnspots
from shared.utils import DEFAULT_OUTPUT_DIR, save_chunked_line_groups


def main():
    futures = bnfutures.generate_watchlists()
    if futures is None:
        return 1
    futures_pairs, tradfi_futures_pairs, tradfi_base_assets = futures

    spots = bnspots.generate_watchlists(tradfi_base_assets)
    if spots is None:
        return 1
    spot_pairs, tradfi_spot_pairs = spots

    try:
        save_chunked_line_groups(
            {
                "binance_futures_pairs.txt": futures_pairs,
                "binance_tradfi_futures_pairs.txt": tradfi_futures_pairs,
                "binance_usdt_pairs.txt": spot_pairs,
                "binance_tradfi_spot_pairs.txt": tradfi_spot_pairs,
                # Remove names generated before spot and futures were separated.
                "binance_tradfi_pairs.txt": (),
                "binance_tradifi_pairs.txt": (),
            },
            folder=DEFAULT_OUTPUT_DIR,
            validate_updates=True,
        )
    except (OSError, ValueError) as error:
        print(f"观察列表校验或写入失败: {error}")
        return 1

    print(
        "成功更新 Binance 观察列表: "
        f"{len(spot_pairs)} 个现货，"
        f"{len(tradfi_spot_pairs)} 个 TradFi 现货，"
        f"{len(futures_pairs)} 个永续合约，"
        f"{len(tradfi_futures_pairs)} 个 TradFi 合约。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
