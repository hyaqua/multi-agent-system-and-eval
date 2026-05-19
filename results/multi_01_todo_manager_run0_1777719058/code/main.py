#!/usr/bin/env python3
"""Entry point for the CLI Todo Manager – a simple REPL loop."""

from __future__ import annotations

import sys
from typing import Optional

from manager import TaskManager
from task import Task


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _status(task: Task) -> str:
    return "Done" if task.completed else "Active"


def _print_tasks(tasks: list[Task]) -> None:
    """Print a formatted table of tasks."""
    if not tasks:
        print("(no tasks)")
        return

    # Column widths
    widths = {
        "id": 4,
        "title": max(max(len(t.title) for t in tasks), 5),
        "priority": 8,
        "status": 8,
        "date": 19,
    }
    fmt = (
        f"{{id:<{widths['id']}}}  "
        f"{{title:<{widths['title']}}}  "
        f"{{priority:<{widths['priority']}}}  "
        f"{{status:<{widths['status']}}}  "
        f"{{date:<{widths['date']}}}"
    )
    print(fmt.format(id="ID", title="Title", priority="Priority", status="Status", date="Date"))
    print("-" * (sum(widths.values()) + 8))
    for t in tasks:
        print(
            fmt.format(
                id=t.id,
                title=t.title,
                priority=t.priority.capitalize(),
                status=_status(t),
                date=t.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        )


# ---------------------------------------------------------------------------
# Argument parser helpers
# ---------------------------------------------------------------------------

def _parse_args(args: list[str]) -> dict:
    """
    Simple argument parser for commands.

    Recognises:
      --priority high|medium|low
      --sort priority|date
      positional arguments (first word = command, rest = positional)
    """
    result: dict = {"positional": [], "priority": None, "sort": None}
    i = 0
    while i < len(args):
        if args[i] == "--priority" and i + 1 < len(args):
            result["priority"] = args[i + 1]
            i += 2
        elif args[i] == "--sort" and i + 1 < len(args):
            result["sort"] = args[i + 1]
            i += 2
        else:
            result["positional"].append(args[i])
            i += 1
    return result


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_add(mgr: TaskManager, args: list[str]) -> None:
    parsed = _parse_args(args)
    if not parsed["positional"]:
        print("Error: Please provide a task title.")
        print("Usage: add <title> [--priority low|medium|high]")
        return
    title = " ".join(parsed["positional"])
    priority = parsed["priority"] or "medium"
    if priority not in ("low", "medium", "high"):
        print(f"Warning: Unknown priority '{priority}', using 'medium'.")
        priority = "medium"
    task = mgr.add(title, priority)
    print(f"Added task #{task.id}: {task.title} (priority: {task.priority})")


def _cmd_list(mgr: TaskManager, args: list[str]) -> None:
    parsed = _parse_args(args)
    filter_status: Optional[str] = None
    sort_by: Optional[str] = parsed.get("sort")

    # Check positional for filter keywords
    for word in parsed["positional"]:
        if word in ("active", "done"):
            filter_status = word
        elif word == "--sort":
            # already handled by _parse_args
            pass

    tasks = mgr.list_all(filter_status=filter_status, sort_by=sort_by)
    header = "All tasks"
    if filter_status:
        header = f"Tasks ({filter_status})"
    if sort_by:
        header += f" sorted by {sort_by}"
    print(f"--- {header} ---")
    _print_tasks(tasks)


def _cmd_done(mgr: TaskManager, args: list[str]) -> None:
    parsed = _parse_args(args)
    if not parsed["positional"]:
        print("Error: Please provide a task ID.")
        print("Usage: done <id>")
        return
    try:
        task_id = int(parsed["positional"][0])
    except ValueError:
        print("Error: Task ID must be a number.")
        return
    task = mgr.mark_done(task_id)
    if task is None:
        print(f"No task found with ID {task_id}.")
    else:
        print(f"Marked task #{task.id} as done: {task.title}")


def _cmd_delete(mgr: TaskManager, args: list[str]) -> None:
    parsed = _parse_args(args)
    if not parsed["positional"]:
        print("Error: Please provide a task ID.")
        print("Usage: delete <id>")
        return
    try:
        task_id = int(parsed["positional"][0])
    except ValueError:
        print("Error: Task ID must be a number.")
        return
    task = mgr.delete(task_id)
    if task is None:
        print(f"No task found with ID {task_id}.")
    else:
        print(f"Deleted task #{task.id}: {task.title}")


def _cmd_search(mgr: TaskManager, args: list[str]) -> None:
    parsed = _parse_args(args)
    if not parsed["positional"]:
        print("Error: Please provide a search keyword.")
        print("Usage: search <keyword>")
        return
    keyword = " ".join(parsed["positional"])
    results = mgr.search(keyword)
    print(f'--- Search results for "{keyword}" ---')
    _print_tasks(results)


def _cmd_help() -> None:
    print(
        """
Available commands:

  add <title> [--priority low|medium|high]
      Add a new task. Title can be multiple words.
      Example: add "Buy milk" --priority high

  list [active|done] [--sort priority|date]
      List tasks. Optional filter: active, done.
      Optional sort: by priority (high first) or date (newest first).
      Examples:
        list
        list active
        list done --sort priority

  done <id>
      Mark a task as completed by its ID.
      Example: done 3

  delete <id>
      Delete a task by its ID.
      Example: delete 2

  search <keyword>
      Search tasks whose title contains the keyword (case-insensitive).
      Example: search milk

  help
      Show this help message.

  quit | exit
      Exit the program.
"""
    )


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def main() -> None:
    mgr = TaskManager()

    print("=" * 50)
    print("  CLI Todo Manager")
    print("  Type 'help' for available commands, 'quit' to exit.")
    print("=" * 50)

    while True:
        try:
            raw = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            sys.exit(0)

        if not raw:
            continue

        # Split into command + arguments
        parts = raw.split()
        command = parts[0].lower()
        cmd_args = parts[1:]

        if command in ("quit", "exit"):
            print("Goodbye!")
            break
        elif command == "help":
            _cmd_help()
        elif command == "add":
            _cmd_add(mgr, cmd_args)
        elif command == "list":
            _cmd_list(mgr, cmd_args)
        elif command == "done":
            _cmd_done(mgr, cmd_args)
        elif command == "delete":
            _cmd_delete(mgr, cmd_args)
        elif command == "search":
            _cmd_search(mgr, cmd_args)
        else:
            print(f"Unknown command '{command}'. Type 'help' for available commands.")


if __name__ == "__main__":
    main()
