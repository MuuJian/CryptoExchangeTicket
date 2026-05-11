from pathlib import Path


DEFAULT_OUTPUT_DIR = Path("ticket")


def save_lines(lines, filename, folder=DEFAULT_OUTPUT_DIR, empty_message=None, success_message=None):
    """Write one line per item and create the output folder when needed."""
    items = list(lines)
    if not items:
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
    lines,
    filename,
    folder=DEFAULT_OUTPUT_DIR,
    chunk_size=500,
    empty_message=None,
    success_message=None,
):
    """Write watchlist files with a maximum number of lines per file."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    items = list(lines)
    if not items:
        if empty_message:
            print(empty_message)
        return []

    output_dir = Path(folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_path = output_dir / filename
    stem = base_path.stem
    suffix = base_path.suffix
    paths = []

    for index in range(0, len(items), chunk_size):
        chunk = items[index:index + chunk_size]
        part_number = index // chunk_size + 1
        output_path = base_path if part_number == 1 else output_dir / f"{stem}_{part_number}{suffix}"
        output_path.write_text("\n".join(chunk) + "\n", encoding="utf-8")
        paths.append(output_path)

    # Remove stale chunk files from previous longer exports.
    next_part = len(paths) + 1
    while True:
        stale_path = output_dir / f"{stem}_{next_part}{suffix}"
        if not stale_path.exists():
            break
        stale_path.unlink()
        next_part += 1

    if success_message:
        file_list = ", ".join(str(path) for path in paths)
        print(success_message.format(count=len(items), files=len(paths), path=file_list))

    return paths
