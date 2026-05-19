#!/usr/bin/env python3
"""
System Monitor TUI - A terminal-based system monitor using only curses and
standard library. Reads all data from /proc and /sys filesystems.

Usage:
    python system_monitor.py [--interval SECONDS]

Keybindings:
    q, F10       - Quit
    Tab          - Cycle views (Overview, Processes, Network, Disk)
    F5           - Force refresh
    j/k, arrows  - Scroll process list
    c/m/p        - Sort by CPU/MEM/PID
    /            - Search processes
    Escape       - Clear search
    K            - Kill selected process (SIGKILL)
    r            - Renice selected process
    t            - Toggle process tree view
    h            - Show help
"""

import curses
import time
import os
import sys
import argparse
import signal
import pwd
import re
from collections import defaultdict
from datetime import timedelta
from threading import Lock

# ─── Utility Functions ───────────────────────────────────────────────────────

def human_bytes(n):
    """Format bytes in human-readable form."""
    if n is None:
        return 'N/A'
    if n < 1024:
        return f"{n}B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f}K"
    elif n < 1024 ** 3:
        return f"{n / (1024 ** 2):.1f}M"
    elif n < 1024 ** 4:
        return f"{n / (1024 ** 3):.1f}G"
    else:
        return f"{n / (1024 ** 4):.1f}T"


def human_rate(n):
    """Format bytes/sec in human-readable form."""
    if n is None:
        return 'N/A'
    if n < 1024:
        return f"{n:.0f} B/s"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} K/s"
    elif n < 1024 ** 3:
        return f"{n / (1024 ** 2):.1f} M/s"
    elif n < 1024 ** 4:
        return f"{n / (1024 ** 3):.1f} G/s"
    else:
        return f"{n / (1024 ** 4):.1f} T/s"


def format_uptime(seconds):
    """Format uptime as days, hours, minutes, seconds."""
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {secs:02d}s"


def format_time_hours(hours):
    """Format hours as human-readable time."""
    if hours is None:
        return 'N/A'
    if hours < 0.01:
        return '<1m'
    h = int(hours)
    m = int((hours - h) * 60)
    if h > 0:
        return f"{h}h {m}m"
    else:
        return f"{m}m"


# ─── Data Collection ─────────────────────────────────────────────────────────

