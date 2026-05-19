"""Process data collector from /proc filesystem."""

import os
import pwd
import time
from ..utils import safe_read, safe_readlines, safe_int


class ProcessInfo:
    """Represents information about a single process."""

    def __init__(self):
        self.pid = 0
        self.user = ""
        self.cpu_percent = 0.0
        self.mem_percent = 0.0
        self.state = ""
        self.command = ""
        self.ppid = 0  # Parent PID for tree
        self.children = []  # List of child ProcessInfo for tree

    def __repr__(self):
        return f"ProcessInfo(pid={self.pid}, cmd={self.command})"


class ProcessCollector:
    """Collects process information from /proc."""

    def __init__(self):
        self._prev_cpu_times = {}  # pid -> (total_time, timestamp)
        self._page_size = os.sysconf(os.sysconf_names['SC_PAGE_SIZE'])
        self._clock_ticks = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        self._total_memory_kb = 0
        self._total_memory_kb = self._get_total_memory()
        self._uid_cache = {}  # uid -> username

    def _get_total_memory(self):
        """Get total memory from /proc/meminfo."""
        content = safe_read("/proc/meminfo")
        if content:
            for line in content.split('\n'):
                if line.startswith('MemTotal:'):
                    parts = line.split()
                    if len(parts) > 1:
                        return safe_int(parts[1])
        return 1  # Avoid division by zero

    def _get_username(self, uid):
        """Get username from UID."""
        if uid in self._uid_cache:
            return self._uid_cache[uid]
        try:
            name = pwd.getpwuid(uid).pw_name
        except (KeyError, TypeError):
            name = str(uid)
        self._uid_cache[uid] = name
        return name

    def _parse_stat(self, pid):
        """Parse /proc/<pid>/stat and return relevant fields."""
        content = safe_read(f"/proc/{pid}/stat")
        if not content:
            return None

        # The stat file format is tricky because comm field may contain spaces and parens
        # Format: pid (comm) state ppid ...
        try:
            # Find the closing paren of comm
            end_paren = content.rfind(')')
            if end_paren == -1:
                return None
            before_comm = content[:content.find('(')]
            comm = content[content.find('(') + 1:end_paren]
            after_comm = content[end_paren + 2:].split()

            fields = before_comm.split() + [comm] + after_comm
            # fields: pid, comm, state, ppid, pgrp, session, tty_nr, tpgid,
            # flags, minflt, cminflt, majflt, cmajflt, utime, stime,
            # cutime, cstime, priority, nice, num_threads, ...

            if len(fields) < 22:
                return None

            return {
                'pid': safe_int(fields[0]),
                'comm': fields[1],
                'state': fields[2],
                'ppid': safe_int(fields[3]),
                'utime': safe_int(fields[13]),
                'stime': safe_int(fields[14]),
                'cutime': safe_int(fields[15]),
                'cstime': safe_int(fields[16]),
                'priority': safe_int(fields[17]),
                'nice': safe_int(fields[18]),
                'num_threads': safe_int(fields[19]),
                'rss': safe_int(fields[23]) if len(fields) > 23 else 0,  # pages
            }
        except (IndexError, ValueError):
            return None

    def _parse_status(self, pid):
        """Parse /proc/<pid>/status for UID."""
        content = safe_read(f"/proc/{pid}/status")
        if not content:
            return None
        uid = 0
        for line in content.split('\n'):
            if line.startswith('Uid:'):
                parts = line.split()
                if len(parts) > 1:
                    uid = safe_int(parts[1])
                break
        return uid

    def _parse_cmdline(self, pid):
        """Parse /proc/<pid>/cmdline for command."""
        content = safe_read(f"/proc/{pid}/cmdline")
        if content:
            # Replace null bytes with spaces
            cmd = content.replace('\0', ' ').strip()
            if cmd:
                return cmd
        # Fallback to stat's comm field
        stat = self._parse_stat(pid)
        if stat:
            return f"[{stat['comm']}]"
        return ""

    def _get_all_pids(self):
        """Get all process IDs from /proc."""
        pids = []
        try:
            for entry in os.listdir("/proc"):
                if entry.isdigit():
                    pids.append(int(entry))
        except (PermissionError, FileNotFoundError):
            pass
        return pids

    def update(self):
        """Update process list. Returns list of ProcessInfo objects."""
        pids = self._get_all_pids()
        now = time.time()
        processes = []
        current_cpu_times = {}

        for pid in pids:
            stat = self._parse_stat(pid)
            if stat is None:
                continue

            proc = ProcessInfo()
            proc.pid = stat['pid']
            proc.state = stat['state']
            proc.ppid = stat['ppid']
            proc.command = self._parse_cmdline(pid)

            # Truncate command for display
            if len(proc.command) > 50:
                proc.command = proc.command[:47] + "..."

            # Memory percentage
            rss_kb = stat['rss'] * self._page_size // 1024
            proc.mem_percent = (rss_kb / self._total_memory_kb) * 100.0

            # UID -> username
            uid = self._parse_status(pid)
            proc.user = self._get_username(uid)

            # CPU time for calculating percentage
            total_cpu_time = stat['utime'] + stat['stime'] + stat['cutime'] + stat['cstime']
            current_cpu_times[pid] = (total_cpu_time, now)

            # Calculate CPU percentage
            if pid in self._prev_cpu_times:
                prev_time, prev_ts = self._prev_cpu_times[pid]
                time_diff = now - prev_ts
                cpu_diff = total_cpu_time - prev_time
                if time_diff > 0:
                    proc.cpu_percent = 100.0 * (cpu_diff / self._clock_ticks) / time_diff
                else:
                    proc.cpu_percent = 0.0
            else:
                proc.cpu_percent = 0.0

            processes.append(proc)

        self._prev_cpu_times = current_cpu_times
        return processes

    def build_tree(self, processes):
        """Build a process tree from flat process list.
        Returns a list of root ProcessInfo objects with children populated."""
        by_pid = {p.pid: p for p in processes}

        # Clear children
        for p in processes:
            p.children = []

        roots = []
        for p in processes:
            parent = by_pid.get(p.ppid)
            if parent and parent != p:
                parent.children.append(p)
            else:
                roots.append(p)

        return roots

    def flatten_tree(self, roots, indent="", is_root=True):
        """Flatten a process tree into a list with indentation strings.
        Returns list of (ProcessInfo, indent_str) tuples."""
        result = []

        for i, node in enumerate(roots):
            is_last = (i == len(roots) - 1)

            if is_root and len(roots) == 1:
                # Single root: no prefix needed
                prefix = ""
            elif is_last:
                prefix = "└─ "
            else:
                prefix = "├─ "

            line_indent = indent + prefix
            result.append((node, line_indent))

            if node.children:
                if is_last:
                    new_indent = indent + "   "
                else:
                    new_indent = indent + "│  "
                result.extend(self.flatten_tree(node.children, new_indent, is_root=False))

        return result
