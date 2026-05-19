#!/usr/bin/env python3
"""
Command-line Todo Manager

A REPL-based todo manager with persistent JSON storage.
Supports: add, list, done, delete, search, help, quit/exit.
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

DATA_FILE = "tasks.json"


class Task:
    """Represents a single todo task."""

    _next_id = 1

    def __init__(
        self,
        title: str,
        priority: str = "medium",
        completed: bool = False,
        created_at: Optional[str] = None,
        task_id: Optional[int] = None,
    ):
        if task_id is not None:
            self.id = task_id
            Task._next_id = max(Task._next_id, task_id + 1)
        else:
            self.id = Task._next_id
            Task._next_id += 1

        self.title = title
        self.priority = priority.lower() if priority else "medium"
        if self.priority not in ("low", "medium", "high"):
            self.priority = "medium"
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            title=data["title"],
            priority=data.get("priority", "medium"),
            completed=data.get("completed", False),
            created_at=data.get("created_at"),
            task_id=data["id"],
        )

    @classmethod
    def reset_id_counter(cls, max_id: int = 0):
        cls._next_id = max_id + 1

    def __repr__(self) -> str:
        status = "✓" if self.completed else "○"
        return f"[{self.id}] {status} {self.title} | priority: {self.priority} | {self.created_at}"


class TodoManager:
    """Manages tasks with persistence to a JSON file."""

    PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

    def __init__(self, filepath: str = DATA_FILE):
        self.filepath = filepath
        self.tasks: list[Task] = []
        self._load()

    def _load(self):
        """Load tasks from the JSON file if it exists."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                Task.reset_id_counter(0)
                max_id = 0
                for item in data:
                    task = Task.from_dict(item)
                    self.tasks.append(task)
                    if task.id > max_id:
                        max_id = task.id
                Task.reset_id_counter(max_id)
            except (json.JSONDecodeError, KeyError):
                print("Warning: Could not parse tasks file. Starting fresh.")
                self.tasks = []

    def _save(self):
        """Save tasks to the JSON file."""
        data = [task.to_dict() for task in self.tasks]
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, title: str, priority: str = "medium") -> Task:
        """Add a new task and persist."""
        task = Task(title=title, priority=priority)
        self.tasks.append(task)
        self._save()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """Find a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def mark_done(self, task_id: int) -> bool:
        """Mark a task as completed. Returns True on success."""
        task = self.get_task(task_id)
        if task is None:
            return False
        if task.completed:
            return False  # Already done
        task.completed = True
        self._save()
        return True

    def delete(self, task_id: int) -> bool:
        """Delete a task by ID. Returns True on success."""
        task = self.get_task(task_id)
        if task is None:
            return False
        self.tasks.remove(task)
        self._save()
        return True

    def list_all(
        self,
        status_filter: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> list[Task]:
        """
        Return tasks, optionally filtered and sorted.

        status_filter: None (all), 'active' (not completed), 'done' (completed)
        sort_by: None (by ID), 'priority' (high→low), 'date' (newest first)
        """
        tasks = list(self.tasks)

        # Filter
        if status_filter == "active":
            tasks = [t for t in tasks if not t.completed]
        elif status_filter == "done":
            tasks = [t for t in tasks if t.completed]

        # Sort
        if sort_by == "priority":
            tasks.sort(key=lambda t: self.PRIORITY_ORDER.get(t.priority, 99))
        elif sort_by == "date":
            tasks.sort(key=lambda t: t.created_at, reverse=True)
        else:
            tasks.sort(key=lambda t: t.id)

        return tasks

    def search(self, keyword: str) -> list[Task]:
        """Search tasks whose title contains the keyword (case-insensitive)."""
        kw = keyword.lower()
        return [t for t in self.tasks if kw in t.title.lower()]


def print_tasks(tasks: list[Task]):
    """Pretty-print a list of tasks."""
    if not tasks:
        print("  No tasks found.")
        return
    for task in tasks:
        print(f"  {task}")


def show_help():
    """Print available commands."""
    print("Available commands:")
    print("  add <title> [--priority low|medium|high]")
    print("      Add a new task. Default priority is 'medium'.")
    print("  list [active|done] [--sort priority|date]")
    print("      List tasks. Optional filter and sort.")
    print("  done <id>")
    print("      Mark a task as completed.")
    print("  delete <id>")
    print("      Delete a task.")
    print("  search <keyword>")
    print("      Search tasks by keyword in title.")
    print("  help")
    print("      Show this help message.")
    print("  quit | exit")
    print("      Exit the program.")


def parse_add_command(args: list[str]) -> tuple[str, str]:
    """Parse 'add' arguments. Returns (title, priority)."""
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


def parse_list_command(args: list[str]) -> tuple[Optional[str], Optional[str]]:
    """Parse 'list' arguments. Returns (status_filter, sort_by)."""
    status_filter = None
    sort_by = None

    i = 0
    while i < len(args):
        if args[i] == "active":
            status_filter = "active"
        elif args[i] == "done":
            status_filter = "done"
        elif args[i] == "--sort" and i + 1 < len(args):
            sort_by = args[i + 1].lower()
            i += 1
        i += 1

    # Validate sort_by
    if sort_by and sort_by not in ("priority", "date"):
        sort_by = None

    return status_filter, sort_by


def repl():
    """Main REPL loop."""
    manager = TodoManager()

    print("Todo Manager — type 'help' for available commands, 'quit' to exit.")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        parts = raw.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if command == "quit" or command == "exit":
            print("Goodbye!")
            break

        elif command == "help":
            show_help()

        elif command == "add":
            if not args:
                print("Error: 'add' requires a title. Usage: add <title> [--priority low|medium|high]")
                continue
            title, priority = parse_add_command(args)
            if not title:
                print("Error: Task title cannot be empty.")
                continue
            if priority not in ("low", "medium", "high"):
                print(f"Error: Invalid priority '{priority}'. Use low, medium, or high.")
                continue
            task = manager.add(title, priority)
            print(f"Added task [{task.id}]: {task.title} (priority: {task.priority})")

        elif command == "list":
            status_filter, sort_by = parse_list_command(args)
            tasks = manager.list_all(status_filter=status_filter, sort_by=sort_by)

            # Build description
            desc_parts = []
            if status_filter == "active":
                desc_parts.append("Active tasks")
            elif status_filter == "done":
                desc_parts.append("Completed tasks")
            else:
                desc_parts.append("All tasks")

            if sort_by:
                desc_parts.append(f"(sorted by {sort_by})")

            print(" ".join(desc_parts) + ":")
            print_tasks(tasks)

        elif command == "done":
            if not args:
                print("Error: 'done' requires a task ID. Usage: done <id>")
                continue
            try:
                task_id = int(args[0])
            except ValueError:
                print(f"Error: '{args[0]}' is not a valid task ID. IDs are numbers.")
                continue
            if manager.mark_done(task_id):
                task = manager.get_task(task_id)
                print(f"Marked task [{task_id}] as done: {task.title}")
            else:
                task = manager.get_task(task_id)
                if task is None:
                    print(f"Error: No task found with ID {task_id}.")
                else:
                    print(f"Task [{task_id}] is already marked as done.")

        elif command == "delete":
            if not args:
                print("Error: 'delete' requires a task ID. Usage: delete <id>")
                continue
            try:
                task_id = int(args[0])
            except ValueError:
                print(f"Error: '{args[0]}' is not a valid task ID. IDs are numbers.")
                continue
            task = manager.get_task(task_id)
            if task is None:
                print(f"Error: No task found with ID {task_id}.")
                continue
            title = task.title
            if manager.delete(task_id):
                print(f"Deleted task [{task_id}]: {title}")

        elif command == "search":
            if not args:
                print("Error: 'search' requires a keyword. Usage: search <keyword>")
                continue
            keyword = " ".join(args)
            results = manager.search(keyword)
            print(f"Search results for '{keyword}':")
            print_tasks(results)

        else:
            print(f"Unknown command: '{command}'. Type 'help' to see available commands.")


if __name__ == "__main__":
    repl()
