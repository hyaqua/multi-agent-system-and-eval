STATUS: COMPLETE

## Features Implemented and Verified

1. ✅ REPL loop accepting text commands — Runs in a continuous loop reading from stdin, with `> ` prompt.
2. ✅ `add` command with title and optional priority — Supports `add <title>` (defaults to medium) and `add <title> --priority low|medium|high`. Validates priority values.
3. ✅ `list` command showing ID, title, priority, status (✓/○), and creation date — Pretty-printed table format.
4. ✅ `done <id>` command — Marks task as complete by ID. Handles: non-existent ID, non-numeric ID, already-completed tasks.
5. ✅ `delete <id>` command — Removes task by ID. Handles: non-existent ID, non-numeric ID.
6. ✅ Filter by status — `list active` shows incomplete tasks, `list done` shows completed tasks.
7. ✅ Sort by priority or date — `list --sort priority` (high→low), `list --sort date` (newest first). Works combined with status filters.
8. ✅ `search <keyword>` command — Case-insensitive substring match in titles.
9. ✅ JSON file persistence — Saves to `tasks.json` after every add/done/delete operation.
10. ✅ Load from JSON on startup — Restores all tasks if the file exists. Handles corrupt JSON gracefully.
11. ✅ Invalid commands and IDs — Clear error messages for: unknown commands, missing arguments, invalid priorities, non-numeric IDs, non-existent IDs.
12. ✅ `help` command — Displays all available commands with usage.
13. ✅ `quit` and `exit` commands — Both stop the program with a "Goodbye!" message.

## Files Created
- `todo.py` — Complete single-file implementation (~350 lines).

## Testing Summary
- Tested all commands individually and in combination.
- Tested edge cases: empty input, invalid priorities, missing arguments, non-numeric IDs, non-existent IDs, already-done tasks.
- Verified persistence by running the program twice and confirming tasks survive.
- Verified JSON file format is correct.
