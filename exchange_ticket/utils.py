from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PACKAGE_ROOT / "ticket"


def unique_lines(lines: Iterable[str]) -> list[str]:
    """Return non-empty lines in input order without duplicates."""
    return list(dict.fromkeys(line.strip() for line in lines if line and line.strip()))


def optional_float(value: object, *, multiplier: float = 1) -> float | None:
    if value is None:
        return None
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return None


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def save_lines(
    lines: Iterable[str],
    filename: str,
    folder: str | Path = DEFAULT_OUTPUT_DIR,
    empty_message: str | None = None,
    success_message: str | None = None,
) -> Path | None:
    """Write one line per item and create the output folder when needed."""
    items = unique_lines(lines)
    if not items:
        output_path = Path(folder) / filename
        if output_path.exists():
            output_path.unlink()
        if empty_message:
            print(empty_message)
        return None

    output_path = Path(folder) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(items) + "\n", encoding="utf-8")

    if success_message:
        print(success_message.format(count=len(items), path=output_path))

    return output_path


def save_chunked_lines(
    lines: Iterable[str],
    filename: str,
    folder: str | Path = DEFAULT_OUTPUT_DIR,
    chunk_size: int = 500,
    empty_message: str | None = None,
    success_message: str | None = None,
) -> list[Path]:
    """Write watchlist files with a maximum number of lines per file."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    items = unique_lines(lines)
    output_dir = Path(folder)
    base_path = output_dir / filename
    if not items:
        remove_chunked_files(base_path)
        if empty_message:
            print(empty_message)
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = base_path.stem
    suffix = base_path.suffix
    paths = []

    for index in range(0, len(items), chunk_size):
        chunk = items[index : index + chunk_size]
        part_number = index // chunk_size + 1
        output_path = base_path if part_number == 1 else output_dir / f"{stem}_{part_number}{suffix}"
        output_path.write_text("\n".join(chunk) + "\n", encoding="utf-8")
        paths.append(output_path)

    remove_chunked_files(base_path, keep=set(paths))

    if success_message:
        file_list = ", ".join(str(path) for path in paths)
        print(success_message.format(count=len(items), files=len(paths), path=file_list))

    return paths


def remove_chunked_files(base_path: Path, *, keep: set[Path] | None = None) -> None:
    """Remove an export and its numbered parts, optionally preserving current files."""
    keep = keep or set()
    candidates = [base_path]
    if base_path.parent.exists():
        candidates.extend(
            path
            for path in base_path.parent.glob(f"{base_path.stem}_*{base_path.suffix}")
            if path.stem.removeprefix(f"{base_path.stem}_").isdigit()
        )
    for path in candidates:
        if path not in keep and path.exists():
            path.unlink()