class SystemDataCollector:
    """Reads system data from /proc and /sys filesystems."""

    def __init__(self):
        self._prev_cpu = None
        self._prev_net = None
        self._prev_net_time = None
        self._prev_disk = None
        self._prev_disk_time = None
        self._cpu_history = []
        self._num_cores = 0
        self._history_lock = Lock()
        self._prev_processes = {}
        self._prev_process_time = None
        self._init_cpu()

    def _init_cpu(self):
        """Initialize CPU core count and history."""
        try:
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('cpu') and line[3].isdigit():
                        self._num_cores += 1
        except Exception:
            self._num_cores = 1
        self._cpu_history = [[] for _ in range(max(self._num_cores, 1))]

    # ─── CPU ─────────────────────────────────────────────────────────────────

    def read_cpu(self):
        """Read CPU stats from /proc/stat. Returns per-core usage percentages."""
        try:
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
        except Exception:
            return []

        cpus = {}
        for line in lines:
            if line.startswith('cpu'):
                parts = line.split()
                name = parts[0]
                vals = list(map(int, parts[1:]))
                cpus[name] = vals

        if self._prev_cpu is None:
            self._prev_cpu = cpus
            # Initialize history with zeros
            for i in range(self._num_cores):
                self._cpu_history[i].append(0.0)
            return [0.0] * self._num_cores

        result = []
        core_names = sorted([k for k in cpus if k != 'cpu'])
        for name in core_names:
            if name in self._prev_cpu and name in cpus:
                prev = self._prev_cpu[name]
                curr = cpus[name]
                prev_total = sum(prev)
                curr_total = sum(curr)
                diff_total = curr_total - prev_total
                if diff_total > 0:
                    prev_idle = prev[3] + (prev[4] if len(prev) > 4 else 0)
                    curr_idle = curr[3] + (curr[4] if len(curr) > 4 else 0)
                    diff_idle = curr_idle - prev_idle
                    usage = 100.0 * (diff_total - diff_idle) / diff_total
                else:
                    usage = 0.0
                result.append(round(usage, 1))
            else:
                result.append(0.0)

        # Also compute total CPU
        if 'cpu' in cpus and 'cpu' in self._prev_cpu:
            prev = self._prev_cpu['cpu']
            curr = cpus['cpu']
            prev_total = sum(prev)
            curr_total = sum(curr)
            diff_total = curr_total - prev_total
            if diff_total > 0:
                prev_idle = prev[3] + (prev[4] if len(prev) > 4 else 0)
                curr_idle = curr[3] + (curr[4] if len(curr) > 4 else 0)
                diff_idle = curr_idle - prev_idle
                total_usage = 100.0 * (diff_total - diff_idle) / diff_total
            else:
                total_usage = 0.0
        else:
            total_usage = sum(result) / len(result) if result else 0.0

        self._prev_cpu = cpus

        # Store in history (store total as first history entry)
        with self._history_lock:
            if not result:
                result = [total_usage]
            for i, usage in enumerate(result):
                if i < len(self._cpu_history):
                    self._cpu_history[i].append(usage)
                    if len(self._cpu_history[i]) > 60:
                        self._cpu_history[i] = self._cpu_history[i][-60:]

        return result

    def get_cpu_history(self, core_index=0):
        """Get CPU usage history for a specific core."""
        with self._history_lock:
            if core_index < len(self._cpu_history):
                return list(self._cpu_history[core_index])
            return []

    def get_total_cpu_history(self):
        """Get averaged CPU history across all cores."""
        with self._history_lock:
            if not self._cpu_history:
                return []
            max_len = max(len(h) for h in self._cpu_history)
            result = []
            for i in range(max_len):
                vals = [h[i] for h in self._cpu_history if i < len(h)]
                result.append(sum(vals) / len(vals) if vals else 0)
            return result

    def get_cpu_count(self):
        return self._num_cores

    # ─── Memory ──────────────────────────────────────────────────────────────

    def read_memory(self):
        """Read memory info from /proc/meminfo."""
        mem = {}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip()
                        val = int(val_str.split()[0])
                        mem[key] = val * 1024
        except Exception:
            return {}

        cached = mem.get('Cached', 0) + mem.get('SReclaimable', 0)
        total = mem.get('MemTotal', 0)
        available = mem.get('MemAvailable', 0)
        used = total - available
        return {
            'total': total,
            'free': mem.get('MemFree', 0),
            'available': available,
            'cached': cached,
            'buffers': mem.get('Buffers', 0),
            'used': used,
        }

    def read_swap(self):
        """Read swap info from /proc/meminfo."""
        mem = {}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        val_str = parts[1].strip()
                        val = int(val_str.split()[0])
                        mem[key] = val * 1024
        except Exception:
            return {}
        total = mem.get('SwapTotal', 0)
        free = mem.get('SwapFree', 0)
        return {'total': total, 'free': free, 'used': total - free}

    # ─── Uptime ──────────────────────────────────────────────────────────────

    def read_uptime(self):
        """Read system uptime from /proc/uptime."""
        try:
            with open('/proc/uptime', 'r') as f:
                return float(f.readline().split()[0])
        except Exception:
            return 0.0

    # ─── Load Average ────────────────────────────────────────────────────────

    def read_loadavg(self):
        """Read load averages from /proc/loadavg."""
        try:
            with open('/proc/loadavg', 'r') as f:
                parts = f.readline().split()
                return {'1min': float(parts[0]), '5min': float(parts[1]), '15min': float(parts[2])}
        except Exception:
            return {'1min': 0, '5min': 0, '15min': 0}

    # ─── Processes ───────────────────────────────────────────────────────────

    def read_processes(self):
        """Read process list from /proc."""
        processes = []
        pid_dirs = []
        try:
            for entry in os.listdir('/proc'):
                if entry.isdigit():
                    pid_dirs.append(int(entry))
        except PermissionError:
            pass

        for pid in pid_dirs:
            try:
                stat_path = f'/proc/{pid}/stat'
                cmdline_path = f'/proc/{pid}/cmdline'
                status_path = f'/proc/{pid}/status'

                with open(stat_path, 'r') as f:
                    stat = f.read()

                # Parse /proc/pid/stat
                close_paren = stat.rfind(')')
                comm_start = stat.find('(')
                if comm_start < 0 or close_paren < 0:
                    continue
                comm = stat[comm_start + 1:close_paren]
                fields = stat[close_paren + 2:].split()

                state = fields[0] if len(fields) > 0 else '?'
                ppid = int(fields[1]) if len(fields) > 1 else 0
                utime = int(fields[11]) if len(fields) > 11 else 0
                stime = int(fields[12]) if len(fields) > 12 else 0
                vsize = int(fields[20]) if len(fields) > 20 else 0
                rss = int(fields[21]) if len(fields) > 21 else 0
                nice_val = int(fields[16]) if len(fields) > 16 else 0

                # Get UID from status
                uid = 0
                try:
                    with open(status_path, 'r') as f:
                        for line in f:
                            if line.startswith('Uid:'):
                                uid = int(line.split()[1])
                                break
                except Exception:
                    pass

                try:
                    username = pwd.getpwuid(uid).pw_name
                except KeyError:
                    username = str(uid)

                # Get command line
                try:
                    with open(cmdline_path, 'rb') as f:
                        cmdline = f.read().decode('utf-8', errors='replace')
                        cmd = cmdline.replace('\x00', ' ').strip() if cmdline else comm
                except Exception:
                    cmd = comm

                if len(cmd) > 80:
                    cmd = cmd[:77] + '...'

                processes.append({
                    'pid': pid,
                    'user': username,
                    'cpu': 0.0,
                    'mem': rss * 4096,
                    'mem_percent': 0.0,
                    'state': state,
                    'command': cmd,
                    'ppid': ppid,
                    'nice': nice_val,
                    'utime': utime,
                    'stime': stime,
                    'vsize': vsize,
                })
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except Exception:
                continue

        # Compute memory percentages
        mem_total = 0
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_total = int(line.split()[1]) * 1024
                        break
        except Exception:
            pass

        for proc in processes:
            if mem_total > 0:
                proc['mem_percent'] = round(100.0 * proc['mem'] / mem_total, 1)

        return processes

    def compute_process_cpu(self, processes):
        """Compute CPU% for processes based on delta of CPU ticks."""
        now = time.time()
        cpu_count = max(self._num_cores, 1)

        for proc in processes:
            pid = proc['pid']
            utime = proc.get('utime', 0)
            stime = proc.get('stime', 0)
            total_ticks = utime + stime

            if self._prev_process_time is not None and pid in self._prev_processes:
                prev = self._prev_processes[pid]
                prev_ticks = prev['utime'] + prev['stime']
                elapsed = now - self._prev_process_time
                if elapsed > 0:
                    delta_ticks = max(0, total_ticks - prev_ticks)
                    proc['cpu'] = round(100.0 * delta_ticks / (elapsed * 100) / cpu_count, 1)
                else:
                    proc['cpu'] = 0.0
            else:
                proc['cpu'] = 0.0

            self._prev_processes[pid] = {
                'utime': utime,
                'stime': stime,
                'timestamp': now,
            }

        # Clean up dead processes
        current_pids = {p['pid'] for p in processes}
        for p in list(self._prev_processes.keys()):
            if p not in current_pids:
                del self._prev_processes[p]

        self._prev_process_time = now
        return processes

    # ─── Network ─────────────────────────────────────────────────────────────

    def read_network(self):
        """Read network I/O from /proc/net/dev. Returns per-interface rates."""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()
        except Exception:
            return {}

        current = {}
        for line in lines[2:]:
            parts = line.split(':')
            if len(parts) < 2:
                continue
            iface = parts[0].strip()
            data = parts[1].split()
            if len(data) >= 10:
                current[iface] = {
                    'rx_bytes': int(data[0]),
                    'tx_bytes': int(data[8]),
                }

        now = time.time()
        result = {}

        if self._prev_net is not None and self._prev_net_time is not None:
            elapsed = now - self._prev_net_time
            if elapsed > 0:
                for iface, data in current.items():
                    prev_data = self._prev_net.get(iface, {'rx_bytes': data['rx_bytes'], 'tx_bytes': data['tx_bytes']})
                    rx_rate = (data['rx_bytes'] - prev_data['rx_bytes']) / elapsed
                    tx_rate = (data['tx_bytes'] - prev_data['tx_bytes']) / elapsed
                    result[iface] = {
                        'rx_rate': max(0, rx_rate),
                        'tx_rate': max(0, tx_rate),
                        'rx_bytes': data['rx_bytes'],
                        'tx_bytes': data['tx_bytes'],
                    }
            else:
                for iface, data in current.items():
                    result[iface] = {
                        'rx_rate': 0, 'tx_rate': 0,
                        'rx_bytes': data['rx_bytes'], 'tx_bytes': data['tx_bytes'],
                    }
        else:
            for iface, data in current.items():
                result[iface] = {
                    'rx_rate': 0, 'tx_rate': 0,
                    'rx_bytes': data['rx_bytes'], 'tx_bytes': data['tx_bytes'],
                }

        self._prev_net = current
        self._prev_net_time = now
        return result

    # ─── Disk Usage ──────────────────────────────────────────────────────────

    def read_disk_usage(self):
        """Read disk usage for mounted filesystems."""
        mounts = []
        try:
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        device = parts[0]
                        mountpoint = parts[1]
                        fstype = parts[2] if len(parts) > 2 else ''
                        # Skip purely virtual filesystems
                        if fstype in ('proc', 'sysfs', 'devtmpfs', 'devpts',
                                      'cgroup', 'cgroup2', 'pstore', 'bpf', 'debugfs',
                                      'tracefs', 'securityfs', 'fusectl', 'configfs',
                                      'hugetlbfs', 'mqueue', 'nsfs', 'binfmt_misc',
                                      'rpc_pipefs', 'nfsd'):
                            continue
                        mounts.append((device, mountpoint, fstype))
        except Exception:
            return []

        result = []
        for device, mountpoint, fstype in mounts:
            try:
                st = os.statvfs(mountpoint)
                total = st.f_blocks * st.f_frsize
                free = st.f_bfree * st.f_frsize
                avail = st.f_bavail * st.f_frsize
                used = total - free
                percent = round(100.0 * used / total, 1) if total > 0 else 0.0
                result.append({
                    'device': device,
                    'mountpoint': mountpoint,
                    'total': total,
                    'used': used,
                    'free': avail,
                    'percent': percent,
                })
            except Exception:
                continue
        return result

    # ─── Disk I/O ────────────────────────────────────────────────────────────

    def read_disk_io(self):
        """Read disk I/O stats from /proc/diskstats."""
        try:
            with open('/proc/diskstats', 'r') as f:
                lines = f.readlines()
        except Exception:
            return {}

        current = {}
        for line in lines:
            parts = line.split()
            if len(parts) < 14:
                continue
            name = parts[2]

            # Skip ram disks, loop devices
            if name.startswith(('ram', 'loop')):
                continue
            # Skip partitions (sda1, nvme0n1p1, etc.)
            if re.match(r'^(sd|vd|hd|xvd)[a-z]+\d+$', name):
                continue
            if re.match(r'^nvme\d+n\d+p\d+$', name):
                continue
            if re.match(r'^mmcblk\d+p\d+$', name):
                continue

            current[name] = {
                'read_sectors': int(parts[5]) if len(parts) > 5 else 0,
                'write_sectors': int(parts[9]) if len(parts) > 9 else 0,
            }

        now = time.time()
        result = {}

        if self._prev_disk is not None and self._prev_disk_time is not None:
            elapsed = now - self._prev_disk_time
            if elapsed > 0:
                for name, data in current.items():
                    prev = self._prev_disk.get(name)
                    if prev:
                        read_rate = (data['read_sectors'] - prev['read_sectors']) * 512 / elapsed
                        write_rate = (data['write_sectors'] - prev['write_sectors']) * 512 / elapsed
                        result[name] = {
                            'read_rate': max(0, read_rate),
                            'write_rate': max(0, write_rate),
                        }
                    else:
                        result[name] = {'read_rate': 0, 'write_rate': 0}
        else:
            for name in current:
                result[name] = {'read_rate': 0, 'write_rate': 0}

        self._prev_disk = current
        self._prev_disk_time = now
        return result

    # ─── Battery ─────────────────────────────────────────────────────────────

    def read_battery(self):
        """Read battery status from /sys/class/power_supply."""
        batteries = []
        try:
            power_path = '/sys/class/power_supply'
            if not os.path.exists(power_path):
                return batteries
            for entry in os.listdir(power_path):
                if not (entry.startswith('BAT') or entry.lower() == 'battery'):
                    continue
                bat_path = os.path.join(power_path, entry)

                # Read capacity
                capacity = None
                cap_path = os.path.join(bat_path, 'capacity')
                if os.path.exists(cap_path):
                    with open(cap_path, 'r') as f:
                        capacity = int(f.read().strip())

                # Read status
                status = 'Unknown'
                stat_path = os.path.join(bat_path, 'status')
                if os.path.exists(stat_path):
                    with open(stat_path, 'r') as f:
                        status = f.read().strip()

                # Read energy/power for time estimation
                energy_now = None
                energy_full = None
                power_now = None

                enow_path = os.path.join(bat_path, 'energy_now')
                efull_path = os.path.join(bat_path, 'energy_full')
                pnow_path = os.path.join(bat_path, 'power_now')

                if os.path.exists(enow_path):
                    with open(enow_path, 'r') as f:
                        energy_now = int(f.read().strip())
                if os.path.exists(efull_path):
                    with open(efull_path, 'r') as f:
                        energy_full = int(f.read().strip())
                if os.path.exists(pnow_path):
                    with open(pnow_path, 'r') as f:
                        power_now = int(f.read().strip())

                # If no power_now, try current * voltage
                if power_now is None or power_now <= 0:
                    cnow_path = os.path.join(bat_path, 'current_now')
                    vnow_path = os.path.join(bat_path, 'voltage_now')
                    current_now = None
                    voltage_now = None
                    if os.path.exists(cnow_path):
                        with open(cnow_path, 'r') as f:
                            current_now = int(f.read().strip())
                    if os.path.exists(vnow_path):
                        with open(vnow_path, 'r') as f:
                            voltage_now = int(f.read().strip())
                    if current_now is not None and voltage_now is not None:
                        # Both in micro-units (µA, µV), product gives pW
                        power_now = current_now * voltage_now / 1e12  # Convert to watts? Actually units vary

                time_remaining = None
                if energy_now is not None and energy_full is not None and power_now is not None and power_now > 0:
                    if status == 'Discharging':
                        time_remaining = energy_now / power_now
                    elif status == 'Charging':
                        remaining_energy = energy_full - energy_now
                        if remaining_energy > 0:
                            time_remaining = remaining_energy / power_now

                # Fallback: estimate from capacity percentage
                if time_remaining is None and capacity is not None and energy_full is not None and power_now is not None and power_now > 0:
                    energy_est = energy_full * capacity / 100.0
                    if status == 'Discharging':
                        time_remaining = energy_est / power_now
                    elif status == 'Charging' and capacity < 100:
                        time_remaining = (energy_full - energy_est) / power_now

                batteries.append({
                    'name': entry,
                    'capacity': capacity,
                    'status': status,
                    'time_remaining': time_remaining,
                })
        except Exception:
            pass
        return batteries

    # ─── Network Connections ─────────────────────────────────────────────────

    def read_connections(self):
        """Read TCP connection counts by state."""
        states_map = {
            '01': 'ESTABLISHED', '02': 'SYN_SENT', '03': 'SYN_RECV',
            '04': 'FIN_WAIT1', '05': 'FIN_WAIT2', '06': 'TIME_WAIT',
            '07': 'CLOSE', '08': 'CLOSE_WAIT', '09': 'LAST_ACK',
            '0A': 'LISTEN', '0B': 'CLOSING',
        }
        counts = defaultdict(int)

        for path in ['/proc/net/tcp', '/proc/net/tcp6']:
            try:
                with open(path, 'r') as f:
                    lines = f.readlines()
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        state_hex = parts[3]
                        state_name = states_map.get(state_hex, 'UNKNOWN')
                        counts[state_name] += 1
            except Exception:
                pass
        return dict(counts)


