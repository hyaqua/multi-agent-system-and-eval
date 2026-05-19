## Revised Implementation Plan

### 1. Files and Their Purposes

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Parses command-line arguments, invokes chosen operation (organize, undo, dry-run). |
| `organizer.py` | Core `Organizer` class that scans a directory, applies rules to compute destinations, handles conflict resolution, performs moves (or simulates), and logs actions. **Also resets the log at the start of an organize run** to ensure undo only reverses the most recent operation. |
| `rules.py` | Functions returning a destination sub-path based on a rule: extension category, date, or size. Only imports what is needed (e.g., `datetime`); **no unused `import os`**. |
| `logger.py` | Manages the JSONL log file: appending move records, reading entries for undo, clearing the log, and resetting the log when a new organize run begins. |
| `utils.py` | Small helpers: human-readable size formatting, progress ticker. |

### 2. Architecture (unchanged)

```
main.py → (argparse) → dispatches to Organizer
                         |
                         ├── rules.py (destination path logic)
                         ├── logger.py (JSONL logging)
                         └── utils.py (formatting, progress)
```

- **`Organizer`** is instantiated with a target directory, a rule type (`ext`, `date`, `size`), a dry-run flag, and a logger instance.
- **Before processing any files**, the organizer calls `logger.reset()` to ensure only the current run’s moves are recorded (enabling undo of *the last operation only*).
- `Organizer.scan()` uses `os.scandir()` to collect non-hidden files, catching `PermissionError` per entry and warning to stderr.
- `Organizer.organize()` iterates over files, calls the appropriate rule function to get a relative subfolder, resolves naming conflicts by appending `_N`, then either prints the intended move (dry-run) or performs `shutil.move()` and logs to JSONL.
- `Logger` writes one JSON object per line. It provides `reset()` to truncate the log, `log_entry()` to append, and `read_log()` for undo. Undo reads the log in reverse, moves files back, and on success clears the log.
- Progress is reported via `utils.show_progress()` that prints a dot to stderr for every 10 files processed.

### 3. Implementation Order (updated)

1. **Wire up argument parsing** (`main.py`).
2. **Build rule functions** (`rules.py`): extension mapping, date path, size category. *Ensure no unused imports – only import modules actually used (e.g., `datetime`).*
3. **Implement file scanning** in `organizer.py` with hidden-file filtering and error handling.
4. **Add destination path computation and conflict resolution** in `organizer.py`.
5. **Create the JSONL logger** (`logger.py`) including the `reset()` method that truncates the log file. This method is called by the organizer before any moves.
6. **Integrate dry-run vs actual moves** in `organizer.py`. In the actual (non-dry) path, the organizer first invokes `self.logger.reset()` to drop any prior log, then processes files.
7. **Add summary display** after processing.
8. **Implement undo** (`main.py` calls organizer with `--undo`, which uses logger to reverse moves). Because the log contains only the most recent organize run (thanks to step 6), undo reverses exactly the last operation and then clears the log.
9. **Add progress indicator** (`utils.show_progress()`).
10. **Polish error handling** and ensure all warnings go to stderr.

### 4. Libraries Required

- **Standard library only**: `argparse`, `os`, `os.path` / `pathlib`, `shutil`, `json`, `datetime`, `sys`, `math` (for size thresholds), `time` (for log timestamp). *No `os` import in `rules.py` unless a rule needs it (they do not).*

### 5. Feature Implementation Details (updated)

| Feature | Implementation Approach |
|---------|------------------------|
| **Target directory argument** | `parser.add_argument('directory', type=pathlib.Path, help='...')`; convert to absolute path. |
| **Scan and list files** | Use `os.scandir(directory)`. For each entry that is a file and not hidden: gather `name`, `stat().st_size`, `stat().st_mtime`. Print a formatted list before organizing. |
| **Organize by extension category** | `rules.get_ext_category(ext)` returns category. Used when neither `--by-date` nor `--by-size` is given. |
| **Organize by date (`--by-date`)** | `rules.get_date_path(mtime)` → `datetime.fromtimestamp(mtime).strftime('%Y/%m')`. |
| **Organize by size (`--by-size`)** | `rules.get_size_category(size)` returns `Small` (< 1 MB), `Medium` (1–100 MB), `Large` (> 100 MB). |
| **Dry-run mode (`--dry-run`)** | When flag is set, moves are not executed. Intended destination and conflict resolution suffix printed; summary table shown. |
| **Summary display** | Counts aggregated by destination folder, printed as simple table. |
| **Filename conflict resolution** | Before moving, check if `dest` exists. If yes, try `file_1.ext`, `file_2.ext`, … until free. |
| **Logging operations** | `Logger` appends entries to `organizer_log.jsonl`. Each line `{"timestamp": ..., "source": ..., "destination": ...}` written after a successful move. |
| **Undo (`--undo`)** | Reads the log file (which contains only the most recent operation thanks to the reset at the start of each organize run). Processes entries in **reverse order**: moves `destination` back to `source`. If `source` already exists, appends a timestamp suffix to avoid overwriting newly created files. If `destination` is missing, warns and skips. On success, the log file is truncated so that subsequent organizes start clean. |
| **Skipping hidden files/directories** | Names starting with `.` ignored; only regular files processed. |
| **Permission error handling** | `PermissionError` during scanning/moving is caught, warning to stderr, file skipped. |
| **Progress indicator** | Counter per file; dot to stderr every 10 files; newline at end. Silent if fewer than 20 files. |
| **Unused import bug** | `rules.py` will not contain `import os` (or any unused import). Only `datetime` is needed for date rules. |

### 6. Key Changes from Original Plan

- **Logger reset**: Added `Logger.reset()` that truncates the log file. Called by `Organizer` before performing any actual moves (not in dry-run). This ensures the log contains only the most recent organize operation, so undo reverses exactly that operation.
- **Undo scope**: Undo now correctly undoes only the last operation by relying on the log being reset at the start of each organize run. The “Undo” description updated to reflect this.
- **Clean rules.py**: Explicitly stated that `rules.py` avoids the unused `import os` bug; only necessary imports are used.