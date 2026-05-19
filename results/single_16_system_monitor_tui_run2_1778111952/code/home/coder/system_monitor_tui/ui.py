"""Main curses UI controller for system_monitor_tui."""

import curses
import signal
import time
import os
from .collectors.cpu import CPUCollector
from .collectors.memory import MemoryCollector
from .collectors.system import SystemCollector
from .collectors.processes import ProcessCollector
from .collectors.network import NetworkCollector
from .collectors.disk import DiskCollector
from .collectors.battery import BatteryCollector
from .views.overview import OverviewView
from .views.processes import ProcessesView
from .views.network import NetworkView
from .views.disk import DiskView


class SystemMonitorUI:
    """Main TUI application."""

    VIEW_OVERVIEW = 0
    VIEW_PROCESSES = 1
    VIEW_NETWORK = 2
    VIEW_DISK = 3

    VIEW_NAMES = ["Overview", "Processes", "Network", "Disk"]

    def __init__(self, interval=1.0):
        self.interval = interval
        self.running = True
        self.current_view = self.VIEW_OVERVIEW
        self.force_refresh = False

        # Collectors
        self.cpu_collector = CPUCollector()
        self.memory_collector = MemoryCollector()
        self.system_collector = SystemCollector()
        self.process_collector = ProcessCollector()
        self.network_collector = NetworkCollector()
        self.disk_collector = DiskCollector()
        self.battery_collector = BatteryCollector()

        # Cached data from last update
        self.cpu_data = None
        self.mem_data = None
        self.swap_data = None
        self.sys_data = None
        self.processes = []
        self.net_data = None
        self.conn_counts = None
        self.disk_usage = None
        self.disk_io = None
        self.battery_data = None

        # Views
        self.overview_view = OverviewView()
        self.processes_view = ProcessesView()
        self.network_view = NetworkView()
        self.disk_view = DiskView()

        self.screen = None
        self.colors_initialized = False

    def init_colors(self):
        """Initialize curses color pairs."""
        if self.colors_initialized:
            return
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_BLUE, -1)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(8, curses.COLOR_MAGENTA, -1)

        self.colors_initialized = True

    def get_color(self, usage):
        """Return color pair index based on usage percentage."""
        if usage < 50:
            return curses.color_pair(1)
        elif usage < 80:
            return curses.color_pair(2)
        else:
            return curses.color_pair(3)

    def run(self):
        """Start the curses TUI."""
        self.screen = curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        """Main curses loop."""
        self.screen = stdscr
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)

        self.init_colors()
        signal.signal(signal.SIGWINCH, lambda sig, frame: self._handle_resize())

        last_update = 0
        self.update_all_data()

        try:
            while self.running:
                now = time.time()

                key = stdscr.getch()
                if key != -1:
                    self._handle_key(key)

                if self.force_refresh or (now - last_update >= self.interval):
                    self.update_all_data()
                    last_update = now
                    self.force_refresh = False

                try:
                    self._draw(stdscr)
                except curses.error:
                    pass

                time.sleep(0.05)

        finally:
            self._cleanup()

    def _cleanup(self):
        """Cleanup terminal state before exit."""
        curses.curs_set(1)
        curses.endwin()

    def _handle_resize(self):
        """Handle terminal resize."""
        if self.screen:
            curses.endwin()
            self.screen.refresh()
            self.force_refresh = True

    def update_all_data(self):
        """Update all data collectors and cache results."""
        # CPU
        global_pct, per_core, cpu_history, per_core_history = self.cpu_collector.update()
        self.cpu_data = {
            'global': global_pct,
            'per_core': per_core,
            'history': cpu_history,
            'per_core_history': per_core_history,
            'cpu_count': self.cpu_collector.cpu_count,
        }

        # Memory
        self.memory_collector.update()
        self.mem_data = self.memory_collector.get_summary()
        self.swap_data = self.memory_collector.get_swap()

        # System
        self.sys_data = self.system_collector.update()

        # Processes
        self.processes = self.process_collector.update()

        # Network
        self.net_data = self.network_collector.update()
        self.conn_counts = self.network_collector.get_connection_counts()

        # Disk
        self.disk_usage = self.disk_collector.get_all_usage()
        self.disk_io = self.disk_collector.get_io_stats()

        # Battery
        self.battery_data = self.battery_collector.update()

    def _handle_key(self, key):
        """Handle keyboard input."""
        # Handle terminal resize
        if key == curses.KEY_RESIZE:
            self.force_refresh = True
            if self.screen:
                self.screen.erase()
                self.screen.refresh()
            return

        # Global keys
        if key == ord('q') or key == curses.KEY_F10:
            self.running = False
            return

        if key == curses.KEY_F5:
            self.force_refresh = True
            return

        # Tab cycles between views
        if key == ord('\t') or key == 9:
            self.current_view = (self.current_view + 1) % 4
            self.processes_view.search_mode = False
            self.processes_view.search_query = ""
            return

        # View-specific keys
        if self.current_view == self.VIEW_PROCESSES:
            self._handle_process_keys(key)

    def _handle_process_keys(self, key):
        """Handle process view specific keys."""
        pv = self.processes_view

        # Search mode
        if pv.search_mode:
            if key == 27:  # Escape
                pv.search_mode = False
                pv.search_query = ""
                pv.scroll_offset = 0
                return
            elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                if pv.search_query:
                    pv.search_query = pv.search_query[:-1]
                pv.scroll_offset = 0
                return
            elif 32 <= key <= 126:
                pv.search_query += chr(key)
                pv.scroll_offset = 0
                return
            return

        # Not in search mode
        if key == ord('/'):
            pv.search_mode = True
            pv.search_query = ""
            return

        if key == 27:  # Escape
            pv.search_query = ""
            pv.scroll_offset = 0
            return

        if key == ord('j') or key == curses.KEY_DOWN:
            total = len(pv.filtered_processes)
            if total > 0:
                pv.selected_index = min(pv.selected_index + 1, total - 1)
                self._ensure_visible(pv)
            return

        if key == ord('k') or key == curses.KEY_UP:
            pv.selected_index = max(pv.selected_index - 1, 0)
            self._ensure_visible(pv)
            return

        if key == ord('c'):
            pv.sort_key = 'cpu'
            pv.sort_reverse = True
            return

        if key == ord('m'):
            pv.sort_key = 'mem'
            pv.sort_reverse = True
            return

        if key == ord('p'):
            pv.sort_key = 'pid'
            pv.sort_reverse = False
            return

        if key == ord('t'):
            pv.show_tree = not pv.show_tree
            pv.scroll_offset = 0
            pv.selected_index = 0
            return

        if key == ord('K'):
            self._kill_process(pv)
            return

        if key == ord('r'):
            self._renice_process(pv)
            return

        if key == curses.KEY_NPAGE or key == ord(' '):
            total = len(pv.filtered_processes)
            if total > 0:
                pv.scroll_offset += pv.visible_rows
                pv.selected_index = min(pv.selected_index + pv.visible_rows, total - 1)
            return

        if key == curses.KEY_PPAGE:
            pv.scroll_offset = max(0, pv.scroll_offset - pv.visible_rows)
            pv.selected_index = max(0, pv.selected_index - pv.visible_rows)
            return

        if key == ord('g'):
            pv.selected_index = 0
            pv.scroll_offset = 0
            return

        if key == ord('G'):
            total = len(pv.filtered_processes)
            if total > 0:
                pv.selected_index = total - 1
                pv.scroll_offset = max(0, total - pv.visible_rows)
            return

    def _ensure_visible(self, pv):
        """Ensure selected item is visible."""
        total = len(pv.filtered_processes)
        if total == 0:
            pv.selected_index = 0
            pv.scroll_offset = 0
            return
        if pv.selected_index < 0:
            pv.selected_index = 0
        if pv.selected_index >= total:
            pv.selected_index = total - 1
        if pv.selected_index < pv.scroll_offset:
            pv.scroll_offset = pv.selected_index
        elif pv.selected_index >= pv.scroll_offset + pv.visible_rows:
            pv.scroll_offset = pv.selected_index - pv.visible_rows + 1
        if pv.scroll_offset < 0:
            pv.scroll_offset = 0

    def _kill_process(self, pv):
        """Kill selected process after confirmation."""
        total = len(pv.filtered_processes)
        if total == 0 or pv.selected_index < 0 or pv.selected_index >= total:
            return

        proc_item = pv.filtered_processes[pv.selected_index]
        if isinstance(proc_item, tuple):
            proc = proc_item[0]
        else:
            proc = proc_item

        confirmed = self._show_confirm(
            f"Kill process {proc.pid} ({proc.command[:30]})? (y/n)"
        )
        if confirmed:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except (PermissionError, ProcessLookupError) as e:
                self._show_message(f"Error: {e}", 2)

    def _renice_process(self, pv):
        """Renice selected process."""
        total = len(pv.filtered_processes)
        if total == 0 or pv.selected_index < 0 or pv.selected_index >= total:
            return

        proc_item = pv.filtered_processes[pv.selected_index]
        if isinstance(proc_item, tuple):
            proc = proc_item[0]
        else:
            proc = proc_item

        new_nice = self._show_input(f"New nice value for PID {proc.pid} (-20 to 19): ")
        if new_nice is not None and new_nice.strip():
            try:
                nice_val = int(new_nice.strip())
                if nice_val < -20 or nice_val > 19:
                    self._show_message("Nice value must be between -20 and 19", 2)
                    return
                os.system(f"renice {nice_val} -p {proc.pid} > /dev/null 2>&1")
            except ValueError:
                self._show_message("Invalid nice value", 2)

    def _show_confirm(self, message):
        """Show a confirmation prompt."""
        if not self.screen:
            return False
        try:
            h, w = self.screen.getmaxyx()
            self.screen.addstr(h - 1, 0, message + " ", curses.A_REVERSE)
            self.screen.clrtoeol()
            self.screen.refresh()
            curses.curs_set(1)
            self.screen.nodelay(False)
            key = self.screen.getch()
            self.screen.nodelay(True)
            curses.curs_set(0)
            return key in (ord('y'), ord('Y'))
        except curses.error:
            return False

    def _show_input(self, prompt):
        """Show an input prompt. Returns string or None."""
        if not self.screen:
            return None
        try:
            h, w = self.screen.getmaxyx()
            input_str = ""
            curses.curs_set(1)
            self.screen.nodelay(False)

            while True:
                full_prompt = prompt + input_str
                self.screen.addstr(h - 1, 0, full_prompt[:w - 1] + " " * max(0, w - len(full_prompt) - 1))
                self.screen.clrtoeol()
                self.screen.refresh()
                key = self.screen.getch()
                if key == ord('\n') or key == curses.KEY_ENTER or key == 10 or key == 13:
                    break
                elif key == 27:  # Escape
                    input_str = None
                    break
                elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:
                    input_str = input_str[:-1]
                elif 32 <= key <= 126:
                    input_str += chr(key)

            self.screen.nodelay(True)
            curses.curs_set(0)
            return input_str
        except curses.error:
            self.screen.nodelay(True)
            curses.curs_set(0)
            return None

    def _show_message(self, message, duration=2):
        """Show a message temporarily."""
        if not self.screen:
            return
        try:
            h, w = self.screen.getmaxyx()
            self.screen.addstr(h - 1, 0, message[:w - 1] + " " * max(0, w - len(message) - 1), curses.A_REVERSE)
            self.screen.clrtoeol()
            self.screen.refresh()
            time.sleep(duration)
        except curses.error:
            pass

    def _draw(self, stdscr):
        """Draw the current view."""
        try:
            stdscr.erase()
            h, w = stdscr.getmaxyx()

            if h < 5 or w < 40:
                stdscr.addstr(0, 0, "Terminal too small")
                stdscr.refresh()
                return

            self._draw_header(stdscr, h, w)

            body_top = 2
            body_height = h - 3

            if self.current_view == self.VIEW_OVERVIEW:
                self.overview_view.draw(stdscr, body_top, body_height, w, self)
            elif self.current_view == self.VIEW_PROCESSES:
                self.processes_view.draw(stdscr, body_top, body_height, w, self)
            elif self.current_view == self.VIEW_NETWORK:
                self.network_view.draw(stdscr, body_top, body_height, w, self)
            elif self.current_view == self.VIEW_DISK:
                self.disk_view.draw(stdscr, body_top, body_height, w, self)

            self._draw_footer(stdscr, h, w)
            stdscr.refresh()
        except curses.error:
            pass

    def _draw_header(self, stdscr, h, w):
        """Draw top header bar."""
        try:
            header_text = " System Monitor TUI "
            view_name = self.VIEW_NAMES[self.current_view]
            header = f"{header_text}| View: {view_name} | q=Quit Tab=Switch F5=Refresh "
            header = header.ljust(w)[:w]
            stdscr.addstr(0, 0, header, curses.A_REVERSE | curses.color_pair(4))

            hints = " F5:Refresh  Tab:Switch  q:Quit "
            if self.current_view == self.VIEW_PROCESSES:
                hints = " j/k:Nav  c:CPU  m:Mem  p:PID  t:Tree  /:Search  K:Kill  r:Renice  q:Quit "
            elif self.current_view == self.VIEW_OVERVIEW:
                hints = " Tab:Switch View  F5:Refresh  q:Quit "
            elif self.current_view == self.VIEW_NETWORK:
                hints = " Tab:Switch View  F5:Refresh  q:Quit "
            elif self.current_view == self.VIEW_DISK:
                hints = " Tab:Switch View  F5:Refresh  q:Quit "

            hints = hints.ljust(w)[:w]
            stdscr.addstr(1, 0, hints, curses.color_pair(6))
        except curses.error:
            pass

    def _draw_footer(self, stdscr, h, w):
        """Draw footer bar."""
        try:
            footer = f" Interval: {self.interval}s | "
            if self.processes_view.search_mode:
                footer += f"Search: /{self.processes_view.search_query}  (Esc to clear) "
            footer = footer.ljust(w)[:w]
            stdscr.addstr(h - 1, 0, footer, curses.A_REVERSE | curses.color_pair(4))
        except curses.error:
            pass
