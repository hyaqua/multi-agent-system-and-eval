"""views.py - Curses rendering classes for each view."""

import curses
import os
import signal
from typing import List, Dict, Optional, Deque

from ui_utils import (
    draw_progress_bar, draw_braille_graph, draw_box, draw_table_header,
    safe_addstr, format_bytes, format_bytes_per_sec, format_uptime,
    get_usage_color, COLOR_GREEN, COLOR_YELLOW, COLOR_RED,
    COLOR_CYAN, COLOR_WHITE, COLOR_BLUE, COLOR_MAGENTA
)
from data_collector import DataCollector


class BaseView:
    """Base class for all views."""

    def __init__(self, collector: DataCollector):
        self.collector = collector

    def draw(self, win, height: int, width: int) -> None:
        """Draw the view content. Override in subclasses."""
        pass

    def handle_key(self, key: int) -> Optional[str]:
        """Handle a keypress. Return 'redraw' if display needs refresh, else None."""
        return None


# ---------------------------------------------------------------------------
# OverviewView
# ---------------------------------------------------------------------------
class OverviewView(BaseView):
    """System overview: CPU, memory, swap, uptime, load, battery."""

    def draw(self, win, height: int, width: int) -> None:
        win.erase()
        c = self.collector

        y = 0

        # Title
        safe_addstr(win, y, 2, "SYSTEM OVERVIEW", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # --- CPU Section ---
        safe_addstr(win, y, 2, "CPU", curses.A_BOLD | curses.A_UNDERLINE)
        y += 1

        bar_width = min(60, width - 20)
        for core in c.cpu_per_core:
            if y >= height - 2:
                break
            label = f"CPU{core['core']}"
            draw_progress_bar(win, y, 4, bar_width, core['percent'], label=label)
            y += 1

        # Total CPU
        if y < height - 2:
            safe_addstr(win, y, 4, f"Total:  {c.cpu_total:5.1f}%",
                       curses.color_pair(get_usage_color(c.cpu_total)) | curses.A_BOLD)
            y += 1

        # CPU History graph
        if len(c._cpu_history) > 0 and y < height - 5:
            y += 1
            safe_addstr(win, y, 2, "CPU History (60s)", curses.A_BOLD)
            y += 1
            graph_width = min(width - 4, 120)
            draw_braille_graph(win, y, 4, graph_width, c._cpu_history)
            y += 2

        # --- Memory Section ---
        if y < height - 3:
            y += 1
            safe_addstr(win, y, 2, "Memory", curses.A_BOLD | curses.A_UNDERLINE)
            y += 1
            mem = c.memory
            if mem:
                draw_progress_bar(win, y, 4, bar_width, mem.get('percent', 0),
                                  label="RAM  ")
                y += 1
                safe_addstr(win, y, 4,
                           f"Total: {format_bytes(mem.get('total', 0))}  "
                           f"Used: {format_bytes(mem.get('used', 0))}  "
                           f"Free: {format_bytes(mem.get('free', 0))}  "
                           f"Avail: {format_bytes(mem.get('available', 0))}  "
                           f"Cached: {format_bytes(mem.get('cached', 0))}")
                y += 1

        # --- Swap Section ---
        if y < height - 3 and c.swap and c.swap.get('total', 0) > 0:
            y += 1
            safe_addstr(win, y, 2, "Swap", curses.A_BOLD | curses.A_UNDERLINE)
            y += 1
            draw_progress_bar(win, y, 4, bar_width, c.swap.get('percent', 0), label="Swap ")
            y += 1
            safe_addstr(win, y, 4,
                       f"Total: {format_bytes(c.swap.get('total', 0))}  "
                       f"Used: {format_bytes(c.swap.get('used', 0))}  "
                       f"Free: {format_bytes(c.swap.get('free', 0))}")
            y += 1

        # --- Uptime ---
        if y < height - 2:
            y += 1
            safe_addstr(win, y, 2, "Uptime:", curses.A_BOLD)
            safe_addstr(win, y, 12, format_uptime(c.uptime_seconds))
            y += 1

        # --- Load Averages ---
        if y < height - 2:
            safe_addstr(win, y, 2, "Load Avg:", curses.A_BOLD)
            safe_addstr(win, y, 14,
                       f"1m: {c.loadavg[0]:.2f}  5m: {c.loadavg[1]:.2f}  15m: {c.loadavg[2]:.2f}")
            y += 1

        # --- Battery ---
        if y < height - 2:
            y += 1
            if c.battery and c.battery.get('present'):
                bat = c.battery
                cap = bat.get('capacity', '?')
                status = bat.get('status', '?')
                tr = bat.get('time_remaining')
                line = f"Battery: {cap}% [{status}]"
                if tr is not None:
                    h = int(tr)
                    m = int((tr - h) * 60)
                    line += f"  Remaining: {h}h {m}m"
                safe_addstr(win, y, 2, line, curses.A_BOLD)
            else:
                safe_addstr(win, y, 2, "Battery: N/A")
            y += 1

        # Footer help
        safe_addstr(win, height - 1, 0,
                    " q/F10:Exit | Tab:Next View | F5:Refresh ",
                    curses.A_REVERSE)


# ---------------------------------------------------------------------------
# ProcessView
# ---------------------------------------------------------------------------
class ProcessView(BaseView):
    """Scrollable process list with sorting, search, kill, renice, tree view."""

    def __init__(self, collector: DataCollector):
        super().__init__(collector)
        self.scroll_offset = 0
        self.selected_index = 0
        self.sort_key = 'cpu'
        self.sort_reverse = True
        self.search_query = ''
        self.search_active = False  # True when user is typing search
        self.filter_active = False  # True when filter is applied (Enter locked)
        self.tree_mode = False
        # Flat mode state saved when switching to tree
        self._flat_scroll = 0
        self._flat_selected = 0

        # Modal states
        self._modal = None          # 'kill', 'renice', 'search'
        self._modal_prompt = ''     # prompt message
        self._modal_input = ''      # user input (for renice)
        self._modal_pid = None      # PID being acted on
        self._modal_error = ''      # error message

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def handle_key(self, key: int) -> Optional[str]:
        """Handle keypress. Return 'redraw' if the display should refresh."""

        # --- Modal: kill confirmation ---
        if self._modal == 'kill':
            if key in (ord('y'), ord('Y')):
                pid = self._modal_pid
                self._modal = None
                self._modal_prompt = ''
                self._modal_error = ''
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except PermissionError:
                        self._modal_error = f"Permission denied killing PID {pid}"
                        return 'redraw'
                    except ProcessLookupError:
                        self._modal_error = f"PID {pid} no longer exists"
                        return 'redraw'
                self.collector.update()
                return 'redraw'
            elif key in (ord('n'), ord('N'), 27):  # n or Escape
                self._modal = None
                self._modal_prompt = ''
                self._modal_input = ''
                self._modal_error = ''
                return 'redraw'
            return None

        # --- Modal: renice input ---
        if self._modal == 'renice':
            if key == 27:  # Escape
                self._modal = None
                self._modal_prompt = ''
                self._modal_input = ''
                self._modal_error = ''
                return 'redraw'
            elif key in (curses.KEY_ENTER, 10, 13):  # Enter
                pid = self._modal_pid
                val = self._modal_input.strip()
                self._modal = None
                self._modal_prompt = ''
                if pid is not None and val:
                    try:
                        nice_val = int(val)
                        if nice_val < -20:
                            nice_val = -20
                        if nice_val > 19:
                            nice_val = 19
                        os.setpriority(os.PRIO_PROCESS, pid, nice_val)
                    except ValueError:
                        self._modal_error = f"Invalid nice value: {val}"
                        return 'redraw'
                    except PermissionError:
                        self._modal_error = f"Permission denied renice PID {pid}"
                        return 'redraw'
                    except ProcessLookupError:
                        self._modal_error = f"PID {pid} no longer exists"
                        return 'redraw'
                self._modal_input = ''
                self._modal_error = ''
                return 'redraw'
            elif key in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
                self._modal_input = self._modal_input[:-1]
                return 'redraw'
            elif 32 <= key <= 126:
                self._modal_input += chr(key)
                return 'redraw'
            return None

        # --- Modal: search ---
        if self._modal == 'search':
            if key == 27:  # Escape - cancel search
                self._modal = None
                self.search_query = ''
                self.filter_active = False
                self.search_active = False
                self._modal_prompt = ''
                self._modal_input = ''
                self.selected_index = 0
                self.scroll_offset = 0
                return 'redraw'
            elif key in (curses.KEY_ENTER, 10, 13):  # Enter - lock filter
                self._modal = None
                self.search_active = False
                self.filter_active = True
                self._modal_prompt = ''
                self._modal_input = ''
                self.selected_index = 0
                self.scroll_offset = 0
                return 'redraw'
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self._modal_input = self._modal_input[:-1]
                self.search_query = self._modal_input
                if not self.search_query:
                    self.filter_active = False
                self.selected_index = 0
                self.scroll_offset = 0
                return 'redraw'
            elif 32 <= key <= 126:
                self._modal_input += chr(key)
                self.search_query = self._modal_input
                self.filter_active = True
                self.selected_index = 0
                self.scroll_offset = 0
                return 'redraw'
            return None

        # --- Normal navigation ---
        if key == ord('/'):
            self._modal = 'search'
            self._modal_prompt = 'Search: '
            self._modal_input = ''
            self.search_query = ''
            self.search_active = True
            self.filter_active = False
            return 'redraw'

        if key == ord('t'):
            if self.tree_mode:
                self.tree_mode = False
                self.scroll_offset = self._flat_scroll
                self.selected_index = self._flat_selected
            else:
                self._flat_scroll = self.scroll_offset
                self._flat_selected = self.selected_index
                self.tree_mode = True
                self.scroll_offset = 0
                self.selected_index = 0
            return 'redraw'

        if key in (curses.KEY_DOWN, ord('j')):
            self._move_selection(1)
            return 'redraw'
        if key in (curses.KEY_UP, ord('k')):
            self._move_selection(-1)
            return 'redraw'
        if key in (curses.KEY_NPAGE, ord(' ')):
            # Page down
            visible = self._visible_rows()
            self._move_selection(visible)
            return 'redraw'
        if key == curses.KEY_PPAGE:
            visible = self._visible_rows()
            self._move_selection(-visible)
            return 'redraw'
        if key == ord('g'):
            self.selected_index = 0
            self.scroll_offset = 0
            return 'redraw'
        if key == ord('G'):
            plist = self._get_display_list()
            self.selected_index = max(0, len(plist) - 1)
            self._clamp_scroll()
            return 'redraw'

        # Sort keys
        if key == ord('c'):
            if self.sort_key == 'cpu':
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_key = 'cpu'
                self.sort_reverse = True
            self.selected_index = 0
            self.scroll_offset = 0
            return 'redraw'
        if key == ord('m'):
            if self.sort_key == 'mem':
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_key = 'mem'
                self.sort_reverse = True
            self.selected_index = 0
            self.scroll_offset = 0
            return 'redraw'
        if key == ord('p'):
            if self.sort_key == 'pid':
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_key = 'pid'
                self.sort_reverse = True
            self.selected_index = 0
            self.scroll_offset = 0
            return 'redraw'

        # Kill
        if key == ord('K'):
            plist = self._get_display_list()
            if plist and 0 <= self.selected_index < len(plist):
                pid = plist[self.selected_index]['pid']
                self._modal = 'kill'
                self._modal_pid = pid
                self._modal_prompt = f"Kill PID {pid}? (y/n)"
                self._modal_error = ''
                return 'redraw'

        # Renice
        if key == ord('r'):
            plist = self._get_display_list()
            if plist and 0 <= self.selected_index < len(plist):
                pid = plist[self.selected_index]['pid']
                self._modal = 'renice'
                self._modal_pid = pid
                self._modal_input = ''
                self._modal_prompt = f"New nice value for PID {pid}: "
                self._modal_error = ''
                return 'redraw'

        return None

    def _move_selection(self, delta: int) -> None:
        plist = self._get_display_list()
        if not plist:
            self.selected_index = 0
            return
        self.selected_index += delta
        if self.selected_index < 0:
            self.selected_index = 0
        if self.selected_index >= len(plist):
            self.selected_index = len(plist) - 1
        self._clamp_scroll()

    def _clamp_scroll(self) -> None:
        """Ensure scroll_offset keeps selected_index in view."""
        plist = self._get_display_list()
        if not plist:
            self.scroll_offset = 0
            return
        visible = self._visible_rows()
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        if self.selected_index >= self.scroll_offset + visible:
            self.scroll_offset = self.selected_index - visible + 1
        if self.scroll_offset < 0:
            self.scroll_offset = 0
        if self.scroll_offset >= len(plist):
            self.scroll_offset = max(0, len(plist) - 1)

    # ------------------------------------------------------------------
    # Process list building
    # ------------------------------------------------------------------
    def _get_display_list(self) -> List[Dict]:
        """Return the sorted/filtered/treemode list for display."""
        procs = self.collector.processes

        # Filter
        query = self.search_query.strip().lower() if (self.search_active or self.filter_active) else ''
        if query:
            procs = [p for p in procs if query in p['command'].lower()]

        if self.tree_mode:
            return self._build_tree_list(procs)
        else:
            # Sort flat list
            reverse = self.sort_reverse
            key_map = {
                'cpu': lambda p: p['cpu'],
                'mem': lambda p: p['mem'],
                'pid': lambda p: p['pid'],
            }
            sort_fn = key_map.get(self.sort_key, key_map['cpu'])
            procs = sorted(procs, key=sort_fn, reverse=reverse)
            return procs

    def _build_tree_list(self, procs: List[Dict]) -> List[Dict]:
        """Build a tree-ordered display list with indent info."""
        if not procs:
            return []

        pids = {p['pid'] for p in procs}
        children: Dict[int, List[Dict]] = {}
        for p in procs:
            ppid = p.get('ppid', 0)
            if ppid not in children:
                children[ppid] = []
            children[ppid].append(p)

        # Sort children by PID
        for ppid in children:
            children[ppid].sort(key=lambda x: x['pid'])

        result = []

        def _walk(pid, depth, prefix):
            stack = children.get(pid, [])
            for i, p in enumerate(stack):
                is_last = (i == len(stack) - 1)
                if depth == 0:
                    indent = ''
                else:
                    connector = '└─ ' if is_last else '├─ '
                    indent = prefix + connector
                p['_tree_indent'] = indent
                p['_tree_depth'] = depth
                result.append(p)
                if p['pid'] in children:
                    new_prefix = prefix + ('   ' if is_last else '│  ')
                    _walk(p['pid'], depth + 1, new_prefix)

        # Roots: pid not in the list as a child of someone, or ppid=0
        all_pids = {p['pid'] for p in procs}
        roots = []
        for p in procs:
            if p.get('ppid', 0) not in all_pids or p.get('ppid', 0) == 0:
                roots.append(p)
        roots.sort(key=lambda x: x['pid'])

        for i, p in enumerate(roots):
            is_last = (i == len(roots) - 1)
            p['_tree_indent'] = ''
            p['_tree_depth'] = 0
            result.append(p)
            if p['pid'] in children:
                new_prefix = '   ' if is_last else '│  '
                _walk(p['pid'], 1, new_prefix)

        return result

    def _visible_rows(self) -> int:
        """How many rows can be displayed (excluding header, footer, modals)."""
        # 1 header + 1 footer = 2 rows reserved
        return max(1, curses.LINES - 3)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self, win, height: int, width: int) -> None:
        win.erase()

        y = 0
        # Title
        mode_label = "[Tree]" if self.tree_mode else "[List]"
        filter_label = f" [filter: '{self.search_query}']" if (self.filter_active or self.search_active) else ""
        title = f"PROCESSES {mode_label}{filter_label}"
        safe_addstr(win, y, 2, title, curses.A_BOLD | curses.A_REVERSE)
        y += 1

        # Table header
        col_names = [
            ("PID", 7), ("USER", 10), ("CPU%", 7), ("MEM%", 7), ("STATE", 6), ("COMMAND", 20)
        ]
        if self.tree_mode:
            # In tree mode, PID col is a bit wider
            col_names = [
                ("PID", 20), ("CPU%", 7), ("MEM%", 7), ("STATE", 6), ("COMMAND", 20)
            ]

        sort_k = self.sort_key.upper() if self.sort_key in ('cpu', 'mem', 'pid') else ''
        draw_table_header(win, y, 0, col_names, sort_key=sort_k, sort_reverse=self.sort_reverse)
        y += 1

        plist = self._get_display_list()
        data_start_y = y
        visible = max(1, height - y - 2)  # reserve 2 for footer and modal

        # Clamp scroll
        if self.scroll_offset >= len(plist):
            self.scroll_offset = max(0, len(plist) - visible)
        if self.selected_index >= len(plist):
            self.selected_index = max(0, len(plist) - 1)

        end_idx = min(self.scroll_offset + visible, len(plist))

        for i in range(self.scroll_offset, end_idx):
            p = plist[i]
            draw_y = data_start_y + (i - self.scroll_offset)
            if draw_y >= height - 1:
                break

            is_selected = (i == self.selected_index)
            attr = curses.A_REVERSE if is_selected else 0

            if self.tree_mode:
                indent = p.get('_tree_indent', '')
                cmd = p['command']
                cmd_str = cmd[:width - 40] if width > 40 else cmd[:20]
                line = f"{indent}{p['pid']:<6}"
                # Fill to 20 for PID column
                if len(line) > 20:
                    line = line[:20]
                else:
                    line = line.ljust(20)
                line += f"{p['cpu']:6.1f} {p['mem']:6.1f} {p['state']:<5} {cmd_str}"
            else:
                pid_s = str(p['pid']).rjust(6)
                user_s = p['user'][:9].ljust(10)
                cpu_s = f"{p['cpu']:6.1f}"
                mem_s = f"{p['mem']:6.1f}"
                state_s = p['state'][:5].ljust(6)
                cmd_s = p['command'][:width - 40] if width > 40 else p['command'][:20]
                line = f"{pid_s}{user_s}{cpu_s}{mem_s}{state_s}{cmd_s}"

            safe_addstr(win, draw_y, 0, line[:width - 1], attr)

        # Footer / help
        footer_y = height - 1
        footer = (
            " j/k:Nav | c:CPU m:MEM p:PID sort | /:Search | K:Kill | r:Renice | t:Tree | q:Quit"
        )
        safe_addstr(win, footer_y, 0, footer[:width - 1], curses.A_REVERSE)

        # Modal overlay
        self._draw_modal(win, height, width)

    def _draw_modal(self, win, height: int, width: int) -> None:
        """Draw any active modal prompt."""
        if not self._modal:
            return

        modal_y = height - 2
        safe_addstr(win, modal_y, 0, " " * (width - 1), curses.A_REVERSE)

        if self._modal == 'kill':
            msg = self._modal_prompt
            safe_addstr(win, modal_y, 2, msg, curses.A_BOLD | curses.A_REVERSE)
        elif self._modal == 'renice':
            msg = self._modal_prompt + self._modal_input
            safe_addstr(win, modal_y, 2, msg, curses.A_BOLD | curses.A_REVERSE)
            safe_addstr(win, modal_y, len(msg) + 2, " ", 0)  # cursor placeholder
        elif self._modal == 'search':
            msg = "Search: " + self._modal_input
            safe_addstr(win, modal_y, 2, msg, curses.A_BOLD | curses.A_REVERSE)

        if self._modal_error:
            safe_addstr(win, modal_y, 2,
                       self._modal_error[:width - 3],
                       curses.A_BOLD | curses.color_pair(COLOR_RED) | curses.A_REVERSE)


