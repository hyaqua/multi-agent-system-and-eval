# Revised Implementation Plan: system_monitor_tui (File‑First, Verify‑Before‑Everything)

## Objective
Produce a fully functional terminal system monitor at `/home/dmce/im-buddy2/system_monitor_tui.py` using only the Python standard library and `curses`.  
The program must implement all features from the specification.  
**All prior failures stemmed from missing files.** This plan makes file creation an absolute, unskippable prerequisite; no feature work may begin until every source file exists, compiles, and a skeleton TUI launches and exits cleanly. After that foundation is solid, every required feature is implemented step‑by‑step, with verifications at each stage.

---

## Step 0 – Mandatory File Creation & Verification ( DO NOT SKIP )

Run every command **exactly** as shown. These commands create the project directory, main script, and companion modules.  
If any command fails, **STOP** and fix the problem before continuing.

1. **Create target directory**  
   ```bash
   mkdir -p /home/dmce/im-buddy2
   ```

2. **Write the main script skeleton** – a minimal `curses` app that displays a title and exits on `q`.  
   ```bash
   cat > /home/dmce/im-buddy2/system_monitor_tui.py << 'ENDOFSCRIPT'
   #!/usr/bin/env python3
   """system_monitor_tui – Terminal system monitor (htop-like)."""
   import curses
   import argparse
   import sys
   import signal

   def main(stdscr, interval):
       curses.curs_set(0)
       stdscr.nodelay(True)
       stdscr.keypad(True)
       curses.noecho()
       curses.cbreak()
       signal.signal(signal.SIGWINCH, lambda signum, frame: stdscr.clear())
       stdscr.addstr(0, 0, "System Monitor TUI")
       stdscr.addstr(2, 0, "Loading... Press 'q' or F10 to exit.")
       stdscr.refresh()
       while True:
           key = stdscr.getch()
           if key in (ord('q'), curses.KEY_F10):
               break
           elif key == curses.KEY_RESIZE:
               stdscr.clear()
               stdscr.addstr(0,0,"Resized")
               stdscr.refresh()
           curses.napms(100)

   if __name__ == "__main__":
       parser = argparse.ArgumentParser(description="System Monitor TUI")
       parser.add_argument("--interval", type=float, default=1.0,
                           help="Update interval in seconds")
       args = parser.parse_args()
       try:
           curses.wrapper(main, args.interval)
       except Exception as e:
           print(f"Fatal: {e}", file=sys.stderr)
           sys.exit(1)
   ENDOFSCRIPT
   ```

3. **Make the script executable**  
   ```bash
   chmod +x /home/dmce/im-buddy2/system_monitor_tui.py
   ```

4. **Create companion module stubs** – they will be fully implemented later.  
   ```bash
   echo '"""System data reader – will be filled."""' > /home/dmce/im-buddy2/data_collector.py
   echo '"""Curses view renderers – will be filled."""' > /home/dmce/im-buddy2/views.py
   echo '"""UI drawing helpers – will be filled."""' > /home/dmce/im-buddy2/ui_utils.py
   ```

5. **Verify file presence and syntax** – all commands must succeed.  
   ```bash
   ls -l /home/dmce/im-buddy2/system_monitor_tui.py /home/dmce/im-buddy2/data_collector.py /home/dmce/im-buddy2/views.py /home/dmce/im-buddy2/ui_utils.py
   python3 -m py_compile /home/dmce/im-buddy2/system_monitor_tui.py
   python3 -m py_compile /home/dmce/im-buddy2/data_collector.py
   python3 -m py_compile /home/dmce/im-buddy2/views.py
   python3 -m py_compile /home/dmce/im-buddy2/ui_utils.py
   python3 /home/dmce/im-buddy2/system_monitor_tui.py --help
   ```
   Expected: file sizes printed, **no compilation errors**, `--help` displays usage.

6. **Manual curses test** – launch the skeleton and confirm it runs.  
   ```bash
   python3 /home/dmce/im-buddy2/system_monitor_tui.py
   ```
   You must see the title and loading message; press `q` to exit. If the screen clears and the shell returns normally, the test passes. If the program crashes, fix permissions/directory and re‑run from step 5.

**Do not move beyond Step 0 until every verification passes.**

---

## Step 1 – Data Collection Module (`data_collector.py`)

