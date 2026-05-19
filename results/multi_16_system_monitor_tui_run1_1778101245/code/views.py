"""View classes for the System Monitor TUI.

Four views: Overview, Processes, Network, Disk.
Each view owns its rendering logic using collectors and UI helpers.
Each view draws into its own sub-window starting at screen row 1.
"""

import curses
import os
import signal

import collectors
import ui
import utils


class View:
    """Base class for all views with sub-window management."""

    def __init__(self, name: str):
        self.name = name
        self.scroll_offset = 0
        self.max_scroll = 0
        self.win = None

    def init_window(self):
        """Create the sub-window below the tab bar."""
        # Use try/except in case curses hasn't been initialised yet
        try:
            self.win = curses.newwin(curses.LINES - 1, curses.COLS, 1, 0)
        except curses.error:
            self.win = None

    def resize(self):
        """Handle terminal resize by recreating the sub-window."""
        self.init_window()

    def draw(self, width: int, height: int):
        """Draw the view. Override in subclasses."""
        if self.win is None:
            return
        self.win.erase()

    def handle_key(self, key: int) -> bool:
        """Handle a key press. Return True if handled."""
        return False


class OverviewView(View):
    """Overview view showing CPU, memory, uptime, load, battery."""

    def __init__(self):
        super().__init__("Overview")

    def draw(self, width: int, height: int):
        super().draw(width, height)
        if self.win is None:
            return
        win = self.win
        win_height = height - 1  # subtract tab bar row

        y = 0
        # Title
        ui.safe_addstr(win, y, 0, " SYSTEM MONITOR ", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # --- CPU Section ---
        per_core, overall = collectors.get_cpu_percent()
        ui.draw_section_header(win, y, 0, "CPU", width)
        y += 1

        # Draw aggregate CPU bar
        ui.draw_bar(win, y, 2, width - 4, overall, "Overall")
        y += 1

        # CPU history sparkline
        history = collectors.get_cpu_history()
        sparkline_width = min(width - 4, 60)
        ui.safe_addstr(win, y, 2, "History: ")
        ui.draw_sparkline(win, y, 12, sparkline_width, history)
        y += 1

        # Per-core CPU bars
        for cpu_name, usage in sorted(per_core.items()):
            if cpu_name == "cpu":
                continue
            if y >= win_height - 2:
                break
            label = cpu_name
            ui.draw_bar(win, y, 2, width - 4, usage, label)
            y += 1

        y += 1

        # --- Memory Section ---
        mem = collectors.get_memory_info()
        ui.draw_section_header(win, y, 0, "Memory", width)
        y += 1

        ram_total = mem.get("total", 0)
        ram_used = mem.get("used", 0)
        ram_percent = (ram_used / ram_total * 100) if ram_total > 0 else 0.0

        ui.draw_labeled_bar(win, y, 2, width - 4, 10,
                            "RAM",
                            ram_percent,
                            utils.format_bytes(ram_used),
                            utils.format_bytes(ram_total))
        y += 1

        # Show detailed memory info
        details = (
            f"Used: {utils.format_bytes(ram_used)}  "
            f"Free: {utils.format_bytes(mem.get('free', 0))}  "
            f"Avail: {utils.format_bytes(mem.get('available', 0))}  "
            f"Cache: {utils.format_bytes(mem.get('cached', 0))}"
        )
        ui.safe_addstr(win, y, 4, details[:width - 6])
        y += 1

        # Swap - show used, total, AND free
        swap_total = mem.get("swap_total", 0)
        swap_used = mem.get("swap_used", 0)
        swap_free = mem.get("swap_free", 0)
        swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0.0

        ui.draw_labeled_bar(win, y, 2, width - 4, 10,
                            "Swap",
                            swap_percent,
                            utils.format_bytes(swap_used),
                            utils.format_bytes(swap_total))
        y += 1

        # Show swap free on a detail line
        swap_details = (
            f"Used: {utils.format_bytes(swap_used)}  "
            f"Free: {utils.format_bytes(swap_free)}  "
            f"Total: {utils.format_bytes(swap_total)}"
        )
        ui.safe_addstr(win, y, 4, swap_details[:width - 6])
        y += 1

        # --- System Info ---
        y += 1
        ui.draw_section_header(win, y, 0, "System", width)
        y += 1

        uptime = collectors.get_uptime()
        load1, load5, load15 = collectors.get_loadavg()

        ui.safe_addstr(win, y, 4, f"Uptime: {utils.format_uptime(uptime)}")
        y += 1
        ui.safe_addstr(win, y, 4,
                       f"Load Avg: {load1:.2f} (1m)  {load5:.2f} (5m)  {load15:.2f} (15m)")
        y += 1

        # Battery
        battery = collectors.get_battery()
        if battery and battery.get("capacity") is not None:
            cap = battery["capacity"]
            status = battery.get("status", "Unknown")
            time_rem = battery.get("time_remaining")
            batt_color = ui.get_color_for_percent(100 - cap if status == "Discharging" else cap)
            batt_str = f"Battery: {cap}% [{status}]"
            if time_rem is not None:
                batt_str += f"  Est: {utils.format_time_remaining(time_rem)}"
            ui.safe_addstr(win, y, 4, batt_str, curses.color_pair(batt_color))
            y += 1
        else:
            ui.safe_addstr(win, y, 4, "Battery: N/A")
            y += 1


class ProcessesView(View):
    """Process table view with sorting, scrolling, search, kill, renice, tree."""

    def __init__(self):
        super().__init__("Processes")
        self.sort_key = "cpu"  # sort by CPU% by default
        self.search_term = ""
        self.search_mode = False
        self.search_input = ""
        self.tree_mode = False
        self.selected_idx = 0
        self.processes = []
        self.filtered_processes = []
        self.mem_total = 0
        self.prompt_mode = None  # 'kill' or 'renice'
        self.prompt_input = ""
        self.prompt_target = None  # (pid, cmd) tuple
        self.status_msg = ""
        self.status_timer = 0

    def draw(self, width: int, height: int):
        super().draw(width, height)
        if self.win is None:
            return
        win = self.win
        win_height = height - 1

        # Collect process data
        self.processes = collectors.get_processes()
        self._apply_filter_and_sort()

        y = 0

        # Title
        sort_labels = {"cpu": "CPU%", "mem": "MEM%", "pid": "PID"}
        sort_label = sort_labels.get(self.sort_key, self.sort_key)
        search_info = f' Search: "{self.search_term}"' if self.search_term else ""
        title = f" PROCESSES (sort: {sort_label}){search_info} "
        ui.safe_addstr(win, y, 0, title[:width], curses.A_BOLD | curses.A_REVERSE)
        y += 1

        if self.tree_mode:
            self._draw_tree(win, width, win_height, y)
            return

        # Column definitions
        pid_w = 7
        user_w = 10
        cpu_w = 7
        mem_w = 7
        state_w = 6
        fixed = pid_w + user_w + cpu_w + mem_w + state_w + 5  # spaces
        cmd_w = max(10, width - fixed)

        columns = [
            ("PID", pid_w), ("USER", user_w), ("CPU%", cpu_w),
            ("MEM%", mem_w), ("S", state_w), ("COMMAND", cmd_w),
        ]
        ui.draw_table_header(win, y, 0, columns)
        y += 1

        # Calculate visible range
        avail_height = win_height - y - 1
        if avail_height < 1:
            avail_height = 1

        # Clamp selected index
        total = len(self.filtered_processes)
        if total > 0:
            self.selected_idx = max(0, min(self.selected_idx, total - 1))

        visible_start = max(0, self.selected_idx - avail_height + 1)
        if visible_start > self.selected_idx:
            visible_start = self.selected_idx
        visible_end = visible_start + avail_height

        visible_procs = self.filtered_processes[visible_start:visible_end]

        for i, proc in enumerate(visible_procs):
            if y >= win_height - 2:
                break
            row_y = y + i
            actual_idx = visible_start + i
            is_selected = (actual_idx == self.selected_idx)

            cpu_pct = proc.get("cpu_percent", 0.0)
            mem_pct = proc.get("mem_percent", 0.0)

            cpu_color = ui.get_color_for_percent(cpu_pct)
            mem_color = ui.get_color_for_percent(mem_pct)

            pid_str = str(proc.get("pid", "?"))[:pid_w - 1].ljust(pid_w)
            user_str = (proc.get("user", "?") or "?")[:user_w - 1].ljust(user_w)
            cpu_str = f"{cpu_pct:5.1f} ".rjust(cpu_w)
            mem_str = f"{mem_pct:5.1f} ".rjust(mem_w)
            state_str = (proc.get("state", "?") or "?")[:state_w - 1].ljust(state_w)
            cmd_str = (proc.get("command", "?") or "?")[:cmd_w - 1].ljust(cmd_w)

            try:
                attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
                win.addstr(row_y, 0, pid_str, attr)
                win.addstr(row_y, pid_w, user_str, attr)
                win.addstr(row_y, pid_w + user_w, cpu_str, attr | curses.color_pair(cpu_color))
                win.addstr(row_y, pid_w + user_w + cpu_w, mem_str,
                           attr | curses.color_pair(mem_color))
                win.addstr(row_y, pid_w + user_w + cpu_w + mem_w, state_str, attr)
                win.addstr(row_y, pid_w + user_w + cpu_w + mem_w + state_w, cmd_str, attr)
            except curses.error:
                pass

        # Status bar
        help_y = win_height - 1
        help_text = (" j/k:nav  c/m/p:sort  /:search  t:tree  K:kill  r:renice  "
                     "Tab:switch  q:quit  Esc:clear")
        ui.safe_addstr(win, help_y, 0, help_text[:width], curses.A_REVERSE)

        # Show status message
        if self.status_msg and self.status_timer > 0:
            try:
                win.addstr(win_height - 2, 0, f" {self.status_msg} "[:width],
                           curses.A_BOLD)
            except curses.error:
                pass

    def _apply_filter_and_sort(self):
        """Apply current search filter and sort to processes."""
        if self.search_term:
            term = self.search_term.lower()
            self.filtered_processes = [
                p for p in self.processes
                if term in (p.get("command", "") or "").lower()
                   or term in str(p.get("pid", ""))
                   or term in (p.get("user", "") or "").lower()
            ]
        else:
            self.filtered_processes = list(self.processes)

        self.filtered_processes = utils.sort_processes(
            self.filtered_processes, self.sort_key, reverse=True
        )
        if self.filtered_processes:
            self.selected_idx = max(0, min(self.selected_idx,
                                           len(self.filtered_processes) - 1))

    def _draw_tree(self, win, width: int, win_height: int, start_y: int):
        """Draw process tree."""
        roots, children, pid_map = self._build_tree()
        y = start_y
        for i, root in enumerate(roots):
            if y >= win_height - 2:
                break
            is_last = (i == len(roots) - 1)
            y = self._draw_tree_node(win, y, 0, width, root, children, pid_map,
                                     "", is_last, 0, win_height - 2)

    def _build_tree(self):
        """Build process tree from filtered process list."""
        pid_map = {p["pid"]: p for p in self.filtered_processes}
        children = {}
        for p in self.filtered_processes:
            ppid = p.get("ppid", 0)
            if ppid not in children:
                children[ppid] = []
            children[ppid].append(p["pid"])

        # Find roots (processes whose ppid is not in the filtered list)
        roots = []
        for p in self.filtered_processes:
            ppid = p.get("ppid", 0)
            if ppid not in pid_map:
                roots.append(p)

        return roots, children, pid_map

    def _draw_tree_node(self, win, y: int, x: int, width: int, node: dict,
                        children: dict, pid_map: dict, prefix: str,
                        is_last: bool, depth: int, max_y: int):
        """Recursively draw a tree node."""
        if y >= max_y:
            return y

        # Draw this node
        connector = "\u2514\u2500" if is_last else "\u251c\u2500"
        line_prefix = prefix + connector

        pid = node["pid"]
        cmd = (node.get("command", "") or "")[:30]
        cpu = node.get("cpu_percent", 0.0)
        mem = node.get("mem_percent", 0.0)

        node_str = f"{line_prefix} {pid} {cmd} CPU:{cpu:.1f}% MEM:{mem:.1f}%"
        cpu_color = ui.get_color_for_percent(cpu)
        try:
            win.addstr(y, x, node_str[:width], curses.color_pair(cpu_color))
        except curses.error:
            pass
        y += 1

        # Draw children
        child_pids = children.get(pid, [])
        for i, cpid in enumerate(child_pids):
            if cpid in pid_map:
                child_is_last = (i == len(child_pids) - 1)
                new_prefix = prefix + ("    " if is_last else "\u2502   ")
                y = self._draw_tree_node(win, y, x, width, pid_map[cpid],
                                         children, pid_map, new_prefix,
                                         child_is_last, depth + 1, max_y)
                if y >= max_y:
                    break
        return y

    def handle_key(self, key: int) -> bool:
        """Handle process view key bindings."""
        # Handle prompt mode first
        if self.prompt_mode:
            return self._handle_prompt_key(key)

        # Handle search mode
        if self.search_mode:
            return self._handle_search_key(key)

        if key == curses.KEY_DOWN or key == ord("j"):
            if self.filtered_processes:
                self.selected_idx = min(
                    len(self.filtered_processes) - 1,
                    self.selected_idx + 1
                )
            return True
        elif key == curses.KEY_UP or key == ord("k"):
            self.selected_idx = max(0, self.selected_idx - 1)
            return True
        elif key == ord("c"):
            self.sort_key = "cpu"
            self._apply_filter_and_sort()
            return True
        elif key == ord("m"):
            self.sort_key = "mem"
            self._apply_filter_and_sort()
            return True
        elif key == ord("p"):
            self.sort_key = "pid"
            self._apply_filter_and_sort()
            return True
        elif key == ord("/"):
            self.search_mode = True
            self.search_input = ""
            return True
        elif key == 27:  # Escape
            self.search_term = ""
            self.search_input = ""
            self.search_mode = False
            self._apply_filter_and_sort()
            return True
        elif key == ord("t"):
            self.tree_mode = not self.tree_mode
            return True
        elif key == ord("K"):
            return self._initiate_kill()
        elif key == ord("r"):
            return self._initiate_renice()
        elif key == curses.KEY_NPAGE:  # Page Down
            self.selected_idx = min(
                len(self.filtered_processes) - 1,
                self.selected_idx + 10
            )
            return True
        elif key == curses.KEY_PPAGE:  # Page Up
            self.selected_idx = max(0, self.selected_idx - 10)
            return True

        return False

    def _initiate_kill(self) -> bool:
        """Start kill confirmation."""
        pid = self._get_selected_pid()
        if pid is None:
            self.status_msg = "No process selected"
            self.status_timer = 2
            return True
        proc = self.filtered_processes[self.selected_idx]
        cmd = proc.get("command", "unknown") or "unknown"
        self.prompt_mode = "Kill"
        self.prompt_target = (pid, cmd)
        self.prompt_input = ""
        self.status_msg = ""
        return True

    def _initiate_renice(self) -> bool:
        """Start renice prompt."""
        pid = self._get_selected_pid()
        if pid is None:
            self.status_msg = "No process selected"
            self.status_timer = 2
            return True
        proc = self.filtered_processes[self.selected_idx]
        cmd = proc.get("command", "unknown") or "unknown"
        self.prompt_mode = "Renice (-20 to 19)"
        self.prompt_target = (pid, cmd)
        self.prompt_input = ""
        self.status_msg = ""
        return True

    def _handle_prompt_key(self, key: int) -> bool:
        """Handle keys while in prompt mode."""
        if key == 27:  # Escape - cancel
            self.prompt_mode = None
            self.prompt_input = ""
            self.prompt_target = None
            return True

        if self.prompt_mode and "Kill" in str(self.prompt_mode):
            if key in (ord("y"), ord("Y")):
                pid, cmd = self.prompt_target
                try:
                    os.kill(pid, signal.SIGKILL)
                    self.status_msg = f"Killed {cmd} (PID {pid})"
                except PermissionError:
                    self.status_msg = f"Permission denied: {cmd}"
                except ProcessLookupError:
                    self.status_msg = f"Process not found: {pid}"
                except OSError as e:
                    self.status_msg = f"Error: {e}"
                self.status_timer = 3
                self.prompt_mode = None
                self.prompt_target = None
                self.prompt_input = ""
                return True
            elif key in (ord("n"), ord("N")):
                self.status_msg = "Kill cancelled"
                self.status_timer = 2
                self.prompt_mode = None
                self.prompt_target = None
                self.prompt_input = ""
                return True
            return True

        if self.prompt_mode and "Renice" in str(self.prompt_mode):
            if key in (curses.KEY_ENTER, 10, 13):
                # Confirm renice
                try:
                    nice_val = int(self.prompt_input)
                    if nice_val < -20:
                        nice_val = -20
                    elif nice_val > 19:
                        nice_val = 19
                except ValueError:
                    self.status_msg = f"Invalid nice value: {self.prompt_input}"
                    self.status_timer = 2
                    self.prompt_mode = None
                    self.prompt_input = ""
                    self.prompt_target = None
                    return True

                pid, cmd = self.prompt_target
                try:
                    os.setpriority(os.PRIO_PROCESS, pid, nice_val)
                    self.status_msg = f"Reniced {cmd} (PID {pid}) to {nice_val}"
                except PermissionError:
                    self.status_msg = f"Permission denied: {cmd}"
                except ProcessLookupError:
                    self.status_msg = f"Process not found: {pid}"
                except OSError as e:
                    self.status_msg = f"Error: {e}"
                self.status_timer = 3
                self.prompt_mode = None
                self.prompt_input = ""
                self.prompt_target = None
                return True
            elif key in (curses.KEY_BACKSPACE, 127):
                self.prompt_input = self.prompt_input[:-1]
                return True
            elif key == ord("-") and len(self.prompt_input) == 0:
                self.prompt_input = "-"
                return True
            elif ord("0") <= key <= ord("9"):
                self.prompt_input += chr(key)
                return True
            return True

        return False

    def _handle_search_key(self, key: int) -> bool:
        """Handle keys while in search mode."""
        if key == 27:  # Escape - clear search and exit search mode
            self.search_mode = False
            self.search_term = ""
            self.search_input = ""
            self._apply_filter_and_sort()
            return True
        elif key in (curses.KEY_ENTER, 10, 13):  # Enter
            self.search_term = self.search_input
            self.search_mode = False
            self._apply_filter_and_sort()
            return True
        elif key in (curses.KEY_BACKSPACE, 127):
            self.search_input = self.search_input[:-1]
            self.search_term = self.search_input
            self._apply_filter_and_sort()
            return True
        elif 32 <= key <= 126:  # Printable characters
            self.search_input += chr(key)
            self.search_term = self.search_input
            self._apply_filter_and_sort()
            return True
        return True

    def _get_selected_pid(self):
        """Get the PID of the selected process."""
        if 0 <= self.selected_idx < len(self.filtered_processes):
            return self.filtered_processes[self.selected_idx].get("pid")
        return None


class NetworkView(View):
    """Network view showing interfaces and connections."""

    def __init__(self):
        super().__init__("Network")

    def draw(self, width: int, height: int):
        super().draw(width, height)
        if self.win is None:
            return
        win = self.win
        win_height = height - 1

        y = 0
        ui.safe_addstr(win, y, 0, " NETWORK ", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # Interfaces
        interfaces = collectors.get_network_interfaces()
        ui.draw_section_header(win, y, 0, "Interfaces", width)
        y += 1

        # Header
        iface_w = 12
        rx_w = 14
        tx_w = 14
        total_w = 14
        columns = [
            ("Interface", iface_w), ("RX Rate", rx_w), ("TX Rate", tx_w),
            ("Total RX", total_w), ("Total TX", total_w),
        ]
        ui.draw_table_header(win, y, 0, columns)
        y += 1

        for iface in interfaces:
            if y >= win_height - 4:
                break
            rx_color = ui.get_color_for_percent(
                min(100, iface.get("rx_rate", 0) / (1024 * 1024) * 10)
            )
            tx_color = ui.get_color_for_percent(
                min(100, iface.get("tx_rate", 0) / (1024 * 1024) * 10)
            )

            try:
                win.addstr(y, 0, iface["name"][:iface_w - 1].ljust(iface_w))
                win.addstr(y, iface_w,
                           utils.format_bytes_per_sec(iface.get("rx_rate", 0)).ljust(rx_w),
                           curses.color_pair(rx_color))
                win.addstr(y, iface_w + rx_w,
                           utils.format_bytes_per_sec(iface.get("tx_rate", 0)).ljust(tx_w),
                           curses.color_pair(tx_color))
                win.addstr(y, iface_w + rx_w + tx_w,
                           utils.format_bytes(iface.get("rx_bytes", 0)).ljust(total_w))
                win.addstr(y, iface_w + rx_w + tx_w + total_w,
                           utils.format_bytes(iface.get("tx_bytes", 0)).ljust(total_w))
            except curses.error:
                pass
            y += 1

        y += 1

        # Active connections
        connections = collectors.get_tcp_connections()
        ui.draw_section_header(win, y, 0, "Active Connections", width)
        y += 1

        total_conn = sum(connections.values())
        ui.safe_addstr(win, y, 2, f"Total: {total_conn}")
        y += 1

        # Show non-zero connection states
        if total_conn > 0:
            states_order = ["ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT",
                            "SYN_SENT", "SYN_RECV", "FIN_WAIT1", "FIN_WAIT2",
                            "CLOSING", "LAST_ACK", "CLOSE"]
            line_parts = []
            for state in states_order:
                count = connections.get(state, 0)
                if count > 0:
                    line_parts.append(f"{state}: {count}")
            if line_parts:
                line_str = "  ".join(line_parts)
                ui.safe_addstr(win, y, 2, line_str[:width - 4])
                y += 1
            else:
                ui.safe_addstr(win, y, 2, "No active connections")
                y += 1

        # Help
        help_y = win_height - 1
        ui.safe_addstr(win, help_y, 0, " Tab:switch view  q:quit ", curses.A_REVERSE)


class DiskView(View):
    """Disk view showing usage and I/O."""

    def __init__(self):
        super().__init__("Disk")

    def draw(self, width: int, height: int):
        super().draw(width, height)
        if self.win is None:
            return
        win = self.win
        win_height = height - 1

        y = 0
        ui.safe_addstr(win, y, 0, " DISK ", curses.A_BOLD | curses.A_REVERSE)
        y += 2

        # Disk usage
        mounts = collectors.get_mounts()
        usage = collectors.get_disk_usage(mounts)
        ui.draw_section_header(win, y, 0, "Disk Usage", width)
        y += 1

        for disk in usage[:win_height // 2 - 3]:
            if y >= win_height - 4:
                break
            label = f"{disk['mountpoint']}"
            ui.draw_labeled_bar(win, y, 2, width - 4, 12,
                                label,
                                disk["percent"],
                                utils.format_bytes(disk["used"]),
                                utils.format_bytes(disk["total"]))
            y += 1
            # Show free space detail line
            free_str = f"  Free: {utils.format_bytes(disk['free'])}"
            ui.safe_addstr(win, y, 14, free_str[:width - 14])
            y += 1

        y += 1

        # Disk I/O
        disk_io = collectors.get_disk_io()
        if disk_io:
            ui.draw_section_header(win, y, 0, "Disk I/O", width)
            y += 1

            # Header
            name_w = 12
            read_w = 14
            write_w = 14
            columns = [
                ("Device", name_w), ("Read Rate", read_w), ("Write Rate", write_w),
            ]
            ui.draw_table_header(win, y, 0, columns)
            y += 1

            for disk in disk_io:
                if y >= win_height - 4:
                    break
                try:
                    win.addstr(y, 0, disk["name"][:name_w - 1].ljust(name_w))
                    win.addstr(y, name_w,
                               utils.format_bytes_per_sec(disk.get("read_rate", 0)).ljust(read_w),
                               curses.color_pair(ui.get_color_for_percent(
                                   min(100, disk.get("read_rate", 0) / (1024 * 1024) * 10))))
                    win.addstr(y, name_w + read_w,
                               utils.format_bytes_per_sec(disk.get("write_rate", 0)).ljust(write_w),
                               curses.color_pair(ui.get_color_for_percent(
                                   min(100, disk.get("write_rate", 0) / (1024 * 1024) * 10))))
                except curses.error:
                    pass
                y += 1

        # Help
        help_y = win_height - 1
        ui.safe_addstr(win, help_y, 0, " Tab:switch view  q:quit ", curses.A_REVERSE)
