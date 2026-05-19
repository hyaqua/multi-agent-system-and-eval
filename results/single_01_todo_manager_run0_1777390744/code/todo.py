#!/usr/bin/env python3
"""
Command-line Todo Manager

A REPL-based task manager with persistence via JSON.
Tasks have a title, priority (low/medium/high), completion status, and creation timestamp.

Commands:
    add <title> [--priority <low|medium|high>]   Add a new task
    list                                          List all tasks
    list active                                   List only active (incomplete) tasks
    list done                                     List only completed tasks
    list --sort priority                          List all tasks sorted by priority
    list --sort date                              List all tasks sorted by creation date
    done <id>                                     Mark a task as complete
    delete <id>                                   Delete a task
    search <keyword>                              Search tasks by keyword in title
    help                                          Show this help message
    quit / exit                                   Exit the program
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# File path for persistence
# ---------------------------------------------------------------------------
TASKS_FILE = os.path.join(os.getcwd(), "tasks.json")

# Priority ordering for sorting (lower index = higher priority)
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Task class
# ---------------------------------------------------------------------------
class Task:
    """A single todo task."""

    def __init__(
        self,
        task_id: int,
        title: str,
        priority: str = "medium",
        completed: bool = False,
        created_at: Optional[str] = None,
    ):
        self.id = task_id
        self.title = title
        self.priority = priority if priority in PRIORITY_ORDER else "medium"
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat(sep=" ", timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "Task":
        return Task(
            task_id=data["id"],
            title=data["title"],
            priority=data.get("priority", "medium"),
            completed=data.get("completed", False),
            created_at=data.get("created_at"),
        )

    def status_str(self) -> str:
        return "✓ Done" if self.completed else "○ Active"

    def __repr__(self):
        return f"Task(id={self.id}, title={self.title!r}, priority={self.priority}, completed={self.completed})"


# ---------------------------------------------------------------------------
# TaskManager class
# ---------------------------------------------------------------------------
class TaskManager:
    """Manages the collection of tasks with persistence."""

    def __init__(self, filepath: str = TASKS_FILE):
        self.filepath = filepath
        self._tasks: dict[int, Task] = {}
        self._next_id: int = 1
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load tasks from JSON file if it exists."""
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    task = Task.from_dict(item)
                    self._tasks[task.id] = task
                    if task.id >= self._next_id:
                        self._next_id = task.id + 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: could not load tasks file: {e}")

    def _save(self) -> None:
        """Save tasks to JSON file."""
        try:
            data = [t.to_dict() for t in self._tasks.values()]
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error: could not save tasks: {e}")

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def add(self, title: str, priority: str = "medium") -> Task:
        """Add a new task.  Returns the created task."""
        if priority not in PRIORITY_ORDER:
            print(f"Invalid priority '{priority}'. Using 'medium'.")
            priority = "medium"
        task = Task(task_id=self._next_id, title=title, priority=priority)
        self._next_id += 1
        self._tasks[task.id] = task
        self._save()
        return task

    def delete(self, task_id: int) -> bool:
        """Delete a task by ID. Returns True if deleted, False if not found."""
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        self._save()
        return True

    def mark_done(self, task_id: int) -> bool:
        """Mark a task as complete. Returns True on success, False if not found."""
        if task_id not in self._tasks:
            return False
        task = self._tasks[task_id]
        if task.completed:
            # Already done — still return True but notify
            return True
        task.completed = True
        self._save()
        return True

    def get_all(self) -> list[Task]:
        """Return all tasks sorted by ID."""
        return sorted(self._tasks.values(), key=lambda t: t.id)

    def get_active(self) -> list[Task]:
        """Return only active (incomplete) tasks."""
        return [t for t in self.get_all() if not t.completed]

    def get_done(self) -> list[Task]:
        """Return only completed tasks."""
        return [t for t in self.get_all() if t.completed]

    def search(self, keyword: str) -> list[Task]:
        """Return tasks whose title contains the keyword (case-insensitive)."""
        kw = keyword.lower()
        return [t for t in self.get_all() if kw in t.title.lower()]

    def sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by priority (high → medium → low), then by ID."""
        return sorted(tasks, key=lambda t: (PRIORITY_ORDER.get(t.priority, 99), t.id))

    def sort_by_date(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by creation date (newest first), then by ID."""
        return sorted(tasks, key=lambda t: (t.created_at, t.id), reverse=True)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def print_tasks(tasks: list[Task]) -> None:
    """Pretty-print a list of tasks in a table-like format."""
    if not tasks:
        print("No tasks found.")
        return
    # Column widths
    header = f"{'ID':<6} {'Title':<30} {'Priority':<10} {'Status':<10} {'Created':<20}"
    print(header)
    print("-" * len(header))
    for t in tasks:
        title = t.title if len(t.title) <= 28 else t.title[:27] + "…"
        print(
            f"{t.id:<6} {title:<30} {t.priority:<10} {t.status_str():<10} {t.created_at:<20}"
        )


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------
def show_help() -> None:
    print(
        """
Available commands:

  add <title> [--priority <low|medium|high>]
      Add a new task. Priority defaults to 'medium'.

  list
      List all tasks.

  list active
      List only active (incomplete) tasks.

  list done
      List only completed tasks.

  list --sort priority
      List all tasks sorted by priority (high → medium → low).

  list --sort date
      List all tasks sorted by creation date (newest first).

  done <id>
      Mark a task as complete by its ID.

  delete <id>
      Delete a task by its ID.

  search <keyword>
      Search for tasks whose title contains the given keyword.

  help
      Show this help message.

  quit / exit
      Exit the program.
"""
    )


