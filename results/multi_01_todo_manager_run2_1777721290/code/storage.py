"""JSON persistence layer for tasks."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any

from task import Task


def _task_to_dict(task: Task) -> dict[str, Any]:
    """Convert a Task to a JSON-serialisable dict."""
    d = asdict(task)
    d["created_at"] = task.created_at.isoformat()
    return d


def _dict_to_task(d: dict[str, Any]) -> Task:
    """Convert a dict from JSON back into a Task."""
    return Task(
        id=d["id"],
        title=d["title"],
        priority=d["priority"],
        completed=d["completed"],
        created_at=datetime.fromisoformat(d["created_at"]),
    )


def load_tasks(filepath: str) -> list[Task]:
    """Load tasks from a JSON file. Returns empty list if file missing or corrupt."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"Warning: {filepath} is not a valid task list. Starting fresh.")
            return []
        return [_dict_to_task(item) for item in data]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Warning: could not load {filepath}: {exc}. Starting fresh.")
        return []


def save_tasks(filepath: str, tasks: list[Task]) -> None:
    """Save tasks to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([_task_to_dict(t) for t in tasks], f, indent=2, ensure_ascii=False)
        f.write("\n")
