# Revised Implementation Plan (Post-Review)

The application currently crashes on startup when not attached to a TTY and the process search is blocking.  
This revised plan addresses those exact failures while keeping all other requirements intact.

## Issues to Fix
1. **Terminal crash (no TTY)** – The error `setupterm: could not find terminal` indicates that `curses` initialisation happens before a terminal check.
2. **Blocking search** – Pressing `/` enters a blocking `getstr()` loop, freezing the UI instead of live filtering.
3. **Unused imports / dead code** – `struct`, `math`, `signal`, duplicate `os`, `search_mode` variable, bare `except` variables.
4. **Edge case in history buffer size** – `MAX_HISTORY = max(1, int(60 / interval))` works for common intervals but may fail for non‑integer intervals if introduced later. We will make it safe.

## Required Changes

### 1. Terminal guard – crash prevention
**File:** `monitor.py` (the main entry point)

- Place the TTY check **at the very top of the file**, before *any* `import` statement that might trigger terminal detection (`os` itself is safe).
- Use a guard that exits with a clear error message if stdout is not a TTY.
- Only after the check succeeds, `import curses`.
- *Do not* rely on any other module’s imports that might pull in `curses` beforehand – restructure if necessary so that `monitor.py` is the sole entry point.

**Implementation sketch:**
```python
#!/usr/bin/env python3
import os
import sys

def has_terminal():
    """Return True if the process is attached to an interactive terminal."""
    return os.isatty(sys.stdout.fileno()) and os.isatty(sys.stdin.fileno())

if not has_terminal():
    print("Error: This application requires an interactive terminal.", file=sys.stderr)
    sys.exit(1)

# Only now is it safe to import curses
import curses
# ... rest of imports and application
```

**Validation:**  
- Run `./monitor.py > /dev/null` → should print error to stderr and exit 1.  
- Run inside a real terminal → proceed normally.

### 2. Real‑time, non‑blocking search
**Affected files:** `monitor.py`, `display.py`, `process.py`

Eliminate all blocking input functions (`getstr()`, `getch()` loops that wait for Enter).  
Replace with a state machine inside the main event loop that already uses `stdscr.timeout()` (e.g., 500 ms).

**State variables** in `main()` or the UI handler:
```python
search_active = False
search_term = ""
```

**Main loop key handling** (after a key is obtained from `stdscr.getch()`):
1. If the current view is **Processes**:
   - Key `/` toggles `search_active`.  
     - Toggling *on* clears any previous `search_term` and resets the filter.  
     - Toggling *off* clears the filter and the term.
   - While `search_active` is `True`:
     - **Printable ASCII (32-126)**: append character to `search_term`, call `process_manager.search(search_term)`.
     - **Backspace (KEY_BACKSPACE, 127, 8)**: remove last character, update filter.
     - **Escape (27)**: clear term, set `search_active = False`, call `process_manager.clear_filter()`.
     - **Navigation keys (`j`, `k`, arrows)**: move selection cursor within the filtered list; do not alter the filter.
     - Any other key is ignored (or used to exit search mode if Escape is the only exit, as specified).
2. **View changes** (tab switching) **must** disable search and clear the filter.

**Process module additions:**
- `search(term: str)` – filter internal process list by case‑insensitive substring match on command name; maintain the original unfiltered list.
- `get_filtered_list()` – return the currently filtered list (or the full list if no filter active).
- `clear_filter()` – restore unfiltered state.

**Status line integration:**  
While `search_active`, show `"Filter: <search_term>"` in the footer/status area.

**Validation:**
- Typing a letter instantly narrows the process table.
- Backspace updates the filter.
- Escape clears everything and exits search mode.
- Arrow keys / `j`, `k` scroll the filtered list without disrupting the filter.
- Changing tabs resets the search.

### 3. Code cleanup
Remove all identified dead imports and variables:

| File           | Removal                                      |
|----------------|----------------------------------------------|
| `monitor.py`   | `import signal` (unused) <br> duplicate `import os` |
| `monitor.py`   | dead variable `search_mode`                  |
| `collector.py` | `import struct`                              |
| `display.py`   | `import math`                                |
| `process.py`   | unused assignment `cpu_delta`                |
| Various        | bare `except:` with variable `e` that is never used – replace with `except Exception` or simply `try/except` without binding if logging required. |

After cleanup, run `flake8`/`pylint` to confirm zero warnings for unused imports/unused variables.

### 4. MAX_HISTORY safety
**File:** likely `collector.py` or `monitor.py` where the CPU history buffer size is defined.

- Current: `MAX_HISTORY = max(1, int(60 / interval))`
- Ensure interval is strictly greater than zero (already enforced by argparse).  
- For robustness, use:  
  ```python
  MAX_HISTORY = max(1, int(60 / max(float(interval), 0.1)))
  ```  
  to avoid division by zero and guarantee at least one entry.

This prevents a crash if `--interval 0` is accidentally provided and the argument parser does not reject it.

## Implementation Order & Validation

1. **Terminal guard**  
   - Insert the `has_terminal()` check **first** in `monitor.py`.  
   - Test with `/dev/null` and in a real terminal.

2. **Real‑time search**  
   - Remove any existing blocking search input (`getstr`).  
   - Implement the character‑by‑character handler as described.  
   - Add filtering methods to `process.py`.  
   - Verify full interactive search with the test scenarios above.

3. **Code cleanup**  
   - Delete all listed unused imports and variables.  
   - Confirm the application still runs without regressions.

4. **MAX_HISTORY fix** (optional but recommended)  
   - Adjust the formula to avoid division by zero.

5. **Full regression test**  
   - Run all views (Overview, Processes, Network, Disk).  
   - Test process tree, kill/renice, sorting, search, and tab switching.  
   - Verify that `--interval` works correctly.

## Summary of Fixes

| Issue                                 | Fix                                                                 |
|---------------------------------------|---------------------------------------------------------------------|
| Crash on non‑TTY (`setupterm` error) | `os.isatty()` guard **before any curses import**, with clear error and exit. |
| Blocking search (UI freeze)          | Real‑time, non‑blocking character‑by‑character handler; `/` toggles, Escape exits. |
| Unused imports / dead variables      | Remove `signal`, `struct`, `math`, duplicate `os`, and unused variables. |
| Potential division by zero in history buffer | Safer `MAX_HISTORY` computation using `max(interval, 0.1)`. |

All other functionality remains unchanged and is expected to work after these corrections.