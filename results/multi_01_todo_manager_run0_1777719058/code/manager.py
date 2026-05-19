"""TaskManager: handles all task logic, file I/O, filtering, and sorting."""

from __future__ import annotations

import json
import os
from typing import Optional

from task import Task


PRIORITY_WEIGHT = {"high": 1, "medium": 2, "low": 3}

TASKS_FILE = "tasks.json"


class TaskManager:
    """Manages an in-memory list of Task objects backed by a JSON file."""

    def __init__(self, filepath: str = TASKS_FILE) -> None:
        self.filepath = filepath
        self.tasks: list[Task] = []
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load tasks from the JSON file. If the file is missing or corrupt, start fresh."""
        if not os.path.exists(self.filepath):
            self.tasks = []
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, list):
                self.tasks = [Task.from_dict(item) for item in raw]
            else:
                self.tasks = []
        except (json.JSONDecodeError, KeyError, TypeError):
            self.tasks = []

    def save(self) -> None:
        """Persist the current task list to JSON."""
        with open(self.filepath, "w", encoding="utf-8") as fh:
            json.dump([t.to_dict() for t in self.tasks], fh, indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_next_id(self) -> int:
        """Return the next available task ID (max existing + 1, or 1 if empty)."""
        if not self.tasks:
            return 1
        return max(t.id for t in self.tasks) + 1

    def _find_index(self, task_id: int) -> int:
        """Return the list index for a given task ID, or -1 if not found."""
        for i, t in enumerate(self.tasks):
            if t.id == task_id:
                return i
        return -1

    # ------------------------------------------------------------------
    # Core mutating operations
    # ------------------------------------------------------------------

    def add(self, title: str, priority: str = "medium") -> Task:
        """Add a new task with *title* and *priority*; save and return it."""
        priority = priority.lower()
        if priority not in PRIORITY_WEIGHT:
            priority = "medium"
        task = Task(
            id=self._get_next_id(),
            title=title,
            priority=priority,
        )
        self.tasks.append(task)
        self.save()
        return task

    def mark_done(self, task_id: int) -> Task | None:
        """Mark the task with *task_id* as completed. Returns the task or None."""
        idx = self._find_index(task_id)
        if idx == -1:
            return None
        self.tasks[idx].completed = True
        self.save()
        return self.tasks[idx]

    def delete(self, task_id: int) -> Task | None:
        """Delete the task with *task_id*. Returns the removed task or None."""
        idx = self._find_index(task_id)
        if idx == -1:
            return None
        removed = self.tasks.pop(idx)
        self.save()
        return removed

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_all(
        self,
        filter_status: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[Task]:
        """
        Return tasks with optional filtering and sorting.

        *filter_status*: 'active' (not completed), 'done' (completed), or None (all).
        *sort_by*: 'priority' (high → low) or 'date' (newest first).
        """
        tasks = list(self.tasks)

        # Filtering
        if filter_status == "active":
            tasks = [t for t in tasks if not t.completed]
        elif filter_status == "done":
            tasks = [t for t in tasks if t.completed]

        # Sorting
        if sort_by == "priority":
            tasks.sort(key=lambda t: PRIORITY_WEIGHT.get(t.priority.lower(), 2))
        elif sort_by == "date":
            tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks

    def search(self, keyword: str) -> list[Task]:
        """Return tasks whose title contains *keyword* (case-insensitive)."""
        kw = keyword.lower()
        return [t for t in self.tasks if kw in t.title.lower()]
