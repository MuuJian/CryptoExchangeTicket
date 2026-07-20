"""File-output and value-conversion helpers shared across the project."""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "exchange_ticket" / "ticket"


def unique_lines(lines: Iterable[str]) -> list[str]:
    """Return non-empty lines in input order without duplicates."""
    return list(dict.fromkeys(line.strip() for line in lines if line and line.strip()))


def optional_float(value: object, *, multiplier: float = 1) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value) * multiplier
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, str):
        candidate = value.strip()
        digits = candidate[1:] if candidate[:1] in {"+", "-"} else candidate
        if not digits or not digits.isdecimal():
            return None
        return int(candidate)

    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        return parsed if value == parsed else None
    except Exception:
        return None


def write_text_atomic(path: Path, text: str) -> None:
    """Write UTF-8 text without exposing a partially written destination."""
    temp_path = _stage_text(path, text)
    try:
        temp_path.replace(path)
    finally:
        _remove_temp_file(temp_path)


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
    outputs = []

    for index in range(0, len(items), chunk_size):
        chunk = items[index : index + chunk_size]
        part_number = index // chunk_size + 1
        output_path = base_path if part_number == 1 else output_dir / f"{stem}_{part_number}{suffix}"
        outputs.append((output_path, "\n".join(chunk) + "\n"))

    staged = []
    try:
        for output_path, text in outputs:
            staged.append((_stage_text(output_path, text), output_path))
        for temp_path, output_path in staged:
            temp_path.replace(output_path)
    finally:
        for temp_path, _ in staged:
            _remove_temp_file(temp_path)

    paths = [output_path for output_path, _ in outputs]
    remove_chunked_files(base_path, keep=set(paths))

    if success_message:
        file_list = ", ".join(str(path) for path in paths)
        print(success_message.format(count=len(items), files=len(paths), path=file_list))

    return paths


def _stage_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
    except BaseException:
        _remove_temp_file(temp_path)
        raise
    return temp_path


def _remove_temp_file(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


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
