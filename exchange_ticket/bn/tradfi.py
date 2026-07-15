"""Shared Binance TradFi classification and watchlist output."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from exchange_ticket.utils import DEFAULT_OUTPUT_DIR, save_chunked_lines, unique_lines


TRADFI_FILENAME = "binance_tradfi_pairs.txt"
LEGACY_MISSPELLED_FILENAME = "binance_tradifi_pairs.txt"

# Binance spot exchangeInfo does not expose a TradFi category. These exact
# base assets keep stock tokens separate without querying the futures API.
SPOT_TRADFI_BASE_ASSET_MAP = {
    "AMDB": "AMD",
    "CBRSB": "CBRS",
    "COINB": "COIN",
    "CRCLB": "CRCL",
    "DRAMB": "DRAM",
    "EWYB": "EWY",
    "GLWB": "GLW",
    "GOOGLB": "GOOGL",
    "INTCB": "INTC",
    "LITEB": "LITE",
    "METAB": "META",
    "MSFTB": "MSFT",
    "MSTRB": "MSTR",
    "MUB": "MU",
    "NBISB": "NBIS",
    "NVDAB": "NVDA",
    "PLTRB": "PLTR",
    "QCOMB": "QCOM",
    "QQQB": "QQQ",
    "SKHYB": "SKHY",
    "SNDKB": "SNDK",
    "SOXLB": "SOXL",
    "SPCXB": "SPCX",
    "SPYB": "SPY",
    "TSLAB": "TSLA",
    "WDCB": "WDC",
}


def is_spot_tradfi(base_asset: object) -> bool:
    return isinstance(base_asset, str) and base_asset in SPOT_TRADFI_BASE_ASSET_MAP


def update_tradfi_watchlist(
    pairs: Iterable[str],
    *,
    market: Literal["spot", "futures"],
    folder: str | Path = DEFAULT_OUTPUT_DIR,
    chunk_size: int = 500,
) -> list[Path]:
    """Replace one market section while preserving the other TradFi section."""
    output_dir = Path(folder)
    existing = _load_existing_pairs(output_dir)
    new_pairs = unique_lines(pairs)

    if market == "spot":
        spot_pairs = new_pairs
        futures_pairs = [pair for pair in existing if pair.endswith(".p")]
    else:
        spot_pairs = [pair for pair in existing if not pair.endswith(".p")]
        futures_pairs = new_pairs

    paths = save_chunked_lines(
        [*spot_pairs, *futures_pairs],
        TRADFI_FILENAME,
        folder=output_dir,
        chunk_size=chunk_size,
        empty_message="沒有找到 Binance TradFi 交易對，或資料為空。",
        success_message="成功將 {count} 個 TradFi 交易對拆成 {files} 個檔案: {path}",
    )
    if paths:
        _remove_legacy_files(output_dir)
    return paths


def _load_existing_pairs(output_dir: Path) -> list[str]:
    pairs = _load_chunked_lines(output_dir, TRADFI_FILENAME)
    if pairs:
        return pairs
    return _load_chunked_lines(output_dir, LEGACY_MISSPELLED_FILENAME)


def _load_chunked_lines(output_dir: Path, filename: str) -> list[str]:
    base_path = output_dir / filename
    paths = [base_path]
    part_number = 2
    while (part_path := output_dir / f"{base_path.stem}_{part_number}{base_path.suffix}").exists():
        paths.append(part_path)
        part_number += 1

    lines = []
    for path in paths:
        if path.exists():
            lines.extend(path.read_text(encoding="utf-8").splitlines())
    return unique_lines(lines)


def _remove_legacy_files(output_dir: Path) -> None:
    legacy_path = output_dir / LEGACY_MISSPELLED_FILENAME
    paths = [legacy_path]
    part_number = 2
    while (part_path := output_dir / f"{legacy_path.stem}_{part_number}{legacy_path.suffix}").exists():
        paths.append(part_path)
        part_number += 1

    for path in paths:
        if path.exists():
            path.unlink()
