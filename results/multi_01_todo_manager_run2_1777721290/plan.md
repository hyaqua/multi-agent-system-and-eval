# Implementation Plan

## Files & Purpose

1. **`task.py`** – Defines the `Task` dataclass and a mapping from priority strings to numeric sort values.
2. **`storage.py`** – Handles reading from and writing to the JSON persistence file (`tasks.json`).
3. **`manager.py`** – Core business logic: creating, listing, filtering, sorting, completing, deleting, and searching tasks; calls storage after each mutation.
4. **`cli.py`** – Contains the REPL loop, command parsing, and all user interaction.
5. **`main.py`** – Entry point that initialises the storage, manager, and starts the CLI.

## Architecture

- **`Task`** – A frozen dataclass with fields: `id: int`, `title: str`, `priority: str`, `completed: bool`, `created_at: datetime`. The `__str__` or a helper method formats output (ID, title, priority, status, formatted date).
- **`Storage`** – Two functions: `load_tasks(filepath)` returns a list of `Task` objects (or empty list if file does not exist); `save_tasks(filepath, tasks)` serialises `Task` objects to JSON. Datetimes are stored as ISO-format strings.
- **`Manager`** – Holds a list of `Task` objects and a `Storage` reference. On initialisation it loads existing tasks and determines the next ID (`max_id + 1` or `1`). Every public method that modifies data (`add_task`, `complete_task`, `delete_task`) calls `_persist()` afterwards. Methods:
  - `add_task(title, priority='medium')` – Creates and appends a new `Task` with the next ID and current datetime, persists.
  - `list_tasks(status=None, sort_by=None)` – Filters by `status` (`'active'` → completed=False, `'done'` → completed=True, otherwise all). Sorts by `sort_by`: `'priority'` (numeric value, high=1, medium=2, low=3) or `'date'` (ascending creation datetime). Returns sorted list.
  - `complete_task(task_id)` – Marks the task with given ID as completed, persists.
  - `delete_task(task_id)` – Removes task by ID, persists.
  - `search_tasks(keyword)` – Returns tasks where `keyword.lower()` is in `title.lower()`.
- **`CLI`** – Contains the `run()` loop. Parses input, dispatches to manager methods, prints formatted output, and handles errors gracefully. Pre-defined help text.
- No external libraries – standard library only (`dataclasses`, `datetime`, `json`, `os`, `sys`, `typing`).

## Implementation Order

1. **`task.py`** – `Task` dataclass, `PRIORITY_ORDER` dictionary.  
2. **`storage.py`** – `load_tasks()`, `save_tasks()`. Test with a dummy file.  
3. **`manager.py`** – `Manager` class with methods. Test each method informally.  
4. **`cli.py`** – Full REPL with command parsing. Use a dictionary mapping command tokens to handler methods. Include `help` and `quit`/`exit`.  
5. **`main.py`** – Create `Storage` and `Manager`, then start `CLI.run()`.  

## Feature Implementation Details

### REPL Loop (`cli.py`)
- Infinite loop printing `> ` prompt.
- Read line, split into parts (support quoted titles with `shlex.split` or naive splitting – use `shlex` for proper handling of quoted strings).
- Dispatch to `_handle_add(args)`, `_handle_list(args)`, etc., or print unknown command if no match.
- `help` prints a pre-defined string listing all commands and usage.

### Add Command
- Syntax: `add "task title" [medium|high|low]`  
- Use `shlex.split` to parse the input, allowing titles with spaces inside quotes.  
- If priority omitted, default `'medium'`. Validate priority values, else error.  
- Call `manager.add_task(title, priority)`. Print success with new task ID.

### List Command
- Syntax: `list [all|active|done] [--sort priority|date]`  
- Parse optional status filter (first argument if not starts with `--`) and optional sort flag (`--sort priority` or `--sort date`).  
- Call `manager.list_tasks(status, sort)`.  
- Print a header and one line per task with ID, title (truncated if very long), priority, status (✅/❌), creation date (formatted).  
- If no tasks, print “No tasks found.”

### Mark Done
- Syntax: `done <id>`  
- Convert id to int, call `manager.complete_task(id)`.  
- Manager raises custom exception (e.g., `TaskNotFoundError`) if ID invalid; CLI catches and prints “No task found with ID X.”

### Delete
- Syntax: `delete <id>`  
- Same as mark done but calls `manager.delete_task(id)`. Confirm deletion? No confirmation required per spec, just delete and print “Task X deleted.”

### Filtering & Sorting
- Implemented inside `manager.list_tasks()` with simple `if` branches and `sorted()` calls.  
- Sorting by priority uses `PRIORITY_ORDER[task.priority]` as sort key; by date uses `task.created_at`.

### Search
- Syntax: `search <keyword>`  
- Call `manager.search_tasks(keyword)`. Display results in same format as list, with a heading “Search results for ‘keyword’:”.

### Persistence
- Storage file path: `tasks.json` in the current working directory.  
- `save_tasks` converts each `Task` to a `dict` with `dataclasses.asdict()`, ensuring `created_at` becomes ISO string.  
- `load_tasks` reads JSON, rebuilds `Task` objects using `datetime.fromisoformat`.  
- Manager calls `_persist()` after any add/delete/complete. On first run, missing file yields an empty list.

### Error Handling
- Unknown command: “Unknown command. Type 'help' to see available commands.”  
- Invalid task ID (not an integer or not found): “No task found with ID X.” (Manager raises, CLI catches).  
- Invalid priority: “Priority must be low, medium, or high.”  
- Missing title for add: “Usage: add <title> [priority]”  
- Invalid sort argument: “Invalid sort option.”  
- If JSON file is corrupted, catch `json.JSONDecodeError` and start with an empty list, printing a warning.

### Help
- `help` command prints a formatted block covering: `add`, `list`, `done`, `delete`, `search`, `help`, `quit`/`exit` with brief examples.

### Quit
- Typing `quit` or `exit` breaks the REPL loop; the program terminates cleanly.