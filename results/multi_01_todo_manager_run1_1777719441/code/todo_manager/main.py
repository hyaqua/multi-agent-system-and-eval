"""REPL entry point for the todo manager."""

import sys
from task_manager import TaskManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
import os as _os
FILENAME = _os.path.join(_os.path.expanduser('~'), '.todo_manager_tasks.json')
STATUS_ICONS = {True: '✓', False: '✗'}

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
HEADER = f"{'ID':<5} {'Title':<25} {'Priority':<10} {'Status':<8} {'Created':<26}"
SEP = '-' * len(HEADER)


def print_table(tasks):
    """Print a list of tasks as a fixed-width table."""
    if not tasks:
        print("No tasks to show.")
        return

    print(HEADER)
    print(SEP)
    for t in tasks:
        status_icon = STATUS_ICONS[t.completed]
        # Truncate title if it is too long for the column
        title = t.title if len(t.title) <= 25 else t.title[:22] + '...'
        print(
            f"{t.id:<5} "
            f"{title:<25} "
            f"{t.priority:<10} "
            f"{status_icon:<8} "
            f"{t.created_at:<26}"
        )


def print_help():
    """Print available commands."""
    print("Available commands:")
    print("  add <title> [-p low|medium|high]   Add a new task")
    print("  list [active|done] [--sort priority|date]")
    print("                                      List tasks")
    print("  done <id>                           Mark a task as completed")
    print("  delete <id>                         Delete a task")
    print("  search <keyword>                    Search tasks by title keyword")
    print("  help                                Show this help message")
    print("  quit / exit                         Exit the program")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
def cmd_add(manager, args):
    """parse  add <title> [-p priority]"""
    if not args:
        print("Usage: add <title> [-p low|medium|high]")
        return

    priority = 'medium'
    title_parts = []
    i = 0
    while i < len(args):
        if args[i] == '-p':
            i += 1
            if i < len(args):
                priority = args[i].lower()
            else:
                print("Error: -p flag requires a priority value (low, medium, high).")
                return
        else:
            title_parts.append(args[i])
        i += 1

    title = ' '.join(title_parts).strip()
    if not title:
        print("Error: Task title cannot be empty.")
        return

    try:
        task = manager.add_task(title, priority)
        manager.save(FILENAME)
        print(f"Task added: [#{task.id}] {task.title}  (priority: {task.priority})")
    except ValueError as exc:
        print(f"Error: {exc}")


def cmd_list(manager, args):
    """parse  list [active|done] [--sort priority|date]"""
    status = None
    sort_by = None

    i = 0
    while i < len(args):
        arg = args[i].lower()
        if arg in ('active', 'done'):
            status = arg
        elif arg == '--sort':
            i += 1
            if i < len(args):
                val = args[i].lower()
                if val in ('priority', 'date'):
                    sort_by = val
                else:
                    print("Error: --sort must be 'priority' or 'date'.")
                    return
            else:
                print("Error: --sort requires a value ('priority' or 'date').")
                return
        else:
            print(f"Unknown list option: '{args[i]}'. Use: list [active|done] [--sort priority|date]")
            return
        i += 1

    tasks = manager.list_tasks(status=status, sort_by=sort_by)
    print_table(tasks)


def cmd_done(manager, args):
    """parse  done <id>"""
    if not args:
        print("Usage: done <id>")
        return
    try:
        task_id = int(args[0])
        task = manager.mark_complete(task_id)
        manager.save(FILENAME)
        print(f"Task #{task.id} marked as completed: {task.title}")
    except ValueError:
        print(f"Error: Invalid ID '{args[0]}'. Please provide a numeric task ID.")


def cmd_delete(manager, args):
    """parse  delete <id>"""
    if not args:
        print("Usage: delete <id>")
        return
    try:
        task_id = int(args[0])
        task = manager.delete_task(task_id)
        manager.save(FILENAME)
        print(f"Task #{task.id} deleted: {task.title}")
    except ValueError:
        print(f"Error: Invalid or unknown task ID '{args[0]}'.")


def cmd_search(manager, args):
    """parse  search <keyword>"""
    if not args:
        print("Usage: search <keyword>")
        return
    keyword = ' '.join(args)
    results = manager.search_tasks(keyword)
    if not results:
        print(f"No tasks found matching '{keyword}'.")
    else:
        print(f"Found {len(results)} task(s) matching '{keyword}':")
        print_table(results)


# ---------------------------------------------------------------------------
# Command dispatch table
# ---------------------------------------------------------------------------
COMMANDS = {
    'add': cmd_add,
    'list': cmd_list,
    'done': cmd_done,
    'delete': cmd_delete,
    'search': cmd_search,
    'help': lambda mgr, args: print_help(),
}


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------
def main():
    manager = TaskManager()
    manager.load(FILENAME)

    print("Todo Manager — type 'help' for available commands, 'quit' to exit.")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd_name = parts[0].lower()
        cmd_args = parts[1:]

        if cmd_name in ('quit', 'exit'):
            print("Goodbye!")
            break

        if cmd_name in COMMANDS:
            COMMANDS[cmd_name](manager, cmd_args)
        else:
            print(f"Unknown command: '{cmd_name}'. Type 'help' for available commands.")


if __name__ == '__main__':
    main()
