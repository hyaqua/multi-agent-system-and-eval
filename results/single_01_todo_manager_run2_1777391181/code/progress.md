STATUS: COMPLETE

## Todo Manager — Progress Report

### Features Implemented

| # | Feature | Status |
|---|---------|--------|
| 1 | REPL loop accepting text commands | ✅ Working |
| 2 | `add <title> [--priority low|medium|high]` | ✅ Working |
| 3 | `list` — shows ID, title, priority, status, creation date | ✅ Working |
| 4 | `done <id>` — mark task complete by ID | ✅ Working |
| 5 | `delete <id>` — delete task by ID | ✅ Working |
| 6 | `list active` / `list done` — filter by status | ✅ Working |
| 7 | `list --sort priority` / `list --sort date` — sort tasks | ✅ Working |
| 8 | `search <keyword>` — case-insensitive title search | ✅ Working |
| 9 | Auto-save to `tasks.json` after every change | ✅ Working |
| 10 | Load tasks from `tasks.json` on startup if it exists | ✅ Working |
| 11 | Graceful handling of invalid commands and task IDs | ✅ Working |
| 12 | `help` command | ✅ Working |
| 13 | `quit` / `exit` to stop the program | ✅ Working |

### Implementation Details

- **Single file**: `todo_manager.py` (~220 lines)
- **Data model**: `Task` class with id (UUID8), title, priority, completed, created_at
- **Persistence**: JSON file (`tasks.json`) with `json.dump`/`json.load`
- **Architecture**: `TaskStore` class for CRUD + query operations; standalone parse functions for each command
- **Command parsing**: Uses `shlex.split` to handle quoted arguments properly
- **Sorting**: Priority sort order is high → medium → low; Date sort is chronological
- **Error handling**: Invalid IDs, missing arguments, unknown commands all produce helpful messages

### Test Results

- Unit/integration test (`test_todo.py`): All assertions pass (exit code 0)
- REPL interactive tests: All commands behave as expected
- Persistence test: Tasks survive restart
- Edge cases tested: empty add, invalid sort parameter, unknown commands, invalid IDs
