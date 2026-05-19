"""JSON logging of file operations for undo support."""

import json
import datetime
from pathlib import Path
from typing import Any

LOG_FILENAME = '.file_organizer_log.json'


def load_log(target_dir: Path) -> dict[str, Any]:
    """Load the log file, returning a dict with 'runs' key."""
    log_path = target_dir / LOG_FILENAME
    if not log_path.exists():
        return {'runs': []}
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {'runs': []}
    if not isinstance(data, dict) or 'runs' not in data:
        return {'runs': []}
    return data


def save_log(target_dir: Path, data: dict[str, Any]) -> None:
    """Save the log data to the log file."""
    log_path = target_dir / LOG_FILENAME
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


def log_operations(
    target_dir: Path,
    operations: list[dict],
    strategy: str,
    dry_run: bool = False,
) -> None:
    """Append a run to the log file.

    Only logs actual (non-dry-run) operations.
    """
    if dry_run:
        return

    # Only log successful operations
    successful = []
    for op in operations:
        if op.get('success') and not op.get('dry_run'):
            successful.append({
                'source': str(op['source']),
                'destination': str(op['destination']),
                'category': op.get('category', ''),
            })

    if not successful:
        return

    log_data = load_log(target_dir)
    run = {
        'timestamp': datetime.datetime.now().isoformat(),
        'strategy': strategy,
        'operations': successful,
    }
    log_data['runs'].append(run)
    save_log(target_dir, log_data)


def get_last_run(target_dir: Path) -> dict | None:
    """Return the most recent run from the log, or None."""
    log_data = load_log(target_dir)
    runs = log_data.get('runs', [])
    if not runs:
        return None
    return runs[-1]


def pop_last_run(target_dir: Path) -> dict | None:
    """Remove and return the most recent run from the log."""
    log_data = load_log(target_dir)
    runs = log_data.get('runs', [])
    if not runs:
        return None
    last = runs.pop()
    save_log(target_dir, log_data)
    return last
