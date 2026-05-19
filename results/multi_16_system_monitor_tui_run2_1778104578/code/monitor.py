#!/usr/bin/env python3
"""System Monitor TUI - Main entry point.

Usage:
    python monitor.py [--interval SECONDS]
"""

import argparse
import curses
import os
import signal
import sys
import time

from collector import Collector
from process import ProcessManager
from display import (
    draw_overview,
    draw_processes,
    draw_process_tree,
    draw_network,
    draw_disk,
    draw_battery_popup,
    draw_confirmation_popup,
    draw_input_popup,
    draw_message_popup,
)


def parse_args():
    parser = argparse.ArgumentParser(description='System Monitor TUI')
    parser.add_argument('--interval', '-i', type=float, default=1.0,
                        help='Update interval in seconds (default: 1.0)')
    return parser.parse_args()


def init_colors():
    """Initialize curses color pairs."""
    curses.start_color()
    curses.use_default_colors()

    # Color pairs
    curses.init_pair(1, curses.COLOR_GREEN, -1)    # low usage
    curses.init_pair(2, curses.COLOR_YELLOW, -1)    # medium usage
    curses.init_pair(3, curses.COLOR_RED, -1)       # high usage
    curses.init_pair(4, curses.COLOR_CYAN, -1)      # headers/accents
    curses.init_pair(5, curses.COLOR_WHITE, -1)     # normal