def parse_add_args(args: list[str]) -> tuple[str, str]:
    """Parse arguments for the 'add' command. Returns (title, priority)."""
    title_parts = []
    priority = "medium"
    i = 0
    while i < len(args):
        if args[i] == "--priority" and i + 1 < len(args):
            priority = args[i + 1].lower()
            i += 2
        else:
            title_parts.append(args[i])
            i += 1
    title = " ".join(title_parts)
    return title, priority


def parse_list_args(args: list[str]) -> tuple[str, str]:
    """
    Parse arguments for the 'list' command.
    Returns (filter_mode, sort_mode).
    filter_mode: 'all', 'active', 'done'
    sort_mode:   'none', 'priority', 'date'
    """
    filter_mode = "all"
    sort_mode = "none"

    for a in args:
        if a in ("active", "done"):
            filter_mode = a
        elif a == "--sort":
            pass  # handled by looking at next arg
        elif a == "priority":
            sort_mode = "priority"
        elif a == "date":
            sort_mode = "date"

    # Handle "--sort priority" / "--sort date" via index-based parsing
    i = 0
    while i < len(args):
        if args[i] == "--sort" and i + 1 < len(args):
            val = args[i + 1]
            if val in ("priority", "date"):
                sort_mode = val
            i += 2
        else:
            if args[i] in ("active", "done"):
                filter_mode = args[i]
            i += 1

    return filter_mode, sort_mode


def repl() -> None:
    """Run the main REPL loop."""
    manager = TaskManager()

    print("Todo Manager — type 'help' for available commands, 'quit' to exit.\n")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        command = parts[0].lower()
        args = parts[1:]

        # ------------------------------------------------------------------
        # help
        # ------------------------------------------------------------------
        if command == "help":
            show_help()

        # ------------------------------------------------------------------
        # quit / exit
        # ------------------------------------------------------------------
        elif command in ("quit", "exit"):
            print("Goodbye!")
            break

        # ------------------------------------------------------------------
        # add
        # ------------------------------------------------------------------
        elif command == "add":
            if not args:
                print("Error: 'add' requires a title. Usage: add <title> [--priority <low|medium|high>]")
                continue
            title, priority = parse_add_args(args)
            if not title:
                print("Error: task title cannot be empty.")
                continue
            if priority not in PRIORITY_ORDER:
                print(f"Error: invalid priority '{priority}'. Use low, medium, or high.")
                continue
            task = manager.add(title, priority)
            print(f"Added task #{task.id}: {task.title}  [{task.priority}]")

        # ------------------------------------------------------------------
        # list
        # ------------------------------------------------------------------
        elif command == "list":
            filter_mode, sort_mode = parse_list_args(args)

            # Fetch based on filter
            if filter_mode == "active":
                tasks = manager.get_active()
            elif filter_mode == "done":
                tasks = manager.get_done()
            else:
                tasks = manager.get_all()

            # Apply sorting
            if sort_mode == "priority":
                tasks = manager.sort_by_priority(tasks)
            elif sort_mode == "date":
                tasks = manager.sort_by_date(tasks)

            print_tasks(tasks)

        # ------------------------------------------------------------------
        # done
        # ------------------------------------------------------------------
        elif command == "done":
            if not args:
                print("Error: 'done' requires a task ID. Usage: done <id>")
                continue
            try:
                task_id = int(args[0])
            except ValueError:
                print(f"Error: invalid task ID '{args[0]}'. Must be a number.")
                continue
            if manager.mark_done(task_id):
                print(f"Task #{task_id} marked as complete.")
            else:
                print(f"Error: no task with ID {task_id}.")

        # ------------------------------------------------------------------
        # delete
        # ------------------------------------------------------------------
        elif command == "delete":
            if not args:
                print("Error: 'delete' requires a task ID. Usage: delete <id>")
                continue
            try:
                task_id = int(args[0])
            except ValueError:
                print(f"Error: invalid task ID '{args[0]}'. Must be a number.")
                continue
            if manager.delete(task_id):
                print(f"Task #{task_id} deleted.")
            else:
                print(f"Error: no task with ID {task_id}.")

        # ------------------------------------------------------------------
        # search
        # ------------------------------------------------------------------
        elif command == "search":
            if not args:
                print("Error: 'search' requires a keyword. Usage: search <keyword>")
                continue
            keyword = " ".join(args)
            results = manager.search(keyword)
            if results:
                print(f"Found {len(results)} task(s) matching '{keyword}':")
                print_tasks(results)
            else:
                print(f"No tasks found matching '{keyword}'.")

        # ------------------------------------------------------------------
        # unknown
        # ------------------------------------------------------------------
        else:
            print(f"Unknown command: '{command}'. Type 'help' to see available commands.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    repl()
