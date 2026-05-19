#!/usr/bin/env python3
"""System Monitor TUI - A terminal-based system monitor using /proc and /sys.

Usage:
    python main.py [--interval SECONDS]
"""

import argparse
import os
import signal
import sys

import collectors
import ui
import views

# Module-level flag set by SIGWINCH handler
_resize_needed = False


def _signal_resize(signum, frame):
    """Signal handler that only sets a flag. No curses calls."""
    global _resize_needed
    _resize_needed = True


def check_terminal():
    """Check if a real terminal (TTY) is available.

    Returns True if both stdin and stdout are connected to a terminal.
    Returns False otherwise, printing a user-friendly error message.
    """
    if not os.isatty(sys.stdout.fileno()) or not os.isatty(sys.stdin.fileno()):
        print(
            "Error: This application requires a real terminal (TTY).",
            file=sys.stderr,
        )
        return False
    return True


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="System Monitor TUI - monitor system resources in the terminal"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0, minimum: 0.1)",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit",
    )
    return parser.parse_args()


def _clear_search_on_view(view):
    """Clear any search/filter state on a view."""
    if hasattr(view, 'search_term'):
        view.search_term = ''
    if hasattr(view, 'search_mode'):
        view.search_mode = False
    if hasattr(view, 'search_input'):
        view.search_input = ''
    if hasattr(view, '_apply_filter_and_sort'):
        view._apply_filter_and_sort()


def main_loop(stdscr, interval: float):
    """Main curses event loop."""
    import curses  # local import for clarity within the curses context
    global _resize_needed

    # Setup
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(False)
    curses.halfdelay(max(1, int(interval * 10)))
    ui.init_colors()

    # Create views (they will initialise their own sub-windows)
    view_list = [
        views.OverviewView(),
        views.ProcessesView(),
        views.NetworkView(),
        views.DiskView(),
    ]
    # Initialise sub-windows for each view
    for v in view_list:
        v.init_window()

    active_view_idx = 0
    force_refresh = True

    # Register signal handler (flag-only, no curses calls)
    signal.signal(signal.SIGWINCH, _signal_resize)

    running = True

    while running:
        # --- Safe resize handling ---
        if _resize_needed:
            _resize_needed = False
            curses.endwin()
            stdscr = curses.initscr()
            curses.curs_set(0)
            curses.noecho()
            curses.halfdelay(max(1, int(interval * 10)))
            ui.init_colors()
            # Resize all view sub-windows
            for v in view_list:
                v.resize()
            force_refresh = True

        height, width = stdscr.getmaxyx()

        # Force refresh handling
        if force_refresh:
            force_refresh = False
            curses.halfdelay(1)  # Short delay for responsiveness after refresh
        else:
            curses.halfdelay(max(1, int(interval * 10)))

        # Clear screen
        stdscr.erase()

        # Get active view
        try:
            active_view = view_list[active_view_idx]
        except IndexError:
            active_view_idx = 0
            active_view = view_list[0]

        # Draw tab bar on line 0 (full-width with active tab highlighted)
        view_names = [v.name for v in view_list]
        ui.draw_tab_bar(stdscr, active_view_idx, view_names)

        # Draw active view in its sub-window
        try:
            active_view.draw(width, height)
        except Exception as e:
            try:
                stdscr.addstr(1, 0, f"Error: {e}"[:width])
            except curses.error:
                pass

        # Show search mode indicator on the last line
        if hasattr(active_view, 'search_mode') and active_view.search_mode:
            try:
                search_display = f"Search: {active_view.search_input}_"
                stdscr.addstr(height - 1, 0, search_display[:width], curses.A_REVERSE)
            except curses.error:
                pass

        # Show confirmation prompts or status messages
        if hasattr(active_view, 'prompt_mode') and active_view.prompt_mode:
            try:
                prompt_str = f" {active_view.prompt_mode}: {active_view.prompt_input}_ "
                stdscr.addstr(height - 1, max(0, width - len(prompt_str) - 2),
                             prompt_str[:width], curses.A_REVERSE)
            except curses.error:
                pass

        # Refresh sub-window then stdscr
        try:
            active_view.win.noutrefresh()
        except curses.error:
            pass
        stdscr.refresh()

        # Get input
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        if key == -1:
            continue

        # Global key handlers
        if key == ord("q") or key == curses.KEY_F10:
            running = False
            continue
        elif key == 9:  # Tab
            active_view_idx = (active_view_idx + 1) % len(view_list)
            force_refresh = True
            continue
        elif key == curses.KEY_BTAB:  # Shift-Tab
            active_view_idx = (active_view_idx - 1) % len(view_list)
            force_refresh = True
            continue
        elif key == curses.KEY_F5:
            collectors.reset_cache()
            force_refresh = True
            continue
        elif key == curses.KEY_RESIZE:
            force_refresh = True
            continue
        elif key == 27:  # Escape
            _clear_search_on_view(active_view)
            force_refresh = True
            continue

        # Pass key to active view
        handled = active_view.handle_key(key)
        if handled:
            force_refresh = True


def main():
    """Entry point."""
    args = parse_args()

    if args.version:
        print("System Monitor TUI v1.0.0")
        return 0

    # Check terminal availability before initializing curses
    if not check_terminal():
        return 1

    interval = max(0.1, args.interval)

    # Import curses only after confirming we have a terminal
    try:
        import curses
    except ImportError as e:
        print(
            f"Error: Failed to import curses module: {e}",
            file=sys.stderr,
        )
        return 1

    try:
        curses.wrapper(main_loop, interval)
    except KeyboardInterrupt:
        pass
    except curses.error as e:
        print(
            f"Terminal initialisation failed: {e}. Are you running in a terminal?",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
