import json
from datetime import datetime, timezone
from pathlib import Path


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return path


def write_breakouts_json(path, breakouts, summary):
    return write_json(
        path,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "date": datetime.now(timezone.utc).date().isoformat(),
            "summary": summary,
            "breakouts": breakouts,
        },
    )


def write_snapshot_json(path, records):
    return write_json(
        path,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": records,
        },
    )