# ─── Main TUI Application ────────────────────────────────────────────────────

class SystemMonitorTUI:
    """Main curses-based system monitor application."""

    def __init__(self, stdscr, interval=1.0):
        self.stdscr = stdscr
        self.interval = interval
        self.collector = SystemDataCollector()
        self.running = True
        self.current_view = 0
        self.views = ['Overview', 'Processes', 'Network', 'Disk']

        # Process view state
        self.process_scroll = 0
        self.process_sort = 'cpu'
        self.process_sort_reverse = True
        self.process_search = ''
        self.process_tree = False
        self.processes = []
        self.process_cursor = 0

        # Help state
        self.show_help = False

        # Confirmation prompt
        self.confirm_prompt = None

        # Input mode
        self.input_mode = None
        self.input_buffer = ''
        self._renice_target = None

        # Cached data
        self.cpu_data = []
        self.mem_data = {}
        self.swap_data = {}
        self.uptime = 0.0
        self.loadavg = {}
        self.network_data = {}
        self.disk_usage = []
        self.disk_io = {}
        self.battery_data = []
        self.connections = {}
        self.last_update = 0

        self._setup_colors()

    def _setup_colors(self):
        """Initialize color pairs."""
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_BLUE, -1)
        curses.init_pair(7, curses.COLOR_MAGENTA, -1)
        curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_RED)
        curses.init_pair(13, curses.COLOR_WHITE, curses.COLOR_BLACK)

    def _get_color_attr(self, percentage):
        """Get color attribute based on percentage."""
        if percentage < 50:
            return curses.color_pair(1)
        elif percentage < 80:
            return curses.color_pair(2)
        else:
            return curses.color_pair(3)

    def run(self):
        """Main event loop."""
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(int(self.interval * 1000))

        self._update_data()

        while self.running:
            now = time.time()
            if now - self.last_update >= self.interval:
                self._update_data()

            self._render()

            try:
                key = self.stdscr.getch()
            except Exception:
                key = -1

            if key != -1:
                self._handle_key(key)

        curses.curs_set(1)
        self.stdscr.nodelay(False)

    def _update_data(self):
        """Refresh all system data."""
        now = time.time()
        self.last_update = now

        self.cpu_data = self.collector.read_cpu()
        self.mem_data = self.collector.read_memory()
        self.swap_data = self.collector.read_swap()
        self.uptime = self.collector.read_uptime()
        self.loadavg = self.collector.read_loadavg()
        self.network_data = self.collector.read_network()
        self.disk_usage = self.collector.read_disk_usage()
        self.disk_io = self.collector.read_disk_io()
        self.battery_data = self.collector.read_battery()
        self.connections = self.collector.read_connections()

        # Always update processes so we have data (needed for process view)
        self.processes = self.collector.read_processes()
        self.collector.compute_process_cpu(self.processes)

    def _handle_key(self, key):
        """Handle keyboard input."""
        if self.confirm_prompt is not None:
            self._handle_confirm(key)
            return

        if self.input_mode == 'search':
            self._handle_search_input(key)
            return

        if self.input_mode == 'renice':
            self._handle_renice_input(key)
            return

        if key == ord('q') or key == curses.KEY_F10:
            self.running = False

        elif key == ord('\t'):
            self.current_view = (self.current_view + 1) % len(self.views)
            self.process_scroll = 0
            self.process_cursor = 0

        elif key == curses.KEY_F5:
            self.collector._prev_cpu = None
            self.collector._prev_net = None
            self.collector._prev_disk = None
            self.collector._prev_processes = {}
            self.collector._prev_process_time = None
            self._update_data()

        elif key == ord('h'):
            self.show_help = not self.show_help

        elif self.current_view == 1:
            self._handle_process_keys(key)

    def _handle_process_keys(self, key):
        """Handle keys specific to process view."""
        filtered = self._get_filtered_processes()
        max_display = self._get_process_area_height()

        if key == ord('j') or key == curses.KEY_DOWN:
            if self.process_cursor < len(filtered) - 1:
                self.process_cursor += 1
            if self.process_cursor >= self.process_scroll + max_display:
                self.process_scroll = self.process_cursor - max_display + 1

        elif key == ord('k') or key == curses.KEY_UP:
            if self.process_cursor > 0:
                self.process_cursor -= 1
            if self.process_cursor < self.process_scroll:
                self.process_scroll = self.process_cursor

        elif key == ord('c'):
            if self.process_sort == 'cpu':
                self.process_sort_reverse = not self.process_sort_reverse
            else:
                self.process_sort = 'cpu'
                self.process_sort_reverse = True

        elif key == ord('m'):
            if self.process_sort == 'mem':
                self.process_sort_reverse = not self.process_sort_reverse
            else:
                self.process_sort = 'mem'
                self.process_sort_reverse = True

        elif key == ord('p'):
            if self.process_sort == 'pid':
                self.process_sort_reverse = not self.process_sort_reverse
            else:
                self.process_sort = 'pid'
                self.process_sort_reverse = True

        elif key == ord('/'):
            self.input_mode = 'search'
            self.input_buffer = ''
            self.process_search = ''

        elif key == 27:  # Escape
            self.process_search = ''
            self.input_buffer = ''

        elif key == ord('t'):
            self.process_tree = not self.process_tree
            self.process_scroll = 0
            self.process_cursor = 0

        elif key == ord('K'):
            filtered = self._get_filtered_processes()
            if 0 <= self.process_cursor < len(filtered):
                proc = filtered[self.process_cursor]
                self.confirm_prompt = f"Kill PID {proc['pid']} ({proc['command'][:30]})? (y/n)"

        elif key == ord('r'):
            filtered = self._get_filtered_processes()
            if 0 <= self.process_cursor < len(filtered):
                proc = filtered[self.process_cursor]
                self.input_mode = 'renice'
                self.input_buffer = ''
                self._renice_target = proc

    def _handle_search_input(self, key):
        """Handle input in search mode."""
        if key == 27:  # Escape
            self.input_mode = None
            self.process_search = ''
            self.input_buffer = ''
        elif key in (10, 13):  # Enter
            self.process_search = self.input_buffer
            self.input_mode = None
            self.process_cursor = 0
            self.process_scroll = 0
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.input_buffer = self.input_buffer[:-1]
            self.process_search = self.input_buffer
            self.process_cursor = 0
            self.process_scroll = 0
        elif 32 <= key <= 126:
            self.input_buffer += chr(key)
            self.process_search = self.input_buffer
            self.process_cursor = 0
            self.process_scroll = 0

    def _handle_renice_input(self, key):
        """Handle input in renice mode."""
        if key == 27:  # Escape
            self.input_mode = None
            self.input_buffer = ''
            self._renice_target = None
        elif key in (10, 13):  # Enter
            try:
                new_nice = int(self.input_buffer)
                if -20 <= new_nice <= 19 and self._renice_target:
                    pid = self._renice_target['pid']
                    os.system(f'renice {new_nice} -p {pid} > /dev/null 2>&1')
            except ValueError:
                pass
            self.input_mode = None
            self.input_buffer = ''
            self._renice_target = None
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.input_buffer = self.input_buffer[:-1]
        elif key == ord('-') and len(self.input_buffer) == 0:
            self.input_buffer = '-'
        elif ord('0') <= key <= ord('9'):
            self.input_buffer += chr(key)

    def _handle_confirm(self, key):
        """Handle confirmation prompt."""
        if key in (ord('y'), ord('Y')):
            filtered = self._get_filtered_processes()
            if 0 <= self.process_cursor < len(filtered):
                proc = filtered[self.process_cursor]
                try:
                    os.kill(proc['pid'], signal.SIGKILL)
                except Exception:
                    pass
            self.confirm_prompt = None
        elif key in (ord('n'), ord('N'), 27):
            self.confirm_prompt = None

    def _get_filtered_processes(self):
        """Get processes filtered by search and sorted."""
        procs = list(self.processes)
        if self.process_search:
            search_lower = self.process_search.lower()
            procs = [p for p in procs if search_lower in p['command'].lower()]

        if self.process_sort == 'cpu':
            procs.sort(key=lambda p: p.get('cpu', 0.0), reverse=self.process_sort_reverse)
        elif self.process_sort == 'mem':
            procs.sort(key=lambda p: p['mem'], reverse=self.process_sort_reverse)
        elif self.process_sort == 'pid':
            procs.sort(key=lambda p: p['pid'], reverse=self.process_sort_reverse)

        return procs

    def _get_process_area_height(self):
        """Get height available for process list."""
        max_y, max_x = self.stdscr.getmaxyx()
        return max(1, max_y - 4)

    # ─── Rendering ───────────────────────────────────────────────────────────

    def _render(self):
        """Render the current view."""
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        if max_y < 5 or max_x < 40:
            try:
                self.stdscr.addstr(0, 0, "Terminal too small")
            except curses.error:
                pass
            self.stdscr.refresh()
            return

        if self.show_help:
            self._render_help(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.current_view == 0:
            self._render_overview(max_y, max_x)
        elif self.current_view == 1:
            self._render_processes(max_y, max_x)
        elif self.current_view == 2:
            self._render_network(max_y, max_x)
        elif self.current_view == 3:
            self._render_disk(max_y, max_x)

        # Overlay confirmation prompt
        if self.confirm_prompt:
            self._render_confirm(max_y, max_x)

        # Overlay input prompt
        if self.input_mode:
            self._render_input_prompt(max_y, max_x)

        self._render_status_bar(max_y, max_x)
        self.stdscr.refresh()

    def _render_confirm(self, max_y, max_x):
        """Render confirmation prompt overlay."""
        y = max_y // 2
        x = max(0, max_x // 2 - 40)
        width = min(80, max_x - 2)
        box_attr = curses.A_REVERSE
        for i in range(y, y + 3):
            try:
                self.stdscr.addstr(i, x, ' ' * width, box_attr)
            except curses.error:
                pass
        try:
            self.stdscr.addstr(y + 1, x + 2, self.confirm_prompt[:width - 4], box_attr)
        except curses.error:
            pass

    def _render_input_prompt(self, max_y, max_x):
        """Render input prompt for search or renice."""
        y = max_y - 2
        if self.input_mode == 'search':
            prefix = "Search: "
        elif self.input_mode == 'renice':
            target = self._renice_target
            if target:
                prefix = f"Renice PID {target['pid']} (nice {target.get('nice', 0)}): "
            else:
                prefix = "Renice: "
        else:
            prefix = "> "
        try:
            self.stdscr.addstr(y, 1, prefix + self.input_buffer + '_', curses.A_BOLD)
        except curses.error:
            pass

    def _render_status_bar(self, max_y, max_x):
        """Render bottom status bar."""
        y = max_y - 1
        status = f" View: {self.views[self.current_view]} | Tab: switch | F5: refresh | q: quit | h: help "
        if len(status) > max_x:
            status = status[:max_x - 1]
        try:
            self.stdscr.addstr(y, 0, status.ljust(max_x)[:max_x], curses.A_REVERSE | curses.color_pair(5))
        except curses.error:
            pass

    def _render_help(self, max_y, max_x):
        """Render help overlay."""
        help_lines = [
            "System Monitor TUI - Help",
            "",
            "Global Keys:",
            "  Tab       - Cycle views",
            "  q / F10   - Quit",
            "  F5        - Force refresh",
            "  h         - Toggle help",
            "  j/k/\u2191/\u2193  - Scroll",
            "",
            "Process View:",
            "  c         - Sort by CPU",
            "  m         - Sort by Memory",
            "  p         - Sort by PID",
            "  /         - Search by name",
            "  Escape    - Clear search",
            "  K         - Kill (SIGKILL)",
            "  r         - Renice process",
            "  t         - Toggle tree view",
            "",
            "Press any key to close help",
        ]

        box_height = len(help_lines) + 4
        box_width = min(65, max_x - 4)
        start_y = max(0, (max_y - box_height) // 2)
        start_x = max(0, (max_x - box_width) // 2)

        for i in range(box_height):
            if i == 0:
                line = '\u250c' + '\u2500' * (box_width - 2) + '\u2510'
            elif i == box_height - 1:
                line = '\u2514' + '\u2500' * (box_width - 2) + '\u2518'
            else:
                line = '\u2502' + ' ' * (box_width - 2) + '\u2502'
            try:
                self.stdscr.addstr(start_y + i, start_x, line[:max_x - start_x])
            except curses.error:
                pass

        for i, line in enumerate(help_lines):
            if start_y + i + 2 < max_y - 1:
                try:
                    self.stdscr.addstr(start_y + i + 2, start_x + 1, line[:box_width - 2])
                except curses.error:
                    pass

    # ─── Overview View ───────────────────────────────────────────────────────

    def _render_overview(self, max_y, max_x):
        """Render the overview view."""
        y = 0

        # Title
        title = " System Overview "
        try:
            self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title, curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        # ─── CPU Section ───
        try:
            self.stdscr.addstr(y, 1, "CPU", curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        cpu_count = self.collector.get_cpu_count()
        bar_width = max(10, max_x - 20)

        for i, usage in enumerate(self.cpu_data[:cpu_count]):
            if y >= max_y - 3:
                break
            label = f"Core {i:2d}: "
            try:
                self.stdscr.addstr(y, 2, label)
            except curses.error:
                pass
            bar_start_x = 2 + len(label)
            self._draw_bar(y, bar_start_x, bar_width, usage, max_x)
            try:
                self.stdscr.addstr(y, bar_start_x + bar_width + 1, f"{usage:5.1f}%")
            except curses.error:
                pass
            y += 1

        # CPU history graph
        if y < max_y - 6:
            y += 1
            try:
                self.stdscr.addstr(y, 1, "CPU History (60s)", curses.A_BOLD | curses.color_pair(4))
            except curses.error:
                pass
            y += 1
            history = self.collector.get_total_cpu_history()
            self._draw_braille_graph(y, 2, min(max_x - 4, 120), 4, history)
            y += 5

        # ─── Memory Section ───
        if y < max_y - 8:
            y += 1
            try:
                self.stdscr.addstr(y, 1, "Memory", curses.A_BOLD | curses.color_pair(4))
            except curses.error:
                pass
            y += 1

            mem = self.mem_data
            ram_total = mem.get('total', 0)
            ram_used = mem.get('used', 0)
            ram_percent = (ram_used / ram_total * 100) if ram_total > 0 else 0

            try:
                self.stdscr.addstr(y, 2, "RAM:   ")
            except curses.error:
                pass
            self._draw_bar(y, 10, bar_width, ram_percent, max_x)
            try:
                self.stdscr.addstr(y, bar_width + 11, f"{ram_percent:5.1f}%")
            except curses.error:
                pass
            y += 1

            detail = (f"Total: {human_bytes(ram_total)}  Used: {human_bytes(ram_used)}  "
                      f"Free: {human_bytes(mem.get('free', 0))}  "
                      f"Avail: {human_bytes(mem.get('available', 0))}  "
                      f"Cached: {human_bytes(mem.get('cached', 0))}")
            try:
                self.stdscr.addstr(y, 4, detail[:max_x - 6])
            except curses.error:
                pass
            y += 1

            # Swap
            swap = self.swap_data
            swap_total = swap.get('total', 0)
            swap_used = swap.get('used', 0)
            swap_free = swap.get('free', 0)
            swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0

            try:
                self.stdscr.addstr(y, 2, "Swap:  ")
            except curses.error:
                pass
            self._draw_bar(y, 10, bar_width, swap_percent, max_x)
            try:
                self.stdscr.addstr(y, bar_width + 11, f"{swap_percent:5.1f}%")
            except curses.error:
                pass
            y += 1
            try:
                self.stdscr.addstr(y, 4, f"Total: {human_bytes(swap_total)}  Used: {human_bytes(swap_used)}  Free: {human_bytes(swap_free)}")
            except curses.error:
                pass
            y += 1

        # ─── System Info ───
        if y < max_y - 4:
            y += 1
            try:
                self.stdscr.addstr(y, 1, "System", curses.A_BOLD | curses.color_pair(4))
            except curses.error:
                pass
            y += 1
            try:
                self.stdscr.addstr(y, 2, f"Uptime:  {format_uptime(self.uptime)}")
            except curses.error:
                pass
            y += 1
            la = self.loadavg
            try:
                self.stdscr.addstr(y, 2, f"Load:    {la.get('1min', 0):.2f} (1m)  {la.get('5min', 0):.2f} (5m)  {la.get('15min', 0):.2f} (15m)")
            except curses.error:
                pass
            y += 1

        # ─── Battery ───
        if self.battery_data and y < max_y - 4:
            y += 1
            try:
                self.stdscr.addstr(y, 1, "Battery", curses.A_BOLD | curses.color_pair(7))
            except curses.error:
                pass
            y += 1
            for bat in self.battery_data:
                if y >= max_y - 2:
                    break
                cap = bat.get('capacity')
                status = bat.get('status', 'Unknown')
                time_rem = bat.get('time_remaining')
                if cap is not None:
                    small_bar = max(10, max_x - 35)
                    try:
                        self.stdscr.addstr(y, 2, f"{bat['name']}: ")
                    except curses.error:
                        pass
                    self._draw_bar(y, 10 + len(bat['name']), small_bar, cap, max_x)
                    time_str = format_time_hours(time_rem) if time_rem else 'N/A'
                    try:
                        self.stdscr.addstr(y, small_bar + 12 + len(bat['name']), f"{cap}% {status} {time_str}")
                    except curses.error:
                        pass
                    y += 1

        # ─── Connection Summary ───
        if self.connections and y < max_y - 3:
            y += 1
            try:
                self.stdscr.addstr(y, 1, "TCP Connections", curses.A_BOLD | curses.color_pair(6))
            except curses.error:
                pass
            y += 1
            conn_parts = []
            for state, count in sorted(self.connections.items()):
                if count > 0:
                    conn_parts.append(f"{state}:{count}")
            conn_str = '  '.join(conn_parts)
            if conn_str:
                try:
                    self.stdscr.addstr(y, 2, conn_str[:max_x - 4])
                except curses.error:
                    pass
            y += 1

    # ─── Process View ────────────────────────────────────────────────────────

    def _render_processes(self, max_y, max_x):
        """Render the process view."""
        y = 0

        sort_indicator = {'cpu': '\u25bc' if self.process_sort_reverse else '\u25b2',
                          'mem': '\u25bc' if self.process_sort_reverse else '\u25b2',
                          'pid': '\u25bc' if self.process_sort_reverse else '\u25b2'}.get(self.process_sort, '')
        tree_indicator = '[Tree]' if self.process_tree else '[Flat]'
        search_indicator = f' Search: "{self.process_search}"' if self.process_search else ''

        title = f" Processes {tree_indicator} | Sort: {self.process_sort} {sort_indicator}{search_indicator} "
        try:
            self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title[:max_x], curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        header = f"{'PID':>8} {'USER':<10} {'CPU%':>6} {'MEM%':>6} {'STATE':>6} COMMAND"
        try:
            self.stdscr.addstr(y, 1, header[:max_x - 2], curses.A_REVERSE)
        except curses.error:
            pass
        y += 1

        filtered = self._get_filtered_processes()

        if self.process_tree:
            display_list = self._build_process_tree(filtered)
        else:
            display_list = [(p, 0, []) for p in filtered]

        process_area = max_y - 3
        visible_start = self.process_scroll
        visible_end = min(visible_start + process_area - y, len(display_list))

        for i, item in enumerate(display_list[visible_start:visible_end]):
            if y >= max_y - 2:
                break
            proc, depth, ancestry = item
            actual_idx = visible_start + i

            attr = curses.A_REVERSE if actual_idx == self.process_cursor else curses.A_NORMAL

            # Build tree prefix
            prefix = ''
            if self.process_tree and depth > 0:
                for d in range(depth - 1):
                    if d < len(ancestry) - 1 and not ancestry[d]:
                        prefix += ' \u2502  '
                    else:
                        prefix += '    '
                if ancestry and ancestry[-1]:
                    prefix += ' \u2514\u2500 '
                else:
                    prefix += ' \u251c\u2500 '

            cpu_str = f"{proc.get('cpu', 0):5.1f}"
            mem_str = f"{proc.get('mem_percent', 0):5.1f}"
            state_str = proc.get('state', '?')
            cmd = proc.get('command', '')[:max_x - 48 - len(prefix)]

            line = f"{proc['pid']:>8} {proc['user'][:10]:<10} {cpu_str:>6} {mem_str:>6} {state_str:>6} {prefix}{cmd}"
            line = line[:max_x - 2]

            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass
            y += 1

    def _build_process_tree(self, processes):
        """Build a tree representation of processes."""
        children = defaultdict(list)
        for p in processes:
            children[p.get('ppid', 0)].append(p)

        for ppid in children:
            children[ppid].sort(key=lambda x: x['pid'])

        all_pids = {p['pid'] for p in processes}
        result = []
        visited = set()

        def traverse(proc, depth, ancestry):
            if proc['pid'] in visited:
                return
            visited.add(proc['pid'])
            child_list = children.get(proc['pid'], [])
            for j, child in enumerate(child_list):
                is_last = (j == len(child_list) - 1)
                new_ancestry = ancestry + [is_last]
                result.append((child, depth + 1, new_ancestry))
                traverse(child, depth + 1, new_ancestry)

        # Find root processes
        for p in processes:
            ppid = p.get('ppid', 0)
            if ppid not in all_pids:
                result.append((p, 0, []))
                visited.add(p['pid'])
                traverse(p, 0, [])

        # Any remaining
        for p in processes:
            if p['pid'] not in visited:
                result.append((p, 0, []))
                traverse(p, 0, [])

        return result

    # ─── Network View ────────────────────────────────────────────────────────

    def _render_network(self, max_y, max_x):
        """Render the network view."""
        y = 0

        title = " Network Interfaces "
        try:
            self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title, curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        header = f"{'Interface':<15} {'RX Rate':>12} {'TX Rate':>12} {'RX Total':>12} {'TX Total':>12}"
        try:
            self.stdscr.addstr(y, 1, header[:max_x - 2], curses.A_REVERSE)
        except curses.error:
            pass
        y += 1

        for iface, data in sorted(self.network_data.items()):
            if y >= max_y - 10:
                break
            line = (f"{iface:<15} {human_rate(data.get('rx_rate', 0)):>12} "
                    f"{human_rate(data.get('tx_rate', 0)):>12} "
                    f"{human_bytes(data.get('rx_bytes', 0)):>12} "
                    f"{human_bytes(data.get('tx_bytes', 0)):>12}")
            try:
                self.stdscr.addstr(y, 1, line[:max_x - 2])
            except curses.error:
                pass
            y += 1

        if not self.network_data:
            try:
                self.stdscr.addstr(y, 2, "No network data available")
            except curses.error:
                pass
            y += 1

        # TCP Connections
        y += 1
        try:
            self.stdscr.addstr(y, 1, "TCP Connections by State", curses.A_BOLD | curses.color_pair(6))
        except curses.error:
            pass
        y += 1
        for state, count in sorted(self.connections.items()):
            if y >= max_y - 2:
                break
            try:
                self.stdscr.addstr(y, 4, f"{state:<20} {count:>6}")
            except curses.error:
                pass
            y += 1

    # ─── Disk View ───────────────────────────────────────────────────────────

    def _render_disk(self, max_y, max_x):
        """Render the disk view."""
        y = 0

        title = " Disk Usage "
        try:
            self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title, curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        header = f"{'Mount':<22} {'Total':>8} {'Used':>8} {'Free':>8} {'Use%':>6}"
        try:
            self.stdscr.addstr(y, 1, header[:max_x - 2], curses.A_REVERSE)
        except curses.error:
            pass
        y += 1

        for disk in self.disk_usage:
            if y >= max_y - 12:
                break
            mp = disk['mountpoint'][:20]
            line = (f"{mp:<22} {human_bytes(disk['total']):>8} "
                    f"{human_bytes(disk['used']):>8} {human_bytes(disk['free']):>8} "
                    f"{disk['percent']:>5.1f}%")
            attr = self._get_color_attr(disk['percent'])
            try:
                self.stdscr.addstr(y, 1, line[:max_x - 2], attr)
            except curses.error:
                pass
            y += 1

        # Disk I/O
        y += 1
        try:
            self.stdscr.addstr(y, 1, "Disk I/O", curses.A_BOLD | curses.color_pair(4))
        except curses.error:
            pass
        y += 1

        io_header = f"{'Device':<15} {'Read':>12} {'Write':>12}"
        try:
            self.stdscr.addstr(y, 1, io_header[:max_x - 2], curses.A_REVERSE)
        except curses.error:
            pass
        y += 1

        for dev, data in sorted(self.disk_io.items()):
            if y >= max_y - 2:
                break
            line = f"{dev:<15} {human_rate(data.get('read_rate', 0)):>12} {human_rate(data.get('write_rate', 0)):>12}"
            try:
                self.stdscr.addstr(y, 1, line[:max_x - 2])
            except curses.error:
                pass
            y += 1

        if not self.disk_io:
            try:
                self.stdscr.addstr(y, 2, "No disk I/O data available")
            except curses.error:
                pass
            y += 1

    # ─── Drawing Helpers ─────────────────────────────────────────────────────

    def _draw_bar(self, y, x, width, percentage, max_x):
        """Draw a horizontal bar with color based on usage level."""
        filled = int(width * min(max(percentage, 0), 100) / 100)
        if filled < 0:
            filled = 0
        if filled > width:
            filled = width

        if percentage >= 80:
            bar_attr = curses.color_pair(12)
        elif percentage >= 50:
            bar_attr = curses.color_pair(11)
        else:
            bar_attr = curses.color_pair(10)

        bar_x_end = min(x + width, max_x - 1)
        if x >= max_x:
            return
        filled_end = min(x + filled, max_x - 1)

        try:
            if filled_end > x:
                self.stdscr.addstr(y, x, ' ' * (filled_end - x), bar_attr)
            if bar_x_end > filled_end:
                self.stdscr.addstr(y, filled_end, ' ' * (bar_x_end - filled_end), curses.A_NORMAL)
        except curses.error:
            pass

    def _draw_braille_graph(self, y, x, width, height, data):
        """Draw a braille-based graph of historical CPU data.
        Each braille char covers 2 time points. Multiple rows provide finer resolution.
        """
        if not data:
            try:
                self.stdscr.addstr(y, x, "No data")
            except curses.error:
                pass
            return

        points = list(data)
        if len(points) < 2:
            try:
                self.stdscr.addstr(y, x, "Insufficient data")
            except curses.error:
                pass
            return

        total_levels = height * 4
        max_val = max(points) if max(points) else 1
        if max_val < 1:
            max_val = 1

        # Map each data point to level 0..(total_levels-1)
        levels = [int(min(p / max_val * total_levels, total_levels - 0.001)) for p in points]

        for row in range(height):
            row_base = row * 4
            line_chars = []
            for col in range(width):
                idx = col * 2
                if idx >= len(levels):
                    break
                l0 = levels[idx] - row_base
                l1 = levels[idx + 1] - row_base if idx + 1 < len(levels) else 0

                def col_dots(l):
                    if l <= 0: return 0
                    elif l == 1: return 1
                    elif l == 2: return 2
                    else: return 3

                v0 = col_dots(l0)
                v1 = col_dots(l1)

                # Encode as 2-column braille character
                code = 0
                if v0 & 1: code |= 1    # dot1 (bottom left)
                if v0 & 2: code |= 8    # dot4 (top left)
                if v1 & 1: code |= 2    # dot2 (bottom right)
                if v1 & 2: code |= 16   # dot5 (top right)
                line_chars.append(chr(0x2800 + code))
            try:
                self.stdscr.addstr(y + row, x, ''.join(line_chars)[:width])
            except curses.error:
                pass


# ─── Entry Point ─────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description='Terminal System Monitor TUI')
    parser.add_argument('--interval', '-i', type=float, default=1.0,
                        help='Update interval in seconds (default: 1.0)')
    return parser.parse_args()


def main(stdscr, interval=1.0):
    app = SystemMonitorTUI(stdscr, interval=interval)
    app.run()


if __name__ == '__main__':
    args = parse_args()
    try:
        curses.wrapper(main, interval=args.interval)
    except KeyboardInterrupt:
        print("Interrupted. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
