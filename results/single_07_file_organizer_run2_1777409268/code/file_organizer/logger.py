"""JSON operation logger for undo support."""

import json
import os
import os.path
from datetime import datetime, timezone
from typing import Optional


LOG_FILENAME = ".file_organizer_log.json"


def default_log_path(target_dir: str) -> str:
    """Return the path to the JSON log file inside *target_dir*."""
    return os.path.join(target_dir, LOG_FILENAME)


def read_log(log_path: str) -> list[dict]:
    """Read the log file, return list of operation dicts (newest first)."""
    if not os.path.isfile(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"⚠  Could not read log file '{log_path}': {exc}")
        return []
    if isinstance(data, list):
        return data
    return []


def write_log(log_path: str, operations: list[dict]) -> None:
    """Overwrite log file with the given list of operations."""
    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            json.dump(operations, fh, indent=2, default=str)
    except OSError as exc:
        print(f"⚠  Could not write log file '{log_path}': {exc}")


def append_operations(
    log_path: str,
    new_ops: list[dict],
    *,
    max_entries: int = 10_000,
) -> None:
    """Append *new_ops* to the existing log file.

    The log is kept as a flat JSON array (most recent entry first).
    *max_entries* caps the total number of stored operations to prevent
    unbounded growth.
    """
    existing = read_log(log_path)
    # Prepend as a new "session" entry
    session = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operations": new_ops,
    }
    existing.insert(0, session)
    if len(existing) > max_entries:
        existing = existing[:max_entries]
    write_log(log_path, existing)
