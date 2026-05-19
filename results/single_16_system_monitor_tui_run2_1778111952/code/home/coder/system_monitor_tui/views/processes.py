"""Process view: process table with tree mode, sorting, searching."""

import curses
from ..utils import format_percent


class ProcessesView:
    """Renders the process table/tree view."""

    def __init__(self):
        self.scroll_offset = 0
        self.selected_index = 0
        self.sort_key = 'cpu'  # 'cpu', 'mem', 'pid'
        self.sort_reverse = True
        self.search_query = ""
        self.search_mode = False
        self.show_tree = False
        self.visible_rows = 0
        self.filtered_processes = []

    def _get_sorted_and_filtered(self, processes, ui):
        """Sort and filter process list based on current settings."""
        # Filter by search query
        if self.search_query:
            filtered = [p for p in processes
                        if self.search_query.lower() in p.command.lower()]
        else:
            filtered = list(processes)

        # Sort
        if self.sort_key == 'cpu':
            filtered.sort(key=lambda p: p.cpu_percent, reverse=self.sort_reverse)
        elif self.sort_key == 'mem':
            filtered.sort(key=lambda p: p.mem_percent, reverse=self.sort_reverse)
        elif self.sort_key == 'pid':
            filtered.sort(key=lambda p: p.pid, reverse=self.sort_reverse)

        # Build tree if needed
        if self.show_tree:
            tree_roots = ui.process_collector.build_tree(filtered)
            flat_tree = ui.process_collector.flatten_tree(tree_roots)
            self.filtered_processes = flat_tree  # List of (ProcessInfo, indent)
        else:
            self.filtered_processes = filtered  # List of ProcessInfo

        return self.filtered_processes

    def draw(self, stdscr, top, height, width, ui):
        """Draw the process view."""
        try:
            self.visible_rows = max(1, height - 2)  # Reserve 2 for header

            # Get processes
            processes = ui.processes
            self._get_sorted_and_filtered(processes, ui)

            # Draw column headers
            header = f" {'PID':>8} {'USER':<9} {'CPU%':>6} {'MEM%':>6} {'S':<2} COMMAND"
            # Truncate or pad header
            header = header[:width]
            stdscr.addstr(top, 0, header, curses.A_REVERSE | curses.color_pair(4))

            # Highlight sort column
            sort_positions = {'pid': 1, 'cpu': 27, 'mem': 35}
            if self.sort_key in sort_positions:
                # Mark the sort column in header
                pass  # Header is already drawn

            # Draw process list
            max_idx = len(self.filtered_processes)
            if self.selected_index >= max_idx:
                self.selected_index = max(0, max_idx - 1)
            if self.scroll_offset > self.selected_index:
                self.scroll_offset = self.selected_index
            if self.scroll_offset + self.visible_rows <= self.selected_index:
                self.scroll_offset = max(0, self.selected_index - self.visible_rows + 1)

            for i in range(self.visible_rows):
                idx = self.scroll_offset + i
                if idx >= max_idx:
                    break

                draw_y = top + 1 + i

                if self.show_tree:
                    proc, indent = self.filtered_processes[idx]
                else:
                    proc = self.filtered_processes[idx]
                    indent = ""

                # Highlight selected row
                is_selected = (idx == self.selected_index)
                attr = curses.A_REVERSE if is_selected else curses.A_NORMAL

                # Color for CPU
                cpu_color = ui.get_color(proc.cpu_percent)
                mem_color = ui.get_color(proc.mem_percent)

                # Build the line
                line = self._format_process_line(proc, indent, width)

                stdscr.addstr(draw_y, 0, line[:width], attr)

                # Add colors for CPU% and MEM% columns (if not selected)
                if not is_selected and width > 40:
                    # Overlay CPU% color
                    cpu_str = f"{proc.cpu_percent:5.1f}"
                    cpu_pos = 19  # After PID(8)+space+USER(9)+space
                    try:
                        stdscr.addstr(draw_y, cpu_pos, cpu_str, cpu_color | attr)
                    except curses.error:
                        pass

                    mem_str = f"{proc.mem_percent:5.1f}"
                    mem_pos = 26
                    try:
                        stdscr.addstr(draw_y, mem_pos, mem_str, mem_color | attr)
                    except curses.error:
                        pass

        except curses.error:
            pass

    def _format_process_line(self, proc, indent, width):
        """Format a single process line."""
        cmd = proc.command
        if indent:
            cmd = indent + cmd

        # Truncate command to fit
        available = width - 35  # PID + USER + CPU% + MEM% + STATE + spacing
        if available > 10:
            cmd = cmd[:available]

        return f" {proc.pid:>7} {proc.user[:8]:<9} {proc.cpu_percent:5.1f} {proc.mem_percent:5.1f} {proc.state:<2} {cmd}"