Replace the stub with a robust `DataCollector` class that reads directly from `/proc` and `/sys`:

- Methods:
  - `cpu_usage(per_core=True)` – parse `/proc/stat` for per‑core and total CPU usage (fraction 0‑100).
  - `memory_info()` – parse `/proc/meminfo` for total, used, free, available, cached, swap total/used/free.
  - `loadavg()` – parse `/proc/loadavg` for 1, 5, 15 minute load averages.
  - `uptime()` – parse `/proc/uptime`, convert seconds to days/hours/minutes/seconds.
  - `process_list()` – parse `/proc/[pid]/stat` and `/proc/[pid]/status` for PID, user (from /proc/[pid]/loginuid or fallback UID), CPU%, MEM%, state, command name. Compute CPU% using delta times.
  - `network_io()` – parse `/proc/net/dev` for per‑interface bytes RX/TX; return deltas from previous call.
  - `disk_usage()` – parse `/proc/mounts`, statvfs, filter out virtual filesystems; return total/used/free/%.
  - `disk_io()` – parse `/proc/diskstats` for read/write sectors; compute per‑disk speeds.
  - `battery_status()` – if `/sys/class/power_supply/BAT0` exists, read capacity, status, energy_now, power_now; estimate time remaining.
  - `connection_counts()` – parse `/proc/net/tcp` and count connections by state (0A=LISTEN,01=ESTABLISHED, etc.).
- Cache raw data for one update cycle so that multiple views don’t re‑read files.
- Gracefully handle missing files – return sensible defaults (e.g., `None` or empty lists) without raising exceptions.

**Verification:**  
```bash
python3 -c "
from data_collector import DataCollector
d = DataCollector()
print('CPU:', d.cpu_usage())
print('Memory:', d.memory_info())
print('Load:', d.loadavg())
print('Uptime:', d.uptime())
print('Processes:', len(d.process_list()))
"
```
No errors, plausible numeric values.

---

## Step 2 – Curses Infrastructure & Overview View

In `views.py`, implement `OverviewView` and basic utility functions.  
In `ui_utils.py`, add helpers for drawing progress bars, human‑readable bytes, and braille graphs (stub).

- `OverviewView.draw(stdscr, data, max_y, max_x)` renders:
  - **CPU** – per‑core progress bars (label: “CPU0”, “CPU1”, …) with percentage to the right, using a helper `draw_bar()`.
  - **Memory & Swap** – total/used/free/available/cached in human‑readable units (`human_bytes(n)`).
  - **Uptime** – formatted string.
  - **Load averages** – three values.
  - If battery data is available, display it; otherwise show “Battery: N/A”.

- In the main script (`system_monitor_tui.py`), modify the main loop to:
  - Instantiate `DataCollector` and `OverviewView`.
  - Call `data.refresh()` each second (using the `--interval` value).
  - Call `overview.draw(stdscr, data, max_y, max_x)`.
  - Accept `q`/F10 to exit, `TAB` will be added later.

**Verification:** Run the TUI; the overview screen is fully populated with real‑time CPU bars, memory, swap, uptime, load averages, and battery (if present). All values update at the configured interval.

---

## Step 3 – Historical CPU Graph (Braille Characters)

- In `DataCollector`, maintain a `deque` (maxlen 60) of overall CPU percentages.
- In `ui_utils.py`, implement `draw_braille_graph(window, y, x, data, max_value=100, height=4)`. Each column uses a 2×4 dot matrix to represent 8 levels. Map each percentage to a column and render using Unicode braille characters (`\u2800`–`\u28FF`).
- Integrate the graph into `OverviewView` below the CPU bars.

**Verification:** A scrolling historical graph is visible, updating each second, and the last 60 seconds of CPU usage are plotted.

---

## Step 4 – Process Table (Flat, Scrollable)

Create `ProcessView` in `views.py`:

- **Header row:** `PID  USER  CPU%  MEM%  STATE  COMMAND`
- **Data rows:** populate from `DataCollector.process_list()`.
- **Scroll management:**
  - `scroll_offset` (index of first visible row in filtered/sorted list).
  - `selected_index` (offset in the full sorted/filtered list).
  - Draw only as many rows as fit on screen (account for header), clipping selection highlight within visible window.
- **Navigation:** `j`/`k` and `DOWN`/`UP` move `selected_index`; if it moves beyond visible area, adjust `scroll_offset`.
- Show a highlighted bar on the selected row.

