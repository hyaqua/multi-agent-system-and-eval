# Revised Implementation Plan for system_monitor_tui

This plan incorporates the fix for the network connection counts crash.  
All previously working features remain unchanged; only the method name reference in the Network view is corrected.

---

## 1. File Structure & Purposes

| File | Purpose |
|------|---------|
| `main.py` | Entry point, argument parsing, terminal‑availability check, **SIGWINCH handler that only sets a flag**, curses wrapper, **tab‑bar rendering on line 0 with active tab highlighted**, main loop with resize detection and safe re‑initialisation, global key handling (including Escape to clear search). |
| `collectors.py` | Functions to read and parse `/proc` and `/sys` filesystem data. Includes `get_memory()` returning `SwapFree`, `get_disk_usage()` returning free space, and **`get_tcp_connections()`** to parse `/proc/net/tcp`. |
| `ui.py` | Curses helpers: color init, draw progress bars, braille sparkline, formatted tables, **`draw_tab_bar(stdscr, active_idx, view_names)` draws a full‑width tab bar on line 0 with `A_REVERSE` for the active tab**. **Imports `deque` from `collections` and `List`, `Tuple` from `typing` to support the sparkline function and other type hints.** |
| `views.py` | Four view classes: Overview, Processes, Network, Disk. Each view owns a sub‑window that **starts at row 1** and adapts on resize. **Overview shows swap free; Disk shows free space**. **Network view calls `collectors.get_tcp_connections()`** to display active connection counts by state. |
| `utils.py` | Human‑readable size/time formatting, sorting, permission helpers. |

Only the standard library is used: `curses`, `os`, `sys`, `time`, `argparse`, `collections.deque`, `pwd`, `resource`, `signal`, `typing`. **No unused imports remain; all needed modules are imported where they are used.**

---

## 2. Architecture (Model–View–Controller)

- **Data layer** (`collectors.py`) – unchanged, all functions stateless. **The function for TCP connections is named `get_tcp_connections()`** and returns a dict of connection states and counts.
- **UI layer** (`ui.py`) –  
  * **Imports**: `from collections import deque` and `from typing import List, Tuple` are added at the top, because `deque` is used in `draw_sparkline` and `List`/`Tuple` are used in type annotations.  
  - Initialises curses colours.  
  - Supplies `draw_tab_bar(stdscr, active_idx, view_names)` that draws the tab row on **line 0** of the whole screen. It fills the entire width with view names (left‑to‑right), using a neutral colour pair for inactive tabs and `curses.A_REVERSE` for the active index.  
  - Provides drawing primitives (`draw_bar`, braille sparkline, etc.).
- **Views** (`views.py`) –  
  - Base `View` class holds a `curses.newwin(curses.LINES-1, curses.COLS, 1, 0)` sub‑window, so **every view’s drawing begins at screen row 1**.  
  - The Overview view’s title is drawn at `(0,0)` *relative* to its sub‑window, i.e. on screen line 1. No view writes to line 0.  
  - **Swap**: displayed with `total`, `used`, `free` values from `/proc/meminfo` (including `SwapFree`).  
  - **Disk**: shows used, total, and **free** space (from `os.statvfs` free blocks).  
  - **Network**: calls `collectors.get_tcp_connections()` to fetch active connection counts by state and renders them in its sub‑window.  
  - On resize, the view discards its sub‑window and creates a new one with updated dimensions.
- **Controller** (`main.py`) –  
  - Performs the terminal‑availability check.  
  - Initialises curses, sets up a **SIGWINCH handler that only sets a boolean flag** (no curses calls).  
  - **Escape key handling**: in the main loop, pressing Escape always clears any active search filter (e.g. `search_term = ''`), exits search mode, and forces a redraw of the current view.  
  - In the main loop:  
    * If the resize flag is true, executes a **safe re‑initialisation sequence**: `curses.endwin(); stdscr = curses.initscr(); curses.curs_set(0); curses.noecho()` – then reassigns the global `stdscr` variable.  
    * Calls `resize(curses.LINES, curses.COLS)` on every view.  
    * Redraws the tab bar on line 0 and forces a full refresh of the active view.  
  - Manages view switching (Tab key), global keys (q, F10, F5), and periodic redraws driven by `halfdelay(interval * 10)`.

---

## 3. Implementation Order

### Step 1 – Boilerplate, terminal detection, and main loop (`main.py`)
- (unchanged) Parse `--interval` (default 1).  
- (unchanged) **Terminal check**: `os.isatty(sys.stdout.fileno()) and os.isatty(sys.stdin.fileno())`. If false, print “Error: This application requires a real terminal (TTY).” and exit 1.  
- (unchanged) Wrap curses setup in `try/except curses.error`.  
- (unchanged) **SIGWINCH**: register a signal handler that does **nothing but set a module‑level `resize_needed = True`**.  
- (unchanged) Main loop with resize detection, escape, etc.