def main_loop(stdscr, interval):
    """Main curses event loop."""
    # Setup
    curses.curs_set(0)  # hide cursor
    stdscr.nodelay(True)  # non-blocking getch
    stdscr.timeout(100)   # 100ms timeout for getch
    init_colors()

    # State
    collector = Collector()
    proc_mgr = ProcessManager()

    current_view = 0  # 0=overview, 1=processes, 2=network, 3=disk
    VIEW_NAMES = ['Overview', 'Processes', 'Network', 'Disk']

    # Process view state
    selected_idx = 0
    scroll_offset = 0
    sort_col = 'pid'
    search_str = ''
    search_mode = False
    tree_mode = False

    # Data snapshots
    cpu_percents = [0.0]
    cpu_history = []  # ring buffer: list of [core0, core1, ...]
    MAX_HISTORY = max(1, int(60 / interval))
    mem_data = {}
    swap_data = {}
    uptime = 0.0
    loadavg = (0.0, 0.0, 0.0)
    net_io = []
    connections = {}
    disk_usage = []
    disk_io = []
    battery = None
    process_list = []
    process_tree = []

    last_update = 0.0
    running = True

    def refresh_data():
        """Fetch all data from collectors."""
        nonlocal cpu_percents, cpu_history, mem_data, swap_data, uptime
        nonlocal loadavg, net_io, connections, disk_usage, disk_io, battery
        nonlocal process_list, process_tree

        # CPU
        cpu_percents = collector.get_cpu_percent(interval)
        # Update history ring buffer
        if cpu_percents and len(cpu_percents) > 1:
            cpu_history.append(cpu_percents[1:])  # skip total
        elif cpu_percents:
            cpu_history.append(cpu_percents)
        if len(cpu_history) > MAX_HISTORY:
            cpu_history = cpu_history[-MAX_HISTORY:]

        # Memory & Swap
        mem = collector.get_memory()
        mem_data = mem
        swap_data = {
            'swap_total': mem.get('swap_total', 0),
            'swap_free': mem.get('swap_free', 0),
        }

        # Uptime & Load
        uptime = collector.get_uptime()
        loadavg = collector.get_loadavg()

        # Network
        net_io = collector.get_network_io(interval)
        connections = collector.get_tcp_connections()

        # Disk
        disk_usage = collector.get_disk_usage()
        disk_io = collector.get_disk_io(interval)

        # Battery
        battery = collector.get_battery()

        # Processes
        raw_list = proc_mgr.list_processes()
        # Sort if needed
        if sort_col != 'pid':
            proc_mgr.sort_by(sort_col)
            raw_list = proc_mgr._processes
        # Search
        if search_str:
            process_list = proc_mgr.search(raw_list, search_str)
        else:
            process_list = raw_list

        # Process tree
        if tree_mode:
            # Update process manager's internal list for tree building
            proc_mgr._processes = raw_list
            process_tree = proc_mgr.build_process_tree()

    # Initial data load
    # First CPU call returns zeros, so do a quick initial read
    collector.get_cpu_percent(0.1)
    time.sleep(0.1)
    refresh_data()
    last_update = time.time()

    while running:
        now = time.time()
        force_refresh = False

        # Check for keypress
        try:
            ch = stdscr.getch()
        except KeyboardInterrupt:
            break
        except Exception:
            ch = -1

        # Process key
        if ch != -1:
            if ch == ord('q') or ch == ord('Q') or ch == curses.KEY_F10:
                running = False
                break

            elif ch == curses.KEY_F5:
                force_refresh = True

            elif ch == 9:  # TAB
                current_view = (current_view + 1) % 4
                selected_idx = 0
                scroll_offset = 0

            elif ch == 27:  # ESC - clear search
                if search_str:
                    search_str = ''
                    force_refresh = True

            # View-specific keys
            elif current_view == 1:  # Process view
                if ch == ord('j') or ch == curses.KEY_DOWN:
                    if tree_mode:
                        max_idx = len(process_tree) - 1
                    else:
                        max_idx = len(process_list) - 1
                    if selected_idx < max_idx:
                        selected_idx += 1
                elif ch == ord('k') or ch == curses.KEY_UP:
                    if selected_idx > 0:
                        selected_idx -= 1
                elif ch == ord('c'):
                    sort_col = 'cpu'
                    proc_mgr.sort_by('cpu')
                    force_refresh = True
                    selected_idx = 0
                    scroll_offset = 0
                elif ch == ord('m'):
                    sort_col = 'mem'
                    proc_mgr.sort_by('mem')
                    force_refresh = True
                    selected_idx = 0
                    scroll_offset = 0
                elif ch == ord('p'):
                    sort_col = 'pid'
                    proc_mgr.sort_by('pid')
                    force_refresh = True
                    selected_idx = 0
                    scroll_offset = 0
                elif ch == ord('t'):
                    tree_mode = not tree_mode
                    force_refresh = True
                    selected_idx = 0
                    scroll_offset = 0
                elif ch == ord('/'):
                    # Enter search mode
                    curses.echo()
                    curses.curs_set(1)
                    stdscr.nodelay(False)
                    try:
                        stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, 'Search: ')
                        stdscr.clrtoeol()
                        s = ''
                        while True:
                            c = stdscr.getch()
                            if c == 10 or c == 13:  # Enter
                                break
                            elif c == 27:  # ESC
                                s = ''
                                break
                            elif c == curses.KEY_BACKSPACE or c == 127 or c == 8:
                                s = s[:-1]
                            elif 32 <= c <= 126:
                                s += chr(c)
                            # Redraw prompt
                            stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, ' ' * stdscr.getmaxyx()[1])
                            stdscr.addstr(stdscr.getmaxyx()[0] - 1, 0, f'Search: {s}')
                        search_str = s
                    except Exception:
                        search_str = ''
                    curses.noecho()
                    curses.curs_set(0)
                    stdscr.nodelay(True)
                    stdscr.timeout(100)
                    force_refresh = True
                    selected_idx = 0
                    scroll_offset = 0

                elif ch == ord('K'):
                    # Kill process
                    if tree_mode:
                        if 0 <= selected_idx < len(process_tree):
                            pid = process_tree[selected_idx][0].pid
                        else:
                            pid = None
                    else:
                        if 0 <= selected_idx < len(process_list):
                            pid = process_list[selected_idx].pid
                        else:
                            pid = None

                    if pid is not None:
                        confirm = draw_confirmation_popup(stdscr, f'Kill PID {pid}?')
                        if confirm:
                            success, msg = proc_mgr.kill(pid)
                            draw_message_popup(stdscr, msg)
                            force_refresh = True

                elif ch == ord('r'):
                    # Renice process
                    if tree_mode:
                        if 0 <= selected_idx < len(process_tree):
                            pid = process_tree[selected_idx][0].pid
                        else:
                            pid = None
                    else:
                        if 0 <= selected_idx < len(process_list):
                            pid = process_list[selected_idx].pid
                        else:
                            pid = None

                    if pid is not None:
                        val = draw_input_popup(stdscr, f'New nice value for PID {pid} (-20 to 19):')
                        if val is not None:
                            success, msg = proc_mgr.renice(pid, val)
                            draw_message_popup(stdscr, msg)
                            force_refresh = True

            elif current_view in (2, 3):  # Network or Disk view - allow scrolling
                if ch == ord('j') or ch == curses.KEY_DOWN:
                    scroll_offset += 1
                elif ch == ord('k') or ch == curses.KEY_UP:
                    if scroll_offset > 0:
                        scroll_offset -= 1

        # Refresh data on interval or forced
        if force_refresh or (now - last_update >= interval):
            try:
                refresh_data()
            except Exception as e:
                # Silently handle collection errors
                pass
            last_update = time.time()

        # Clear screen and draw
        stdscr.erase()

        try:
            if current_view == 0:
                draw_overview(stdscr, cpu_history, cpu_percents, mem_data, swap_data, uptime, loadavg)
            elif current_view == 1:
                if tree_mode:
                    draw_process_tree(stdscr, process_tree, selected_idx, scroll_offset)
                else:
                    draw_processes(stdscr, process_list, selected_idx, scroll_offset, sort_col, search_str)
            elif current_view == 2:
                draw_network(stdscr, net_io, connections)
            elif current_view == 3:
                draw_disk(stdscr, disk_usage, disk_io)

            # Battery popup in corner (always shown if battery present)
            draw_battery_popup(stdscr, battery)

            # View indicator at bottom-right
            h, w = stdscr.getmaxyx()
            indicator = f' [{VIEW_NAMES[current_view]}] '
            try:
                stdscr.addstr(h - 1, w - len(indicator), indicator, curses.A_REVERSE)
            except curses.error:
                pass

        except curses.error:
            pass

        stdscr.refresh()

        # Small sleep to prevent busy-waiting
        time.sleep(0.05)


def main():
    args = parse_args()
    interval = max(0.1, args.interval)

    def wrapped(stdscr):
        main_loop(stdscr, interval)

    try:
        curses.wrapper(wrapped)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
