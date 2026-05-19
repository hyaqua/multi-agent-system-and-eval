"""REPL loop, command parsing, and user interaction."""

import shlex
import sys
from typing import Any

from manager import Manager, TaskNotFoundError

HELP_TEXT = """\
Available commands:
  add <title> [priority]     Add a new task. Priority: low|medium|high (default: medium)
                             Example: add "Buy groceries" high
  list [all|active|done]     List tasks. Optional status filter.
           [--sort priority|date]   Sort by priority or creation date.
                             Example: list active --sort priority
  done <id>                  Mark a task as complete.
                             Example: done 3
  delete <id>                Delete a task by its ID.
                             Example: delete 2
  search <keyword>           Search tasks by title keyword.
                             Example: search grocery
  help                       Show this help message.
  quit | exit                Exit the program.
"""


class CLI:
    """Command-line interface for the task manager."""

    def __init__(self, manager: Manager) -> None:
        self._manager: Manager = manager
        self._running: bool = True
        self._commands = self.__init_commands__()

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def _handle_add(self, args: list[str]) -> None:
        if not args:
            print("Usage: add <title> [priority]")
            return

        title = args[0]
        priority = "medium"
        if len(args) >= 2:
            priority = args[1].lower()
            if priority not in ("low", "medium", "high"):
                print("Priority must be low, medium, or high.")
                return

        try:
            task = self._manager.add_task(title, priority)
            print(f"Task #{task.id} added: {task.title}")
        except ValueError as exc:
            print(f"Error: {exc}")

    def _handle_list(self, args: list[str]) -> None:
        status: str | None = None
        sort_by: str | None = None
        i = 0

        # Parse positional status filter
        if args and not args[0].startswith("--"):
            status = args[0].lower()
            if status not in ("all", "active", "done"):
                print("Status filter must be 'all', 'active', or 'done'.")
                return
            if status == "all":
                status = None
            i = 1

        # Parse --sort flag
        while i < len(args):
            if args[i] == "--sort":
                i += 1
                if i >= len(args):
                    print("Missing sort option after --sort. Use 'priority' or 'date'.")
                    return
                sort_by = args[i].lower()
                if sort_by not in ("priority", "date"):
                    print("Invalid sort option. Use 'priority' or 'date'.")
                    return
            else:
                print(f"Unknown argument: {args[i]}")
                return
            i += 1

        try:
            tasks = self._manager.list_tasks(status, sort_by)
        except ValueError as exc:
            print(f"Error: {exc}")
            return

        if not tasks:
            print("No tasks found.")
            return

        # Print header and rows
        print("  ID  STATUS  PRIORITY  CREATED           TITLE")
        for t in tasks:
            print(t)

    def _handle_done(self, args: list[str]) -> None:
        if not args:
            print("Usage: done <id>")
            return
        try:
            task_id = int(args[0])
            self._manager.complete_task(task_id)
            print(f"Task #{task_id} marked as done.")
        except ValueError:
            print("Invalid ID. Provide a numeric task ID.")
        except TaskNotFoundError as exc:
            print(exc)

    def _handle_delete(self, args: list[str]) -> None:
        if not args:
            print("Usage: delete <id>")
            return
        try:
            task_id = int(args[0])
            self._manager.delete_task(task_id)
            print(f"Task #{task_id} deleted.")
        except ValueError:
            print("Invalid ID. Provide a numeric task ID.")
        except TaskNotFoundError as exc:
            print(exc)

    def _handle_search(self, args: list[str]) -> None:
        if not args:
            print("Usage: search <keyword>")
            return
        keyword = args[0]
        results = self._manager.search_tasks(keyword)
        if not results:
            print(f"No tasks match '{keyword}'.")
            return
        print(f"Search results for '{keyword}':")
        print("  ID  STATUS  PRIORITY  CREATED           TITLE")
        for t in results:
            print(t)

    def _handle_help(self, _args: list[str]) -> None:
        print(HELP_TEXT)

    def _handle_quit(self, _args: list[str]) -> None:
        print("Goodbye!")
        self._running = False

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def __init_commands__(self) -> dict[str, Any]:
        """Build dispatch table with bound methods."""
        return {
            "add": self._handle_add,
            "list": self._handle_list,
            "done": self._handle_done,
            "delete": self._handle_delete,
            "search": self._handle_search,
            "help": self._handle_help,
            "quit": self._handle_quit,
            "exit": self._handle_quit,
        }

    def _dispatch(self, command: str, args: list[str]) -> None:
        """Look up command and call handler."""
        handler = self._commands.get(command)
        if handler is None:
            print("Unknown command. Type 'help' to see available commands.")
            return
        handler(args)

    # ------------------------------------------------------------------
    # REPL
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the REPL loop."""
        print("Task Manager. Type 'help' for available commands, 'quit' to exit.")
        while self._running:
            try:
                raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not raw:
                continue

            try:
                parts = shlex.split(raw)
            except ValueError as exc:
                print(f"Parse error: {exc}")
                continue

            command = parts[0].lower()
            args = parts[1:]
            self._dispatch(command, args)


# Attach command map *after* class body so methods exist
CLI._COMMANDS = {
    "add": CLI._handle_add,
    "list": CLI._handle_list,
    "done": CLI._handle_done,
    "delete": CLI._handle_delete,
    "search": CLI._handle_search,
    "help": CLI._handle_help,
    "quit": CLI._handle_quit,
    "exit": CLI._handle_quit,
}