**Verification:** Process list appears, scrolling works with `j`/`k` and arrow keys, selection highlight moves, only visible rows are drawn.

---

## Step 5 – Process Sorting

- In `ProcessView`:
  - Track `sort_key` (default `'cpu'`) and `sort_reverse` (default `True`).
  - When `c`, `m`, or `p` is pressed, set `sort_key` to `'cpu'`, `'mem'`, `'pid'` respectively. Toggle reverse if the same key is pressed again.
  - Before display, sort the process list.
  - Highlight the sorted column in the header, e.g., “CPU*”.
- The sorted list is the basis for scrolling and selection.

**Verification:** Pressing `c` sorts by CPU descending (highest first); pressing again changes to ascending. Press `m` to sort by memory, `p` to sort by PID.

---

## Step 6 – Real‑Time Search Filtering

- In `ProcessView`, when `/` is pressed, enter search mode:
  - A status line appears: “Search: ”.
  - Capture subsequent characters, building a `search_query` string.
  - After each keystroke, filter the process list (case‑insensitive substring match on command name).
  - Display only matching entries.
  - Press `Enter` to lock the filter (exit search mode but keep the filter).
  - Press `Escape` to cancel the search and clear the filter, restoring the full list.
  - During search mode, ignore navigation keys (except Enter/Escape) to prevent accidental movement.
  - Display matching count.

**Verification:** Type `/bash` – only processes containing “bash” are shown. `Escape` restores full list. `Enter` keeps the filter active and returns navigation.

---

## Step 7 – Process Actions: Kill and Renice

### 7.1 Kill (`K`)
- While a process is selected, pressing `K` (uppercase) shows a confirmation prompt: “Kill PID <n>? (y/n)”.
- Wait for `y` or `n`. On `y`, attempt `os.kill(pid, signal.SIGKILL)`. Handle `PermissionError` with an error message.
- After the action (or cancel), dismiss the prompt and refresh the process list.

### 7.2 Renice (`r`)
- Pressing `r` shows: “New nice value for PID <n>: ”.
- **Crucial:** Use a dedicated multi‑character input loop that reads characters until `Enter` or `Escape`.
- The loop must handle:
  - Appending digits and a leading minus sign.
  - Backspace to delete the last character.
  - Enter to submit; convert the assembled string to integer. If invalid format, show error and re‑prompt.
  - Escape aborts without changes.
- On success, call `os.setpriority(os.PRIO_PROCESS, pid, nice_value)`. Catch `PermissionError` and display message.

**Verification:**
- Kill: select a process, press `K`, confirm with `y` – the process disappears.
- Renice: select a process, press `r`, type `-5` and Enter – verify with external `top`/`renice` that priority changed.

---

## Step 8 – Process Tree View (Toggle with `t`)

- In `ProcessView`:
  - Build a tree from PPID relationships using the full process list (unordered).
  - Add a `children` dict keyed by PID.
  - Toggle `t` switches between flat mode and tree mode. Maintain separate scroll state for tree.
  - In tree mode, walk roots (PPID = 0 or not in list) recursively, indenting with ASCII lines: use `├─` and `└─` for children, `│ ` for continuation.
  - Sorting within siblings by PID.
- When switching back to flat mode, restore the previous flat‑mode scroll/selection.

**Verification:** Press `t` to see hierarchical view with branch lines; arrow keys traverse tree; press `t` again returns to flat list.

---

## Step 9 – Network View

Add `NetworkView` in `views.py`:

- **Interface rates:** Use `DataCollector.network_io()` to get bytes sent/received per second for each interface. Display as a table: `Interface | RX (bytes/s) | TX (bytes/s)`, with human‑readable speeds (e.g., KB/s, MB/s).
- **Connection states:** Parse `DataCollector.connection_counts()` and show a simple list: `ESTABLISHED: 5`, `TIME_WAIT: 12`, etc.
- Handle missing `/proc/net/dev` gracefully (show “N/A”).

**Verification:** Rx/Tx rates change, connection counts are reasonable.

---

## Step 10 – Disk View

Add `DiskView`:

- **Usage:** Use `DataCollector.disk_usage()` to get list of filesystems; display as table: `Filesystem | Total | Used | Free | Use%`.
  - Filter out virtual filesystems (tmpfs, proc, sys, devtmpfs, etc.).
