# Implementation Plan: CLI Todo Manager

## 1. File Structure and Purposes

- **`task.py`** – Defines the `Task` data model. No external dependencies.
- **`manager.py`** – Contains `TaskManager`, which handles all task logic, file I/O, and queries.
- **`main.py`** – Entry point; runs the REPL loop, parses commands, and calls `TaskManager`.

All files use only the Python standard library (`json`, `datetime`, `sys`, `os`).

## 2. Architecture Overview

- `Task` is a simple dataclass with attributes:  
  `id: int`, `title: str`, `priority: str` (low/medium/high), `completed: bool`, `created_at: datetime`.
- `TaskManager` manages an in‑memory list of `Task` objects and a JSON file (`tasks.json`).  
  It provides methods: `add`, `mark_done`, `delete`, `list_all` (with optional filtering and sorting), `search`, `load`, `save`.  
  Every mutating method automatically calls `save`.
- `main.py` instantiates `TaskManager`, then enters a `while True` loop reading `input()`.  
  The input is split into parts and dispatched. Results are printed directly. Errors are caught and shown as helpful messages.

## 3. Implementation Order

1. **`task.py`** – `Task` dataclass with a `to_dict` and `from_dict` serializer (used for JSON).
2. **`manager.py`** – `TaskManager`:
   - `__init__`: initialise empty task list, load existing file.
   - `_get_next_id`: auto‑increment from current IDs (starting at 1 if empty).
   - `add(title, priority='medium')`, `mark_done(task_id)`, `delete(task_id)`.
   - `load` / `save` with `json`.
3. **`manager.py`** – filtering and sorting:
   - `list_all(filter_status=None, sort_by=None)`:  
     `filter_status` can be `'active'`, `'done'`, or `None` for all.  
     `sort_by` `'priority'` uses a weight map (high=1, medium=2, low=3) ascending, `'date'` sorts by `created_at`.
   - `search(keyword)`: case‑insensitive substring match in title; returns matching tasks.
4. **`main.py`** – REPL:
   - Print banner. Loop with `>` prompt.
   - Command parsing: split on whitespace, first word is command.
   - Implement commands: `add`, `done`, `delete`, `list`, `search`, `help`, `quit`/`exit`.
   - Handle `list` sub‑commands (`active`, `done`) and flags (`--sort priority|date`).
5. **Error handling & polish**:
   - Graceful messages for unknown commands, missing arguments, invalid task IDs.
   - `help` prints a formatted usage text.
   - Trap `KeyboardInterrupt` for clean exit.

## 4. Libraries

- **Standard library only**: `json`, `datetime`, `sys`, `os`, `typing` (for hints).

## 5. Feature Implementation Details

| Feature | Implementation |
|--------|---------------|
| **REPL loop** | `while True:` with `input('> ')`, `break` on `quit`/`exit`. |
| **Add task** | User types `add "Buy milk" --priority high`. Parser extracts title (mandatory, quoted if spaces) and optional `--priority`. Default priority is medium. Title validated to be non‑empty. Task created with current UTC time, next ID, and saved. |
| **List tasks** | `list` → shows all tasks with columns: ID, Title, Priority, Status, Date. `list active` filters where `completed=False`. `list done` filters where `completed=True`. `list --sort priority` sorts via priority weight; `list --sort date` sorts by creation time (newest first or last, specifiable – here newest first). Combinations work (e.g., `list active --sort priority`). |
| **Mark done** | `done 3` → finds task with ID 3, sets `completed=True`, saves. Error if not found. |
| **Delete** | `delete 3` → removes task with ID 3 from list, saves. Error if not found. |
| **Search** | `search milk` → finds all tasks where `title` contains “milk” (case‑insensitive). Displays matching tasks in same format as list. |
| **Persistence** | `save()` writes the entire task list as JSON array of task dicts to `tasks.json`. Called after every add/done/delete. `load()` reads on startup; if file absent or empty, start with empty list. |
| **Invalid input** | Unknown commands → “Unknown command. Type 'help'.” Missing task ID → “Please provide a task ID.” Invalid ID → “No task found with ID X.” |
| **Help** | `help` prints a summary of all commands with examples. |
| **Quit** | `quit` or `exit` breaks the loop and terminates the program. A final save is not required (already saved on changes). |

## 6. Additional Design Notes

- A simple argument parser can be built manually using `shlex` for quoting if needed, but a straightforward `split()` will work if titles are always quoted when containing spaces. The spec does not require rich formatting, so plain text output is fine.
- Priorities are always stored and compared in lowercase (`'high'`, `'medium'`, `'low'`).
- Creation timestamps are stored as ISO‑8601 strings in JSON for readability; on load they are parsed back to `datetime` objects.
- The manager module will expose a clean API so the REPL only deals with I/O and command routing.