# ---------------------------------------------------------------------------
# NetworkView
# ---------------------------------------------------------------------------
class NetworkView(BaseView):
    """Network I/O rates and TCP connection states."""

    def draw(self, win, height: int, width: int) -> None:
        win.erase()
        y = 0
        c = self.collector

        safe_addstr(win, y, 2, "NETWORK", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # --- Interface rates ---
        safe_addstr(win, y, 2, "Interface Rates", curses.A_BOLD | curses.A_UNDERLINE)
        y += 1

        if c.network:
            # Header
            safe_addstr(win, y, 4, f"{'Interface':<12} {'RX Rate':>15} {'TX Rate':>15}")
            y += 1
            for iface in c.network:
                if y >= height - 3:
                    break
                rx_s = format_bytes_per_sec(iface['rx_rate'])
                tx_s = format_bytes_per_sec(iface['tx_rate'])
                safe_addstr(win, y, 4,
                           f"{iface['interface']:<12} {rx_s:>15} {tx_s:>15}")
                y += 1
        else:
            safe_addstr(win, y, 4, "N/A")
            y += 1

        # --- TCP Connections ---
        y += 1
        safe_addstr(win, y, 2, "TCP Connections", curses.A_BOLD | curses.A_UNDERLINE)
        y += 1

        if c.tcp_counts:
            states_order = ['ESTABLISHED', 'LISTEN', 'TIME_WAIT', 'CLOSE_WAIT',
                           'SYN_SENT', 'SYN_RECV', 'FIN_WAIT1', 'FIN_WAIT2',
                           'CLOSING', 'LAST_ACK', 'CLOSE']
            for state in states_order:
                if state in c.tcp_counts:
                    if y >= height - 2:
                        break
                    safe_addstr(win, y, 4, f"{state}: {c.tcp_counts[state]}")
                    y += 1
            # Show any remaining states not in our order list
            for state, count in sorted(c.tcp_counts.items()):
                if state not in states_order:
                    if y >= height - 2:
                        break
                    safe_addstr(win, y, 4, f"{state}: {count}")
                    y += 1
        else:
            safe_addstr(win, y, 4, "N/A")
            y += 1

        # Footer
        safe_addstr(win, height - 1, 0,
                   " q/F10:Exit | Tab:Next View | F5:Refresh ",
                   curses.A_REVERSE)


# ---------------------------------------------------------------------------
# DiskView
# ---------------------------------------------------------------------------
class DiskView(BaseView):
    """Disk usage and I/O rates."""

    def draw(self, win, height: int, width: int) -> None:
        win.erase()
        y = 0
        c = self.collector

        safe_addstr(win, y, 2, "DISK", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # --- Disk Usage ---
        safe_addstr(win, y, 2, "Filesystem Usage", curses.A_BOLD | curses.A_UNDERLINE)
        y += 1

        if c.disk_usage:
            # Header
            safe_addstr(win, y, 2,
                       f"{'Mount':<16} {'Total':>10} {'Used':>10} {'Free':>10} {'Use%':>6}")
            y += 1
            for fs in c.disk_usage:
                if y >= height // 2:  # Only use top half for usage
                    break
                pct = fs['percent']
                color = get_usage_color(pct)
                safe_addstr(win, y, 2,
                           f"{fs['filesystem']:<16} "
                           f"{format_bytes(fs['total']):>10} "
                           f"{format_bytes(fs['used']):>10} "
                           f"{format_bytes(fs['free']):>10} "
                           f"{pct:5.1f}%",
                           curses.color_pair(color))
                y += 1
        else:
            safe_addstr(win, y, 4, "N/A")
            y += 1

        # --- Disk I/O ---
        y += 1
        safe_addstr(win, y, 2, "Disk I/O Rates", curses.A_BOLD | curses.A_UNDERLINE)
        y += 1

        if c.disk_io:
            safe_addstr(win, y, 4, f"{'Device':<12} {'Read':>15} {'Write':>15}")
            y += 1
            for d in c.disk_io:
                if y >= height - 2:
                    break
                rd_s = format_bytes_per_sec(d['read_rate'])
                wr_s = format_bytes_per_sec(d['write_rate'])
                safe_addstr(win, y, 4,
                           f"{d['device']:<12} {rd_s:>15} {wr_s:>15}")
                y += 1
        else:
            safe_addstr(win, y, 4, "N/A")
            y += 1

        # Footer
        safe_addstr(win, height - 1, 0,
                   " q/F10:Exit | Tab:Next View | F5:Refresh ",
                   curses.A_REVERSE)