- **I/O:** Use `DataCollector.disk_io()` to get read/write speeds per disk (e.g., sda, nvme0n1). Display as `Disk | Read (B/s) | Write (B/s)` with human‑readable units.
- If diskstats is unreadable, show “N/A” for I/O.

**Verification:** Disk usage matches `df -h` output; I/O speeds are non‑negative and update.

---

## Step 11 – Battery Status (Already in Overview)

Ensure that `battery_status()` is integrated into `OverviewView` (as noted in step 2). If the battery is absent, display “Battery: N/A”. No duplicated code.

---

## Step 12 – Color Coding

- In `ui_utils.py`, create `init_colors()` that defines three color pairs:
  - Pair 1: white/green on black (low)
  - Pair 2: white/yellow on black (medium)
  - Pair 3: white/red on black (high)
- Also create `color_for_percent(p, low=50, mid=80)` that returns the pair index.
- Apply to CPU progress bars, memory/swap usage bars, disk usage percentages.

**Verification:** CPU bar green below 50%, yellow 50–80%, red above 80%. The same applies to memory and disk % bars.

---

## Step 13 – View Cycling & Global Shortcuts

- Modify the main loop to hold a list of views: `[overview, process, network, disk]`.
- `current_view_index` tracks which view is active.
- `Tab` cycles `current_view_index` forward, `Shift+Tab` (or `KEY_BTAB`) cycles backward.
- `F5` forces an immediate refresh – skip the delay after drawing.
- During modal prompts (kill confirmation, renice input, search), ignore `Tab`/`F5` until the prompt is dismissed.
- Each view’s `.draw()` receives the full screen, and must respect `max_y, max_x`.

**Verification:** Press Tab repeatedly to switch views; each view draws correctly. F5 causes an instant redraw. Modals block view switching.

---

## Step 14 – Final Polish and Edge Cases

- **Resize handling:** On `KEY_RESIZE`, recalculate `max_y, max_x` and pass to the active view. Avoid clearing unnecessarily; just redraw.
- **Missing `/proc` files:** All data‑collection methods must return `None` or empty structures when a file is absent, and the views show “N/A” or hide the section.
- **Human‑readable units:** `human_bytes(n)` handles bytes up to TiB, showing two decimal places.
- **Clean exit:** `curses.wrapper` restores terminal; no extra cleanup needed.
- **`--interval` flag:** The main loop uses `curses.napms(int(interval * 1000))` between draws, with the optional skip for F5.
- **Process list accuracy:** CPU% calculation uses delta from `/proc/[pid]/stat` utime+stime and total CPU time. First call may show 0% until baseline is stored; that’s expected.

---

## Step 15 – Complete Integration & Final Test

1. **Ensure all files exist** – re‑run the verification commands from Step 0. All files must compile and the `--help` must work.
2. **Full feature test**: systematically verify each feature:
   - **Overview:** CPU bars per core, historical graph (scrolls), memory, swap, uptime, load averages, battery (or N/A).
   - **Process:** Scrollable list, sorting (`c`/`m`/`p`), search (`/`, Escape, Enter), kill (`K`), renice (`r` with multi‑character input), tree view (`t`).
   - **Network:** Interface rates, connection state counts.
   - **Disk:** Filesystem usage, disk I/O speeds.
   - **Global:** `Tab` cycles views, `F5` refreshes immediately, `q`/F10 exits cleanly, `--interval 0.5` doubles update rate.
   - **Color coding:** Green/yellow/red on all meters.
3. **Edge cases:** Delete a `/proc` file temporarily (e.g., `sudo chmod 000 /proc/diskstats`), start the tool, confirm no crash and “N/A” displayed. Resize the terminal window mid‑run; display adapts.

**At the completion of Step 15, the application meets every requirement of the specification.**

---

## Summary of Revisions
- The entire plan is restructured to make **file existence the absolute first step**, with explicit commands that must be executed and verified. This directly addresses the fatal “file not found” error.
- All subsequent steps are identical to the prior revised plan, because the logic was already sound; the only missing piece was the actual file creation.
- The renice input bug fix (multi‑character input loop) remains included.
- Verification steps are embedded at each stage to catch errors early.

**By following this plan exactly, a working system_monitor_tui.py will be produced, fulfilling all requirements.**