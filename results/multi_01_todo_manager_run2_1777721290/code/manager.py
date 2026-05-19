"""Core business logic: task CRUD, listing, filtering, sorting, searching."""

from datetime import datetime
from typing import Callable

from task import PRIORITY_ORDER, VALID_PRIORITIES, Task
import storage


class TaskNotFoundError(Exception):
    """Raised when a task ID does not exist."""


class Manager:
    """Holds the in-memory task list and persists after each mutation."""

    def __init__(self, filepath: str = "tasks.json") -> None:
        self._filepath = filepath
        self._tasks: list[Task] = storage.load_tasks(filepath)
        self._next_id = max((t.id for t in self._tasks), default=0) + 1

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------
    def _persist(self) -> None:
        storage.save_tasks(self._filepath, self._tasks)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_task(self, title: str, priority: str = "medium") -> Task:
        """Create a new task, persist, and return it."""
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Priority must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
            )
        task = Task(
            id=self._next_id,
            title=title,
            priority=priority,
            created_at=datetime.now(),
        )
        self._next_id += 1
        self._tasks.append(task)
        self._persist()
        return task

    def list_tasks(
        self, status: str | None = None, sort_by: str | None = None
    ) -> list[Task]:
        """Filter and sort tasks.

        *status* – 'active' (incomplete), 'done' (complete), or None (all).
        *sort_by* – 'priority' or 'date'; None means insertion order.
        """
        filtered: list[Task]

        if status == "active":
            filtered = [t for t in self._tasks if not t.completed]
        elif status == "done":
            filtered = [t for t in self._tasks if t.completed]
        else:
            filtered = list(self._tasks)

        if sort_by == "priority":
            key: Callable[[Task], int] = lambda t: PRIORITY_ORDER[t.priority]
            filtered = sorted(filtered, key=key)
        elif sort_by == "date":
            filtered = sorted(filtered, key=lambda t: t.created_at)
        elif sort_by is not None:
            raise ValueError(f"Unknown sort option: {sort_by}")

        return filtered

    def complete_task(self, task_id: int) -> Task:
        """Mark a task as done. Raises TaskNotFoundError if ID not found."""
        for i, t in enumerate(self._tasks):
            if t.id == task_id:
                # Replace with a completed copy
                new_t = Task(
                    id=t.id,
                    title=t.title,
                    priority=t.priority,
                    completed=True,
                    created_at=t.created_at,
                )
                self._tasks[i] = new_t
                self._persist()
                return new_t
        raise TaskNotFoundError(f"No task found with ID {task_id}")

    def delete_task(self, task_id: int) -> Task:
        """Remove a task by ID. Returns the deleted task. Raises TaskNotFoundError."""
        for i, t in enumerate(self._tasks):
            if t.id == task_id:
                del self._tasks[i]
                self._persist()
                return t
        raise TaskNotFoundError(f"No task found with ID {task_id}")

    def search_tasks(self, keyword: str) -> list[Task]:
        """Return tasks whose title contains *keyword* (case-insensitive)."""
        kw = keyword.lower()
        return [t for t in self._tasks if kw in t.title.lower()]
