"""Data model, business logic, and persistence for the todo manager."""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from typing import Optional


@dataclass
class Task:
    """A single task with all relevant fields."""
    id: int
    title: str
    priority: str = 'medium'
    completed: bool = False
    created_at: str = ''

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class TaskManager:
    """Manages a collection of tasks with persistence to a JSON file."""

    PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

    def __init__(self):
        self.tasks: list[Task] = []
        self.next_id: int = 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def load(self, filename: str) -> None:
        """Read tasks from a JSON file.  Does nothing if the file is missing."""
        if not os.path.isfile(filename):
            return

        with open(filename, 'r', encoding='utf-8') as fh:
            data = json.load(fh)

        self.tasks = []
        max_id = 0
        for item in data:
            task = Task(
                id=item['id'],
                title=item['title'],
                priority=item.get('priority', 'medium'),
                completed=item.get('completed', False),
                created_at=item.get('created_at', ''),
            )
            self.tasks.append(task)
            if task.id > max_id:
                max_id = task.id

        self.next_id = max_id + 1

    def save(self, filename: str) -> None:
        """Write the current task list to a JSON file."""
        data = [asdict(task) for task in self.tasks]
        with open(filename, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def add_task(self, title: str, priority: str = 'medium') -> Task:
        """Create a new task, persist, and return it."""
        if priority not in self.PRIORITY_ORDER:
            raise ValueError(f"Invalid priority '{priority}'. Use low, medium, or high.")

        task = Task(id=self.next_id, title=title, priority=priority)
        self.next_id += 1
        self.tasks.append(task)
        return task

    def mark_complete(self, task_id: int) -> Task:
        """Mark a task as completed by its ID.  Raises ValueError if not found."""
        task = self._find_by_id(task_id)
        task.completed = True
        return task

    def delete_task(self, task_id: int) -> Task:
        """Remove a task by its ID.  Raises ValueError if not found."""
        task = self._find_by_id(task_id)
        self.tasks.remove(task)
        return task

    def list_tasks(
        self,
        status: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[Task]:
        """
        Return (optionally filtered and sorted) tasks.

        *status*: 'active' (not done), 'done' (completed), or None (all).
        *sort_by*: 'priority' or 'date'.
        """
        # --- filter ---
        if status == 'active':
            result = [t for t in self.tasks if not t.completed]
        elif status == 'done':
            result = [t for t in self.tasks if t.completed]
        else:
            result = list(self.tasks)

        # --- sort ---
        if sort_by == 'priority':
            result.sort(key=lambda t: (self.PRIORITY_ORDER.get(t.priority, 2), t.created_at))
        elif sort_by == 'date':
            result.sort(key=lambda t: t.created_at)

        return result

    def search_tasks(self, keyword: str) -> list[Task]:
        """Return tasks whose title contains *keyword* (case-insensitive)."""
        kw = keyword.lower()
        return [t for t in self.tasks if kw in t.title.lower()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_by_id(self, task_id: int) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task with ID {task_id} not found.")
