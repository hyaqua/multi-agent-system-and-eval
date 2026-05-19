#!/usr/bin/env python3
"""system_monitor_tui.py - Full-screen curses system monitor TUI.

Usage:
    python system_monitor_tui.py [--interval SECONDS]

Reads system statistics from /proc and /sys and displays them in a
curses-based terminal UI with four views: Overview, Processes, Network, Disk.
"""

import argparse
import curses
import sys
import time

from data_collector import DataCollector
from views import OverviewView, ProcessView, NetworkView, DiskView
from ui_utils import setup_colors, safe_addstr


class SystemMonitorApp:
    """Main application controller."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.collector = DataCollector()
        self.views = []
        self.current_view_idx = 0
        self.running = True
        self.last_update = 0.0
        self.stdscr = None

    def init_views(self) -> None:
        """Create view objects."""
        self.views = [
            OverviewView(self.collector),
            ProcessView(self.collector),
            NetworkView(self.collector),
            DiskView(self.collector),
        ]

    @property
    def current_view(self):
        return self.views[self.current_view_idx]

    def run(self, stdscr) -> None:
        """Main curses loop."""
        self.stdscr = stdscr

        # Setup
        curses.curs_set(0)  # Hide cursor
        stdscr.timeout(100)  # 100ms timeout for non-blocking input
        setup_colors()

        self.init_views()
        self.collector.update()  # Initial data load
        self.last_update = time.time()

        # Initial draw
        self._draw()

        # Main loop
        while self.running:
            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                break

            if key == -1:
                # No key pressed - check if it's time to update
                now = time.time()
                if now - self.last_update >= self.interval:
                    self.collector.update()
                    self.last_update = now
                    self._draw()
                continue

            # Handle global keys
            if key == ord('q') or key == curses.KEY_F10:
                self.running = False
                break

            elif key == ord('\t') or key == 9:  # Tab
                self.current_view_idx = (self.current_view_idx + 1) % len(self.views)
                self._draw()
                continue

            elif key == curses.KEY_BTAB or key == 353:  # Shift+Tab
                self.current_view_idx = (self.current_view_idx - 1) % len(self.views)
                self._draw()
                continue

            elif key == curses.KEY_F5:
                self.collector.update()
                self.last_update = time.time()
                self._draw()
                continue

            elif key == curses.KEY_RESIZE:
                self._draw()
                continue

            # Pass key to current view
            result = self.current_view.handle_key(key)
            if result == "redraw":
                self._draw()

    def _draw(self) -> None:
        """Redraw the current view."""
        if self.stdscr is None:
            return
        height, width = self.stdscr.getmaxyx()
        self.stdscr.erase()

        # Draw view name in top bar
        view_names = ["Overview", "Processes", "Network", "Disk"]
        name = view_names[self.current_view_idx] if self.current_view_idx < len(view_names) else "?"
        safe_addstr(self.stdscr, 0, 0,
                   f" System Monitor - {name} "
                   f"{' ' * (width - len(name) - 19)}"
                   "| Tab/S-Tab:Switch | F5:Refresh | q:Quit ",
                   curses.A_REVERSE)

        # Draw current view
        view = self.current_view
        view_height = height - 0
        view.draw(self.stdscr, view_height, width)
        self.stdscr.refresh()


def main():
    parser = argparse.ArgumentParser(description="System Monitor TUI")
    parser.add_argument("--interval", type=float, default=1.0,
                       help="Update interval in seconds (default: 1.0)")
    args = parser.parse_args()

    app = SystemMonitorApp(interval=args.interval)

    try:
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
