"""Overview view: CPU, Memory, Swap, Uptime, Load, Battery, Connections."""

import curses
from ..utils import (
    human_readable_bytes, format_uptime, make_bar,
    braille_graph, format_percent
)


class OverviewView:
    """Renders the overview dashboard."""

    def draw(self, stdscr, top, height, width, ui):
        """Draw the overview view using cached data from ui."""
        y = top

        # CPU section (use cached data)
        y = self._draw_cpu_section(stdscr, y, width, ui)
        y += 1

        # Memory & Swap
        y = self._draw_memory_section(stdscr, y, width, ui)
        y += 1

        # System info (Uptime, Load)
        y = self._draw_system_section(stdscr, y, width, ui)

        # Battery (if available)
        bat = ui.battery_data
        if bat:
            y += 1
            y = self._draw_battery_section(stdscr, y, width, bat, ui)

        # Connection counts
        if y < top + height - 5:
            y += 1
            self._draw_connections_section(stdscr, y, width, ui)

    def _draw_cpu_section(self, stdscr, y, width, ui):
        """Draw CPU usage section."""
        try:
            stdscr.addstr(y, 1, "CPU Usage", curses.A_BOLD | curses.color_pair(4))
            y += 1

            cpu = ui.cpu_data
            if not cpu:
                return y

            global_pct = cpu['global']
            per_core = cpu['per_core']
            history = cpu['history']
            bar_width = min(width - 20, 60)

            # Global CPU bar
            color = ui.get_color(global_pct)
            bar = make_bar(global_pct / 100.0, bar_width)
            stdscr.addstr(y, 1, "  Overall: [")
            stdscr.addstr(y, 12, bar, color)
            stdscr.addstr(y, 12 + bar_width, f"] {format_percent(global_pct)}")
            y += 1

            # Per-core CPU bars
            for core_name in sorted(per_core.keys()):
                if y > top + 20:
                    break
                pct = per_core[core_name]
                color = ui.get_color(pct)
                bar = make_bar(pct / 100.0, bar_width)
                label = f"  {core_name:6s}: ["
                stdscr.addstr(y, 1, label)
                stdscr.addstr(y, 1 + len(label) - 1, bar, color)
                stdscr.addstr(y, 1 + len(label) - 1 + bar_width, f"] {format_percent(pct)}")
                y += 1

            # Historical CPU graph
            if history and y < top + 30:
                y += 1
                stdscr.addstr(y, 1, "CPU History (60s):", curses.A_BOLD | curses.color_pair(4))
                y += 1
                graph_width = min(width - 4, 60)
                graph = braille_graph(history, graph_width)
                stdscr.addstr(y, 1, "  " + graph)

            return y
        except curses.error:
            return y

    def _draw_memory_section(self, stdscr, y, width, ui):
        """Draw memory and swap section."""
        try:
            mem = ui.mem_data
            swap = ui.swap_data

            stdscr.addstr(y, 1, "Memory", curses.A_BOLD | curses.color_pair(4))
            y += 1

            # RAM bar
            if mem and mem['total'] > 0:
                pct = (mem['used'] / mem['total']) * 100.0
                bar_width = min(width - 20, 50)
                color = ui.get_color(pct)
                bar = make_bar(pct / 100.0, bar_width)

                stdscr.addstr(y, 1, "  RAM:      [")
                stdscr.addstr(y, 12, bar, color)
                stdscr.addstr(y, 12 + bar_width, f"] {format_percent(pct)}")
                y += 1

                total_s = human_readable_bytes(mem['total'] * 1024)
                used_s = human_readable_bytes(mem['used'] * 1024)
                free_s = human_readable_bytes(mem['free'] * 1024)
                avail_s = human_readable_bytes(mem['available'] * 1024)
                cached_s = human_readable_bytes(mem['cached'] * 1024)

                info = f"     Total:{total_s}  Used:{used_s}  Free:{free_s}  Avail:{avail_s}  Cached:{cached_s}"
                stdscr.addstr(y, 1, info[:width - 2])
                y += 1

            # Swap bar
            if swap and swap['total'] > 0:
                y += 1
                pct = (swap['used'] / swap['total']) * 100.0
                bar_width = min(width - 20, 50)
                color = ui.get_color(pct)
                bar = make_bar(pct / 100.0, bar_width)

                stdscr.addstr(y, 1, "  Swap:     [")
                stdscr.addstr(y, 12, bar, color)
                stdscr.addstr(y, 12 + bar_width, f"] {format_percent(pct)}")
                y += 1

                total_s = human_readable_bytes(swap['total'] * 1024)
                used_s = human_readable_bytes(swap['used'] * 1024)
                free_s = human_readable_bytes(swap['free'] * 1024)

                info = f"     Total:{total_s}  Used:{used_s}  Free:{free_s}"
                stdscr.addstr(y, 1, info[:width - 2])
                y += 1

            return y
        except curses.error:
            return y

    def _draw_system_section(self, stdscr, y, width, ui):
        """Draw system uptime and load averages."""
        try:
            sys_data = ui.sys_data
            if not sys_data:
                return y

            uptime_str = format_uptime(sys_data['uptime'])
            load1, load5, load15 = sys_data['loadavg']

            stdscr.addstr(y, 1, "System", curses.A_BOLD | curses.color_pair(4))
            y += 1

            stdscr.addstr(y, 1, f"  Uptime:   {uptime_str}"[:width - 2])
            y += 1

            stdscr.addstr(y, 1, "  Load:     ")
            cpu_count = max(1, ui.cpu_data['cpu_count'] if ui.cpu_data else 1)

            def load_color(load_val):
                if load_val < cpu_count * 0.7:
                    return curses.color_pair(1)
                elif load_val < cpu_count * 1.5:
                    return curses.color_pair(2)
                else:
                    return curses.color_pair(3)

            stdscr.addstr(y, 12, f"{load1:.2f}", load_color(load1))
            stdscr.addstr(y, 12 + 6, f"{load5:.2f}", load_color(load5))
            stdscr.addstr(y, 12 + 12, f"{load15:.2f}", load_color(load15))
            stdscr.addstr(y, 12 + 18, "(1m / 5m / 15m)")
            y += 1

        except curses.error:
            pass
        return y

    def _draw_battery_section(self, stdscr, y, width, battery, ui):
        """Draw battery status."""
        try:
            pct = battery['percentage']
            status = battery['status']
            time_rem = battery['time_remaining']

            stdscr.addstr(y, 1, "Battery", curses.A_BOLD | curses.color_pair(4))
            y += 1

            bar_width = min(width - 20, 40)
            if status == "Discharging":
                color = ui.get_color(100 - pct)
            else:
                color = curses.color_pair(1)
            bar = make_bar(pct / 100.0, bar_width)

            stdscr.addstr(y, 1, "  Charge:   [")
            stdscr.addstr(y, 12, bar, color)
            stdscr.addstr(y, 12 + bar_width, f"] {pct}%")
            y += 1

            line = f"  Status:   {status}"
            if time_rem is not None:
                hrs = int(time_rem)
                mins = int((time_rem - hrs) * 60)
                line += f"  Time remaining: {hrs}h {mins}m"
            stdscr.addstr(y, 1, line[:width - 2])
            y += 1
        except curses.error:
            pass
        return y

    def _draw_connections_section(self, stdscr, y, width, ui):
        """Draw active network connections."""
        try:
            conn_counts = ui.conn_counts
            if not conn_counts:
                return y

            stdscr.addstr(y, 1, "TCP Connections", curses.A_BOLD | curses.color_pair(4))
            y += 1

            line = "  "
            for state in ['ESTABLISHED', 'LISTEN', 'TIME_WAIT', 'CLOSE_WAIT',
                          'SYN_SENT', 'SYN_RECV']:
                count = conn_counts.get(state, 0)
                if count > 0:
                    line += f"{state}:{count}  "
            if line.strip():
                stdscr.addstr(y, 1, line[:width - 2])
            else:
                stdscr.addstr(y, 1, "  No active connections")
            y += 1
        except curses.error:
            pass
        return y