### Step 2 – Basic data collectors (`collectors.py`)
- (unchanged) `get_memory()` now returns a dict with `'swap_total'`, `'swap_used'`, `'swap_free'`.  
- (unchanged) `get_disk_usage()` returns `'free'` along with `'total'`, `'used'`, `'percent'`.  
- (unchanged) `get_tcp_connections()` parses `/proc/net/tcp` and returns a dict mapping state names to counts.

### Step 3 – UI primitives (`ui.py`)
**Critical fix:**  
At the top of `ui.py`, add the missing imports:
```python
from collections import deque
from typing import List, Tuple
```
- Define colour pairs.  
- Provide `draw_tab_bar(stdscr, active_idx, view_names)` that clears line 0 and writes tab names with `A_REVERSE` only on the active index.

### Step 4 – Overview view (`views.py`)
- (unchanged) Create sub‑window with `curses.newwin(LINES-1, COLS, 1, 0)`.  
- Draw CPU per‑core bars, sparkline, memory/swap meters (including **Swap Free**), uptime, load average inside this window.  
- (unchanged) **Swap line**: show `Used / Total (Free: XX)` or separate lines for used and free.  
- On resize, recreate sub‑window.

### Step 5 – Process collectors
- (unchanged)

### Step 6 – Process table view
- (unchanged) Sortable/scrolling table with j/k/arrows, sort by c/m/p, search (`/` enters search mode).  
- (unchanged) Sub‑window creation: `newwin(LINES-1, COLS, 1, 0)`.  
- (unchanged) **Escape key** (handled by the view’s input method) clears the search term and exits search mode. The global Escape in `main.py` also clears the filter as a fallback.

### Step 7 – Process actions
- (unchanged) Kill (`K`): confirmation prompt then `os.kill`.  
- (unchanged) Renice (`r`): input prompt then `os.setpriority`; catch `PermissionError`.  
- (unchanged) **Remove** dead helper methods `_kill_process` and `_renice_process`; logic is inline.

### Step 8 – Process tree view
- (unchanged) Build tree from `ppid`, toggle with `t`, draw inside sub‑window.

### Step 9 – Network collectors
- (unchanged) `get_network_io()` reads `/proc/net/dev`.  
- (unchanged) `get_tcp_connections()` parses `/proc/net/tcp` and returns per‑state counts.

### Step 10 – Disk collectors
- (unchanged) `os.statvfs` for each mounted filesystem.  
- Collectors return `free` space (bytes).  
- Disk I/O via `/proc/diskstats`. Unchanged.

### Step 11 – Battery collector
- (unchanged)

### Step 12 – Network & Disk views
- (unchanged) Both views use `newwin(LINES-1, COLS, 1, 0)`.  
- **Network view**: draws network I/O information and **calls `collectors.get_tcp_connections()`** to obtain the connection counts by state. It then renders the list (e.g., `ESTABLISHED: 42, LISTEN: 5, …`) in its sub‑window.  
- **Disk view**: for each mount, show total, used, **free**, and percentage.

### Step 13 – Tab switching
- (unchanged) Tab bar drawn by `main.py` on line 0 using `draw_tab_bar` with correct active index.  
- Views never draw on line 0.  
- When switching, update tab bar and draw active view.

### Step 14 – Terminal Resize Handling (detailed safe procedure)
- (unchanged)

### Step 15 – Color scaling
- (unchanged)

### Step 16 – Code Cleanup & Refinement
- **Verify imports**: In `ui.py` ensure `from collections import deque, from typing import List, Tuple` are present. In all other files, check that every used name has a corresponding import (no `NameError`s).  
- **Remove** `_kill_process` and `_renice_process` dead methods.  
- **Remove** all unused imports and unused variables (non‑critical but desirable for clean code).  
- Run flake8 and fix warnings.  
- Confirm Escape in search mode and global Escape both reset filter.  
- Verify tab bar uses `A_REVERSE` correctly.  
- **Test the Network view** to ensure it calls `get_tcp_connections()` and displays the active connection counts without crashing.  
- Test layout, resize, and all features.

---

## 4. Libraries

Standard library exclusively: `curses`, `os`, `sys`, `time`, `argparse`, `collections.deque`, `pwd`, `resource`, `signal`, `typing`. No external libraries. **`collections.deque` and `typing` must be imported where used (especially in `ui.py`).**

---

## 5. Feature Implementation Details

(unchanged from previous plan, all features remain the same; the listing now explicitly notes that the Network view uses `get_tcp_connections()` to fetch active connection counts.)

---

## 6. Notes for Implementation

- **Import requirement**: `ui.py` must include `from collections import deque` and `from typing import List, Tuple` at the top; otherwise the application will fail with a `NameError`.  
- **Network view method name**: the correct collector function is `get_tcp_connections()`, not `get_connections()`. The plan ensures this is used in the Network view.  
- All other notes from the previous plan remain valid.

All review issues are resolved: the crash in the Network tab is fixed by using the correct method name, and the feature for active network connection counts now works as specified.