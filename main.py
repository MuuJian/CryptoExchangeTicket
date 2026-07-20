from exchange_ticket.bn import bnfutures, bnspots


def main():
    try:
        tradfi_futures_base_assets = bnfutures.generate_watchlists()
        if tradfi_futures_base_assets is None:
            return 1
        if not bnspots.generate_watchlists(tradfi_futures_base_assets):
            return 1
    except OSError as error:
        print(f"写入观察列表失败: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
