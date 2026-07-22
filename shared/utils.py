"""File-output and value-conversion helpers shared across the project."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from math import isfinite
from pathlib import Path
from stat import S_ISREG
from uuid import uuid4

try:
    import fcntl
except ImportError:  # Windows uses the in-process thread lock.
    fcntl = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "exchange_ticket" / "ticket"
MINIMUM_WATCHLIST_ITEMS = 10
MAX_WATCHLIST_REMOVAL_FRACTION = 0.2
_CHUNKED_WRITE_LOCK_FILENAME = ".watchlists.lock"
_CHUNKED_CONFIRMATION_FILENAME = ".watchlists.pending"
_RESERVED_CHUNKED_FILENAMES = frozenset(
    {
        _CHUNKED_WRITE_LOCK_FILENAME.casefold(),
        _CHUNKED_CONFIRMATION_FILENAME.casefold(),
    }
)
_CHUNKED_WRITE_LOCK = threading.Lock()


class _SuspiciousRemovalError(ValueError):
    """A structurally valid update removes too much to accept once."""


def unique_lines(lines: Iterable[str]) -> list[str]:
    """Return non-empty lines in input order without duplicates."""
    items = []
    for line in lines:
        if not isinstance(line, str):
            raise TypeError("lines must contain strings")
        item = line.strip()
        if not item:
            continue
        if "\n" in item or "\r" in item:
            raise ValueError("lines must not contain embedded newlines")
        items.append(item)
    return list(dict.fromkeys(items))


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
        try:
            return int(candidate)
        except (ValueError, OverflowError):
            return None

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
    _regular_file_exists(path)
    temp_path = _stage_text(path, text)
    try:
        _regular_file_exists(path)
        temp_path.replace(path)
    finally:
        _remove_temp_file(temp_path)


def save_chunked_line_groups(
    groups: Mapping[str | Path, Iterable[str]],
    *,
    folder: str | Path = DEFAULT_OUTPUT_DIR,
    chunk_size: int = 500,
    validate_updates: bool = False,
) -> dict[str, list[Path]]:
    """Serialize concurrent writers and transactionally replace chunked lists.

    When requested, non-empty groups are revalidated against the latest files
    after the output lock is acquired.
    """
    _validate_chunk_size(chunk_size)
    if not isinstance(validate_updates, bool):
        raise ValueError("validate_updates must be a boolean")
    output_dir = Path(folder)
    normalized_groups: dict[str, list[str]] = {}
    normalized_names: set[str] = set()

    for filename, lines in groups.items():
        filename_path = _plain_filename(filename)
        normalized_name = filename_path.name.casefold()
        if normalized_name in _RESERVED_CHUNKED_FILENAMES:
            raise ValueError(f"reserved filename: {filename_path.name}")
        if normalized_name in normalized_names:
            raise ValueError(f"duplicate filename: {filename_path.name}")
        normalized_names.add(normalized_name)
        normalized_groups[filename_path.name] = unique_lines(lines)

    _validate_group_filenames(normalized_groups)
    if not normalized_groups:
        return {}

    with _chunked_output_lock(output_dir):
        confirmation_path = output_dir / _CHUNKED_CONFIRMATION_FILENAME
        confirmed_update = False
        if validate_updates:
            fingerprint = _watchlist_fingerprint(normalized_groups)
            confirmed_update = (
                _read_watchlist_confirmation(confirmation_path) == fingerprint
            )
            try:
                for filename, items in normalized_groups.items():
                    if not items:
                        continue
                    validate_chunked_update(
                        items,
                        output_dir / filename,
                        allow_large_removal=confirmed_update,
                    )
            except _SuspiciousRemovalError as exc:
                if not confirmed_update:
                    write_text_atomic(confirmation_path, fingerprint + "\n")
                    raise _SuspiciousRemovalError(
                        f"{exc}; repeat the same complete update to confirm"
                    ) from exc
                raise
            except ValueError:
                _remove_confirmation_file(confirmation_path)
                raise
            else:
                if not confirmed_update:
                    _remove_confirmation_file(confirmation_path)

        outputs: list[tuple[Path, str]] = []
        paths_by_filename: dict[str, list[Path]] = {}
        stale_paths: set[Path] = set()
        output_paths: set[Path] = set()

        for filename, items in normalized_groups.items():
            base_path = output_dir / filename
            group_outputs = _chunked_outputs(items, base_path, chunk_size)
            group_paths = [path for path, _ in group_outputs]
            collisions = output_paths.intersection(group_paths)
            if collisions:
                names = ", ".join(sorted(path.name for path in collisions))
                raise ValueError(f"chunked output filenames overlap: {names}")

            outputs.extend(group_outputs)
            output_paths.update(group_paths)
            paths_by_filename[filename] = group_paths
            stale_paths.update(set(_chunked_files(base_path)) - set(group_paths))

        stale_paths.difference_update(output_paths)
        if validate_updates:
            stale_paths.add(confirmation_path)
        _commit_text_files(outputs, stale_paths)
        return paths_by_filename


@contextmanager
def _chunked_output_lock(output_dir: Path):
    """Hold a thread lock and, where available, an inter-process file lock."""
    with _CHUNKED_WRITE_LOCK:
        output_dir.mkdir(parents=True, exist_ok=True)
        if fcntl is None:
            yield
            return

        lock_path = output_dir / _CHUNKED_WRITE_LOCK_FILENAME
        _regular_file_exists(lock_path)
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield


def _plain_filename(filename: str | Path) -> Path:
    filename_path = Path(filename)
    if filename_path.parent != Path(".") or filename_path.name in {"", ".", ".."}:
        raise ValueError("filename must be a plain file name")
    return filename_path


def _validate_chunk_size(chunk_size: int) -> None:
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ValueError("chunk_size must be a positive integer")


def _validate_group_filenames(groups: Mapping[str, object]) -> None:
    filenames = [Path(filename) for filename in groups]
    for base_path in filenames:
        prefix = f"{base_path.stem.casefold()}_"
        suffix = base_path.suffix.casefold()
        for other_path in filenames:
            if other_path == base_path or other_path.suffix.casefold() != suffix:
                continue
            other_stem = other_path.stem.casefold()
            if (
                other_stem.startswith(prefix)
                and _is_chunk_part(other_stem.removeprefix(prefix))
            ):
                raise ValueError(
                    f"{other_path.name} overlaps numbered chunks of {base_path.name}"
                )


def _chunked_outputs(
    items: list[str],
    base_path: Path,
    chunk_size: int,
) -> list[tuple[Path, str]]:
    outputs = []
    for index in range(0, len(items), chunk_size):
        chunk = items[index : index + chunk_size]
        part_number = index // chunk_size + 1
        output_path = (
            base_path
            if part_number == 1
            else base_path.with_name(
                f"{base_path.stem}_{part_number}{base_path.suffix}"
            )
        )
        outputs.append((output_path, "\n".join(chunk) + "\n"))
    return outputs


def _commit_text_files(
    outputs: list[tuple[Path, str]],
    stale_paths: set[Path],
) -> None:
    """Commit prepared files and restore every old path if a step fails."""
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    created_paths: set[Path] = set()
    preserve_backups = False
    output_paths = {path for path, _ in outputs}

    try:
        for output_path, text in outputs:
            staged.append((_stage_text(output_path, text), output_path))

        affected_paths = sorted(output_paths | stale_paths, key=str)
        for path in affected_paths:
            if _regular_file_exists(path):
                backups.append((_stage_bytes(path), path))
            elif path in output_paths:
                created_paths.add(path)

        try:
            for temp_path, output_path in staged:
                _regular_file_exists(output_path)
                temp_path.replace(output_path)
            for path in sorted(stale_paths, key=str):
                if _regular_file_exists(path):
                    path.unlink()
        except BaseException as commit_error:
            rollback_errors = _rollback_text_files(created_paths, backups)
            if rollback_errors:
                preserve_backups = True
                details = "; ".join(
                    f"{path}: {error}" for path, error in rollback_errors
                )
                recovery_files = ", ".join(
                    str(path) for path, _ in backups if path.exists()
                )
                raise OSError(
                    "chunked file commit and rollback failed: "
                    f"{details}; recovery files: {recovery_files or 'none'}"
                ) from commit_error
            raise
    finally:
        for temp_path, _ in staged:
            _remove_temp_file(temp_path)
        if not preserve_backups:
            for backup_path, _ in backups:
                _remove_temp_file(backup_path)


def _rollback_text_files(
    created_paths: set[Path],
    backups: list[tuple[Path, Path]],
) -> list[tuple[Path, BaseException]]:
    """Restore pre-commit paths and return every rollback failure."""
    errors = []
    for path in sorted(created_paths, key=str):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except BaseException as error:
            errors.append((path, error))

    for backup_path, output_path in backups:
        if not backup_path.exists():
            continue
        try:
            _regular_file_exists(output_path)
            backup_path.replace(output_path)
        except BaseException as error:
            errors.append((output_path, error))
    return errors


def validate_chunked_update(
    lines: Iterable[str],
    base_path: Path,
    *,
    minimum_count: int = MINIMUM_WATCHLIST_ITEMS,
    max_removal_fraction: float = MAX_WATCHLIST_REMOVAL_FRACTION,
    allow_large_removal: bool = False,
) -> list[str]:
    """Return normalized lines after rejecting suspicious item removal."""
    if (
        isinstance(minimum_count, bool)
        or not isinstance(minimum_count, int)
        or minimum_count <= 0
    ):
        raise ValueError("minimum_count must be a positive integer")
    if isinstance(max_removal_fraction, bool):
        raise ValueError("max_removal_fraction must be between 0 and 1")
    try:
        max_removal_fraction = float(max_removal_fraction)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("max_removal_fraction must be between 0 and 1") from exc
    if not isfinite(max_removal_fraction) or not 0 <= max_removal_fraction < 1:
        raise ValueError("max_removal_fraction must be between 0 and 1")
    if not isinstance(allow_large_removal, bool):
        raise ValueError("allow_large_removal must be a boolean")

    items = unique_lines(lines)
    if len(items) < minimum_count:
        raise ValueError(
            f"{base_path.name} only contains {len(items)} items; "
            f"expected at least {minimum_count}"
        )

    existing_items = unique_lines(
        line
        for path in _chunked_files(base_path)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    removed_items = set(existing_items) - set(items)
    if (
        existing_items
        and not allow_large_removal
        and len(removed_items) > len(existing_items) * max_removal_fraction
    ):
        raise _SuspiciousRemovalError(
            f"{base_path.name} would remove {len(removed_items)}/"
            f"{len(existing_items)} existing items"
        )
    return items


def _watchlist_fingerprint(groups: Mapping[str, list[str]]) -> str:
    payload = json.dumps(
        groups,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _read_watchlist_confirmation(path: Path) -> str | None:
    if not _regular_file_exists(path):
        return None
    with path.open("rb") as file:
        raw_value = file.read(129)
    if len(raw_value) > 128:
        return None
    try:
        return raw_value.decode("ascii").strip()
    except UnicodeDecodeError:
        return None


def _remove_confirmation_file(path: Path) -> None:
    if _regular_file_exists(path):
        path.unlink()


def _stage_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
    except BaseException:
        _remove_temp_file(temp_path)
        raise
    return temp_path


def _stage_bytes(path: Path) -> Path:
    if not _regular_file_exists(path):
        raise FileNotFoundError(path)
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.backup")
    try:
        temp_path.write_bytes(path.read_bytes())
    except BaseException:
        _remove_temp_file(temp_path)
        raise
    return temp_path


def _remove_temp_file(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _chunked_files(base_path: Path) -> list[Path]:
    """Find a base file and numeric chunks without interpreting glob syntax."""
    paths = [base_path] if _regular_file_exists(base_path) else []
    if not base_path.parent.exists():
        return paths

    numbered_prefix = f"{base_path.stem}_"
    numbered_paths: list[tuple[int, str, Path]] = []
    for path in base_path.parent.iterdir():
        if (
            path.suffix != base_path.suffix
            or not path.stem.startswith(numbered_prefix)
        ):
            continue
        part_number = path.stem[len(numbered_prefix) :]
        if not _is_chunk_part(part_number):
            continue
        _regular_file_exists(path)
        numbered_paths.append((len(part_number), part_number, path))

    numbered_paths.sort(key=lambda item: (item[0], item[1], item[2].name))
    return paths + [path for _, _, path in numbered_paths]


def _is_chunk_part(value: str) -> bool:
    return (
        value.isascii()
        and value.isdigit()
        and not value.startswith("0")
        and value != "1"
    )


def _regular_file_exists(path: Path) -> bool:
    """Return whether *path* is a regular file and reject other file types."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if not S_ISREG(mode):
        raise OSError(f"expected a regular file: {path}")
    return True
