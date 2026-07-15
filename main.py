"""Command-line entry point for TradingView watchlist generation."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence


Job = tuple[str, Callable[[], object]]


def build_jobs(exchange: str, market: str) -> list[Job]:
    """Build jobs lazily so help and unsupported dependencies stay offline."""
    jobs: list[Job] = []

    if exchange in {"binance", "all"}:
        if market in {"futures", "all"}:
            from exchange_ticket.bn.bnfutures import get_futures_pairs

            jobs.append(("Binance futures", get_futures_pairs))
        if market in {"spot", "all"}:
            from exchange_ticket.bn.bnspots import get_spot_pairs

            jobs.append(("Binance spot", get_spot_pairs))

    if exchange in {"bybit", "all"}:
        if market in {"futures", "all"}:
            from exchange_ticket.bybit.bybitfutures import get_futures_pairs

            jobs.append(("Bybit futures", get_futures_pairs))
        if market in {"spot", "all"}:
            from exchange_ticket.bybit.bybitspot import get_spot_pairs

            jobs.append(("Bybit spot", get_spot_pairs))

    if exchange in {"bitget", "all"} and market in {"spot", "all"}:
        from exchange_ticket.bitget.bitget import get_spot_pairs

        jobs.append(("Bitget spot", get_spot_pairs))

    if exchange in {"okx", "all"} and market in {"spot", "all"}:
        from exchange_ticket.okx.okx import get_spot_pairs

        jobs.append(("OKX spot", get_spot_pairs))

    return jobs


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate TradingView exchange watchlists")
    parser.add_argument(
        "--exchange",
        choices=("binance", "bybit", "bitget", "okx", "all"),
        default="binance",
        help="exchange to export (default: binance)",
    )
    parser.add_argument(
        "--market",
        choices=("spot", "futures", "all"),
        default="all",
        help="market type to export (default: all)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    jobs = build_jobs(args.exchange, args.market)
    if not jobs:
        print(f"No {args.market} exporter is available for {args.exchange}.")
        return 2

    failed = 0
    for label, job in jobs:
        print(f"[{label}]")
        try:
            result = job()
        except Exception as exc:
            failed += 1
            print(f"Export failed: {exc}")
            continue
        if result is None:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
