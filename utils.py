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
