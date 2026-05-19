#!/usr/bin/env python3
"""A command-line todo manager with JSON persistence, filtering, sorting, and search."""

import json
import os
import shlex
import uuid
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Task:
    """A single task with title, priority, completion status, and timestamp."""

    PRIORITIES = ("low", "medium", "high")

    def __init__(
        self,
        title: str,
        priority: str = "medium",
        completed: bool = False,
        task_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.title = title
        self.priority = priority if priority in self.PRIORITIES else "medium"
        self.completed = completed
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            title=d["title"],
            priority=d.get("priority", "medium"),
            completed=d.get("completed", False),
            task_id=d.get("id"),
            created_at=d.get("created_at"),
        )

    @property
    def created_datetime(self) -> datetime:
        return datetime.fromisoformat(self.created_at)

    @property
    def status_str(self) -> str:
        return "Done" if self.completed else "Active"

    def __str__(self) -> str:
        created = self.created_datetime.strftime("%Y-%m-%d %H:%M")
        return (
            f"[{self.id}] {self.title}\n"
            f"     Priority: {self.priority.capitalize()} | "
            f"Status: {self.status_str} | Created: {created}"
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

STORAGE_FILE = "tasks.json"


def load_tasks() -> list[Task]:
    """Load tasks from the JSON file. Returns empty list if file missing or corrupt."""
    if not os.path.exists(STORAGE_FILE):
        return []
    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [Task.from_dict(item) for item in data]
    except (json.JSONDecodeError, KeyError):
        print("Warning: Could not parse tasks.json. Starting with empty task list.")
        return []


def save_tasks(tasks: list[Task]) -> None:
    """Save all tasks to the JSON file."""
    with open(STORAGE_FILE, "w") as f:
        json.dump([t.to_dict() for t in tasks], f, indent=2)


# ---------------------------------------------------------------------------
# Task store (in-memory with auto-save)
# ---------------------------------------------------------------------------

class TaskStore:
    """Holds tasks in memory and persists to JSON after every mutation."""

    def __init__(self):
        self.tasks: list[Task] = load_tasks()

    def _save(self) -> None:
        save_tasks(self.tasks)

    # -- CRUD --

    def add(self, title: str, priority: str = "medium") -> Task:
        task = Task(title=title, priority=priority)
        self.tasks.append(task)
        self._save()
        return task

    def get(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def mark_done(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        task.completed = True
        self._save()
        return True

    def delete(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        self.tasks.remove(task)
        self._save()
        return True

    # -- Query helpers --

    @staticmethod
    def _priority_order(p: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(p, 1)

    def list_tasks(
        self,
        status_filter: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[Task]:
        """Return filtered & sorted tasks.  status_filter: 'active' | 'done' | None."""
        result = list(self.tasks)

        if status_filter == "active":
            result = [t for t in result if not t.completed]
        elif status_filter == "done":
            result = [t for t in result if t.completed]

        if sort_by == "priority":
            result.sort(key=lambda t: self._priority_order(t.priority))
        elif sort_by == "date":
            result.sort(key=lambda t: t.created_datetime)

        return result

    def search(self, keyword: str) -> list[Task]:
        kw = keyword.lower()
        return [t for t in self.tasks if kw in t.title.lower()]


# ---------------------------------------------------------------------------
# REPL / Command parsing
# ---------------------------------------------------------------------------

def print_help() -> None:
    print(
        """
Available commands:

  add <title> [--priority low|medium|high]
      Add a new task.  Priority defaults to 'medium'.

  list [active|done] [--sort priority|date]
      List tasks.  Optionally filter by status and/or sort.
      Examples:  list
                 list active
                 list done --sort priority
                 list --sort date

  done <id>
      Mark a task as complete by its ID.

  delete <id>
      Delete a task by its ID.

  search <keyword>
      Search for tasks whose title contains the keyword (case-insensitive).

  help
      Show this help message.

  quit | exit
      Exit the program.
"""
    )


def parse_list_args(parts: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Parse 'list [active|done] [--sort priority|date]' and return (status, sort)."""
    status: Optional[str] = None
    sort: Optional[str] = None

    i = 0
    while i < len(parts):
        arg = parts[i]
        if arg in ("active", "done"):
            status = arg
        elif arg == "--sort":
            i += 1
            if i < len(parts) and parts[i] in ("priority", "date"):
                sort = parts[i]
            else:
                print("Error: --sort requires 'priority' or 'date'.")
                return None, None
        else:
            print(f"Error: Unexpected argument to 'list': {arg}")
            return None, None
        i += 1

    return status, sort


def parse_add_args(parts: list[str]) -> tuple[Optional[str], str]:
    """Parse 'add <title> [--priority low|medium|high]' and return (title, priority)."""
    title_parts = []
    priority = "medium"
    skip_next = False

    i = 0
    while i < len(parts):
        if skip_next:
            skip_next = False
            i += 1
            continue
        arg = parts[i]
        if arg == "--priority":
            i += 1
            if i < len(parts) and parts[i] in Task.PRIORITIES:
                priority = parts[i]
            else:
                print(f"Error: --priority requires one of: {', '.join(Task.PRIORITIES)}")
                return None, "medium"
        elif arg.startswith("--priority="):
            val = arg.split("=", 1)[1]
            if val in Task.PRIORITIES:
                priority = val
            else:
                print(f"Error: Invalid priority '{val}'. Use: {', '.join(Task.PRIORITIES)}")
                return None, "medium"
        else:
            title_parts.append(arg)
        i += 1

    title = " ".join(title_parts).strip()
    if not title:
        print("Error: Task title cannot be empty.")
        return None, "medium"

    return title, priority


def cmd_add(store: TaskStore, parts: list[str]) -> None:
    title, priority = parse_add_args(parts)
    if title is None:
        return
    task = store.add(title, priority)
    print(f"Added task: [{task.id}] {task.title} (Priority: {task.priority.capitalize()})")


def cmd_list(store: TaskStore, parts: list[str]) -> None:
    status, sort = parse_list_args(parts)
    # If parse_list_args detected an error it already printed a message
    # and returned (None, None).  Only bail out early when there were
    # actually arguments that caused the error (not just an empty `list`).
    if status is None and sort is None and parts:
        return
    tasks = store.list_tasks(status_filter=status, sort_by=sort)
    if not tasks:
        print("No tasks found.")
        return

    print(f"\n{'─' * 60}")
    for t in tasks:
        print(t)
        print(f"{'─' * 60}")
    print(f"Total: {len(tasks)} task(s)\n")


def cmd_done(store: TaskStore, parts: list[str]) -> None:
    if not parts:
        print("Error: 'done' requires a task ID.  Usage: done <id>")
        return
    task_id = parts[0]
    if store.mark_done(task_id):
        task = store.get(task_id)
        print(f"Marked as done: [{task_id}] {task.title if task else ''}")
    else:
        print(f"Error: No task found with ID '{task_id}'.")


def cmd_delete(store: TaskStore, parts: list[str]) -> None:
    if not parts:
        print("Error: 'delete' requires a task ID.  Usage: delete <id>")
        return
    task_id = parts[0]
    if store.delete(task_id):
        print(f"Deleted task [{task_id}].")
    else:
        print(f"Error: No task found with ID '{task_id}'.")


def cmd_search(store: TaskStore, parts: list[str]) -> None:
    if not parts:
        print("Error: 'search' requires a keyword.  Usage: search <keyword>")
        return
    keyword = " ".join(parts)
    results = store.search(keyword)
    if not results:
        print(f"No tasks matching '{keyword}'.")
        return

    print(f"\nSearch results for '{keyword}':")
    print(f"{'─' * 60}")
    for t in results:
        print(t)
        print(f"{'─' * 60}")
    print(f"Found: {len(results)} task(s)\n")


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------

COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "done": cmd_done,
    "delete": cmd_delete,
    "search": cmd_search,
}


def repl() -> None:
    store = TaskStore()
    print("Todo Manager — type 'help' for commands, 'quit' to exit.")
    print(f"Loaded {len(store.tasks)} task(s) from {STORAGE_FILE}.")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        # Split while respecting quoted strings
        try:
            parts = shlex.split(raw)
        except ValueError as e:
            print(f"Error parsing command: {e}")
            continue

        if not parts:
            continue

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit"):
            print("Goodbye!")
            break
        elif cmd == "help":
            print_help()
        elif cmd in COMMANDS:
            try:
                COMMANDS[cmd](store, args)
            except Exception as e:
                print(f"Unexpected error: {e}")
        else:
            print(f"Unknown command: '{cmd}'. Type 'help' to see available commands.")


if __name__ == "__main__":
    repl()
