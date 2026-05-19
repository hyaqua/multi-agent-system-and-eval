#!/usr/bin/env python3
"""
System Monitor TUI
A terminal-based system monitor using curses and /proc filesystem.
All system data read directly from /proc and /sys without external libraries.

Usage: python3 system_monitor_tui.py [--interval SECONDS]
"""

import argparse
import curses
import ctypes
import math
import os
import pwd
import signal
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────
# Braille character encoding for CPU history graph
# Each braille char encodes two adjacent values (left/right columns)
# with 4 vertical levels (0%, 25%, 50%, 75%, 100%)
# ──────────────────────────────────────────────────────────────

# Dot patterns for left column (dots 7,3,2,1 from bottom to top)
_LEFT_DOTS = [0x00, 0x40, 0x44, 0x46, 0x47]

# Dot patterns for right column (dots 8,6,5,4 from bottom to top)
_RIGHT_DOTS = [0x00, 0x80, 0xA0, 0xB0, 0xB8]


def braille_char(left_val: float, right_val: float) -> str:
    """Return a braille character encoding two CPU usage values (0.0–1.0)."""
    left_lvl = max(0, min(4, int(round(left_val * 4))))
    right_lvl = max(0, min(4, int(round(right_val * 4))))
    return chr(0x2800 + _LEFT_DOTS[left_lvl] + _RIGHT_DOTS[right_lvl])


# ──────────────────────────────────────────────────────────────
# Human-readable formatters
# ──────────────────────────────────────────────────────────────

def human_bytes(n: float) -> str:
    """Format bytes into human-readable string."""
    if n < 0:
        n = 0
    if n < 1024:
        return f"{int(n)} B"
    for unit in ("KiB", "MiB", "GiB", "TiB", "PiB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PiB"


def human_rate(bytes_per_sec: float) -> str:
    """Format bytes/sec into human-readable string."""
    return human_bytes(bytes_per_sec) + "/s"


# ──────────────────────────────────────────────────────────────
# Data collectors — read directly from /proc and /sys
# ──────────────────────────────────────────────────────────────

class CPUCollector:
    """Read /proc/stat for per-core and aggregate CPU usage."""

    def __init__(self):
        self.core_count = os.cpu_count() or 1
        self._prev_total: List[int] = []
        self._prev_idle: List[int] = []
        self._history: List[float] = []

    def _parse(self) -> List[Tuple[int, int]]:
        """Return list of (total_ticks, idle_ticks) per CPU line (first=aggregate)."""
        result: List[Tuple[int, int]] = []
        try:
            with open("/proc/stat", "r") as f:
                for line in f:
                    if not line.startswith("cpu"):
                        break
                    parts = line.split()
                    # cpu / cpuN: user nice system idle iowait irq softirq steal
                    vals = [int(x) for x in parts[1:8]]
                    total = sum(vals)
                    idle = vals[3] + vals[4]  # idle + iowait
                    result.append((total, idle))
        except (IOError, PermissionError):
            pass
        return result

    def update(self) -> Dict[str, Any]:
        """Return dict with per_core, aggregate, history."""
        cur = self._parse()
        if not cur:
            return {"per_core": [], "aggregate": 0.0, "history": list(self._history)}

        # First call: store baseline
        if not self._prev_total:
            self._prev_total = [t for t, _ in cur]
            self._prev_idle = [i for _, i in cur]
            return {"per_core": [0.0] * max(0, len(cur) - 1),
                    "aggregate": 0.0,
                    "history": list(self._history)}

        per_core: List[float] = []
        agg = 0.0

        for idx, (total, idle) in enumerate(cur):
            prev_t = self._prev_total[idx] if idx < len(self._prev_total) else total
            prev_i = self._prev_idle[idx] if idx < len(self._prev_idle) else idle
            dt = total - prev_t
            di = idle - prev_i
            usage = (dt - di) / dt if dt > 0 else 0.0
            usage = max(0.0, min(1.0, usage))

            if idx == 0:
                agg = usage
            else:
                per_core.append(usage)

        # Store for next time
        self._prev_total = [t for t, _ in cur]
        self._prev_idle = [i for _, i in cur]

        # History (keep 60 seconds)
        self._history.append(agg)
        if len(self._history) > 60:
            self._history = self._history[-60:]

        return {"per_core": per_core, "aggregate": agg, "history": list(self._history)}


class MemoryCollector:
    """Read /proc/meminfo."""

    def update(self) -> Dict[str, int]:
        """Return dict of meminfo keys -> values in KB."""
        mem: Dict[str, int] = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        v = v.strip()
                        if v.endswith(" kB"):
                            mem[k.strip()] = int(v[:-3])
        except (IOError, PermissionError):
            pass
        return mem


class UptimeCollector:
    """Read /proc/uptime."""

    def update(self) -> float:
        """Return uptime in seconds."""
        try:
            with open("/proc/uptime", "r") as f:
                return float(f.read().split()[0])
        except (IOError, PermissionError, ValueError, IndexError):
            return 0.0


class LoadCollector:
    """Read /proc/loadavg."""

    def update(self) -> Tuple[float, float, float, int, int]:
        """Return (load1, load5, load15, running, total_tasks)."""
        try:
            with open("/proc/loadavg", "r") as f:
                parts = f.read().split()
                return (
                    float(parts[0]),
                    float(parts[1]),
                    float(parts[2]),
                    int(parts[3].split("/")[0]),
                    int(parts[3].split("/")[1]),
                )
        except (IOError, PermissionError, ValueError, IndexError):
            return (0.0, 0.0, 0.0, 0, 0)


class NetworkCollector:
    """Read /proc/net/dev for per-interface byte counters and rates."""

    def __init__(self):
        self._prev: Dict[str, Tuple[int, int]] = {}
        self._prev_time: float = 0.0

    def update(self) -> Dict[str, Dict[str, Any]]:
        """Return dict: iface -> {rx_bytes, tx_bytes, rx_rate, tx_rate}."""
        now = time.monotonic()
        result: Dict[str, Dict[str, Any]] = {}
        try:
            with open("/proc/net/dev", "r") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    iface, rest = line.split(":", 1)
                    iface = iface.strip()
                    parts = rest.split()
                    if len(parts) < 10:
                        continue
                    rx_bytes = int(parts[0])
                    tx_bytes = int(parts[8])
                    rx_rate = 0.0
                    tx_rate = 0.0
                    if iface in self._prev and self._prev_time > 0:
                        dt = now - self._prev_time
                        if dt > 0:
                            rx_rate = (rx_bytes - self._prev[iface][0]) / dt
                            tx_rate = (tx_bytes - self._prev[iface][1]) / dt
                    self._prev[iface] = (rx_bytes, tx_bytes)
                    result[iface] = {
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "rx_rate": max(0.0, rx_rate),
                        "tx_rate": max(0.0, tx_rate),
                    }
        except (IOError, PermissionError):
            pass
        self._prev_time = now
        return result


class ConnectionCollector:
    """Read /proc/net/tcp and /proc/net/tcp6 for connection state counts."""

    _STATE_HEX = {
        "01": "ESTABLISHED",
        "02": "SYN_SENT",
        "03": "SYN_RECV",
        "04": "FIN_WAIT1",
        "05": "FIN_WAIT2",
        "06": "TIME_WAIT",
        "07": "CLOSE",
        "08": "CLOSE_WAIT",
        "09": "LAST_ACK",
        "0A": "LISTEN",
        "0B": "CLOSING",
    }

    def update(self) -> Dict[str, int]:
        """Return dict: state_name -> count."""
        counts: Dict[str, int] = defaultdict(int)
        for proto_file in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(proto_file, "r") as f:
                    next(f)  # skip header
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 4:
                            state_hex = parts[3]
                            name = self._STATE_HEX.get(state_hex, "UNKNOWN")
                            counts[name] += 1
            except (IOError, PermissionError, StopIteration):
                pass
        return dict(counts)


class DiskCollector:
    """Read /proc/diskstats for I/O, /proc/mounts and statvfs for usage."""

    def __init__(self):
        self._prev: Dict[str, Tuple[int, int]] = {}
        self._prev_time: float = 0.0

    def update_io(self) -> Dict[str, Dict[str, Any]]:
        """Return dict: device_name -> {read_rate, write_rate} in bytes/s."""
        now = time.monotonic()
        result: Dict[str, Dict[str, Any]] = {}
        try:
            with open("/proc/diskstats", "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 14:
                        continue
                    name = parts[2]
                    read_sectors = int(parts[5])
                    write_sectors = int(parts[9])
                    read_bytes = read_sectors * 512
                    write_bytes = write_sectors * 512
                    read_rate = 0.0
                    write_rate = 0.0
                    if name in self._prev and self._prev_time > 0:
                        dt = now - self._prev_time
                        if dt > 0:
                            read_rate = (read_bytes - self._prev[name][0]) / dt
                            write_rate = (write_bytes - self._prev[name][1]) / dt
                    self._prev[name] = (read_bytes, write_bytes)
                    result[name] = {
                        "read_rate": max(0.0, read_rate),
                        "write_rate": max(0.0, write_rate),
                    }
        except (IOError, PermissionError):
            pass
        self._prev_time = now
        return result

    @staticmethod
    def update_usage() -> List[Dict[str, Any]]:
        """Return list of dicts for mounted filesystems."""
        mounts: List[Dict[str, Any]] = []
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    dev, mnt = parts[0], parts[1]
                    # Include common filesystem types
                    if not (dev.startswith("/dev/") or dev.startswith("tmpfs") or
                            dev.startswith("overlay") or ":/" in dev):
                        continue
                    try:
                        st = os.statvfs(mnt)
                        total = st.f_blocks * st.f_frsize
                        free = st.f_bfree * st.f_frsize
                        used = total - free
                        pct = (used / total * 100.0) if total > 0 else 0.0
                        mounts.append({
                            "device": dev,
                            "mount": mnt,
                            "total": total,
                            "used": used,
                            "free": free,
                            "pct": pct,
                        })
                    except (OSError, PermissionError):
                        pass
        except (IOError, PermissionError):
            pass
        return mounts


class BatteryCollector:
    """Read /sys/class/power_supply for battery information."""

    def update(self) -> Optional[Dict[str, Any]]:
        """Return battery stats dict or None."""
        base = "/sys/class/power_supply"
        try:
            entries = os.listdir(base)
        except (IOError, PermissionError, FileNotFoundError):
            return None

        bat_dirs = [e for e in entries if e.startswith("BAT") or e.lower() == "battery"]
        if not bat_dirs:
            # Also check for AC adapter or other supplies
            bat_dirs = [e for e in entries if "BAT" in e.upper()]

        for bat in bat_dirs:
            uevent_path = os.path.join(base, bat, "uevent")
            try:
                info: Dict[str, str] = {}
                with open(uevent_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            k, v = line.split("=", 1)
                            info[k] = v
            except (IOError, PermissionError):
                continue

            capacity_str = info.get("POWER_SUPPLY_CAPACITY", "0")
            status_str = info.get("POWER_SUPPLY_STATUS", "Unknown")

            try:
                capacity = int(capacity_str)
            except ValueError:
                capacity = 0

            result: Dict[str, Any] = {
                "capacity": capacity,
                "status": status_str,
            }

            # Time remaining estimation
            energy_now = info.get("POWER_SUPPLY_ENERGY_NOW")
            power_now = info.get("POWER_SUPPLY_POWER_NOW")
            charge_now = info.get("POWER_SUPPLY_CHARGE_NOW")
            current_now = info.get("POWER_SUPPLY_CURRENT_NOW")
            voltage_now = info.get("POWER_SUPPLY_VOLTAGE_NOW")

            # Try energy/power first, then charge/current*voltage
            time_remaining = None
            try:
                if energy_now and power_now:
                    en = float(energy_now)
                    pw = float(power_now)
                    if pw > 0:
                        if status_str == "Discharging":
                            time_remaining = en / pw  # hours
                        elif status_str == "Charging":
                            energy_full = float(info.get("POWER_SUPPLY_ENERGY_FULL", energy_now))
                            time_remaining = max(0, (energy_full - en) / pw)
                elif charge_now and current_now:
                    ch = float(charge_now)
                    cur = float(current_now)
                    if cur > 0:
                        if status_str == "Discharging":
                            time_remaining = ch / cur  # hours
                        elif status_str == "Charging":
                            charge_full = float(info.get("POWER_SUPPLY_CHARGE_FULL", charge_now))
                            time_remaining = max(0, (charge_full - ch) / cur)
            except (ValueError, KeyError):
                time_remaining = None

            result["time_remaining"] = time_remaining
            return result

        return None


class ProcessCollector:
    """Read /proc/[pid]/* for process information."""

    # Get system constants with fallbacks
    try:
        _CLK_TCK = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    except (KeyError, ValueError, AttributeError):
        _CLK_TCK = 100

    try:
        _PAGE_SIZE = os.sysconf(os.sysconf_names["SC_PAGESIZE"])
    except (KeyError, ValueError, AttributeError):
        _PAGE_SIZE = 4096

    def __init__(self):
        self._prev_cpu: Dict[int, Tuple[float, int]] = {}

    def _parse_stat(self, pid: int) -> Optional[Dict[str, Any]]:
        """Parse /proc/[pid]/stat."""
        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                raw = f.read()
        except (IOError, PermissionError):
            return None

        # The comm field is in parentheses and may contain spaces
        lparen = raw.find("(")
        rparen = raw.rfind(")")
        if lparen < 0 or rparen < 0:
            return None

        comm = raw[lparen + 1:rparen]
        rest = raw[rparen + 2:].split()

        if len(rest) < 20:
            return None

        try:
            return {
                "pid": pid,
                "comm": comm,
                "state": rest[0],
                "ppid": int(rest[1]),
                "pgrp": int(rest[2]),
                "session": int(rest[3]),
                "tty_nr": int(rest[4]),
                "tpgid": int(rest[5]),
                "flags": int(rest[6]),
                "minflt": int(rest[7]),
                "cminflt": int(rest[8]),
                "majflt": int(rest[9]),
                "cmajflt": int(rest[10]),
                "utime": int(rest[11]),
                "stime": int(rest[12]),
                "cutime": int(rest[13]),
                "cstime": int(rest[14]),
                "nice": int(rest[16]),
                "num_threads": int(rest[17]),
                "starttime": int(rest[19]),
                "vsize": int(rest[20]) if len(rest) > 20 else 0,
            }
        except (ValueError, IndexError):
            return None

    def _read_status(self, pid: int) -> Dict[str, Any]:
        """Read /proc/[pid]/status for UID, VmRSS."""
        result: Dict[str, Any] = {"uid": 0, "vmrss": 0}
        try:
            with open(f"/proc/{pid}/status", "r") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        parts = line.split()
                        if len(parts) > 1:
                            result["uid"] = int(parts[1])
                    elif line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) > 1:
                            result["vmrss"] = int(parts[1])
        except (IOError, PermissionError):
            pass
        return result

    @staticmethod
    def _username(uid: int) -> str:
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            return str(uid)

    @staticmethod
    def _cmdline(pid: int, fallback: str) -> str:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                data = f.read()
            if data:
                return data.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except (IOError, PermissionError):
            pass
        return fallback

    def update(self, total_mem_kb: int) -> List[Dict[str, Any]]:
        """Collect all processes. Returns list of process dicts."""
        now = time.monotonic()
        processes: List[Dict[str, Any]] = []
        pids: List[int] = []

        try:
            for entry in os.listdir("/proc"):
                if entry.isdigit():
                    pids.append(int(entry))
        except (IOError, PermissionError):
            pass

        for pid in pids:
            stat = self._parse_stat(pid)
            if stat is None:
                continue

            status = self._read_status(pid)
            uid = status["uid"]
            username = self._username(uid)
            vmrss_kb = status["vmrss"]

            total_cpu_ticks = (stat["utime"] + stat["stime"] +
                               stat["cutime"] + stat["cstime"])

            cpu_pct = 0.0
            if pid in self._prev_cpu:
                prev_time, prev_ticks = self._prev_cpu[pid]
                dt = now - prev_time
                if dt > 0:
                    cpu_pct = ((total_cpu_ticks - prev_ticks) /
                               self._CLK_TCK / dt) * 100.0

            self._prev_cpu[pid] = (now, total_cpu_ticks)
            mem_pct = (vmrss_kb / total_mem_kb) * 100.0 if total_mem_kb > 0 else 0.0
            cmdline = self._cmdline(pid, stat["comm"])

            processes.append({
                "pid": pid,
                "ppid": stat["ppid"],
                "user": username,
                "cpu_pct": max(0.0, cpu_pct),
                "mem_pct": max(0.0, mem_pct),
                "state": stat["state"],
                "nice": stat["nice"],
                "command": cmdline,
                "comm": stat["comm"],
                "vmrss_kb": vmrss_kb,
                "threads": stat["num_threads"],
            })

        # Clean stale entries
        cur_set = set(pids)
        stale = [p for p in self._prev_cpu if p not in cur_set]
        for p in stale:
            del self._prev_cpu[p]

        return processes

    @staticmethod
    def build_tree(processes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build a process tree and return a flattened list with tree_prefix."""
        if not processes:
            return []

        pid_map: Dict[int, Dict[str, Any]] = {p["pid"]: p for p in processes}
        children: Dict[int, List[int]] = defaultdict(list)

        for p in processes:
            children[p["ppid"]].append(p["pid"])

        # Sort children by PID
        for ppid in children:
            children[ppid].sort()

        # Roots: processes whose parent is not in our list
        roots = [p for p in processes if p["ppid"] not in pid_map]
        if not roots and processes:
            roots = [processes[0]]

        flat: List[Dict[str, Any]] = []

        def traverse(pid: int, depth: int, ancestors_last: List[bool]):
            proc = pid_map.get(pid)
            if proc is None:
                return
            prefix = ""
            for i in range(depth):
                if i < len(ancestors_last) and ancestors_last[i]:
                    prefix += "    "
                else:
                    prefix += "│   "
            if depth > 0:
                prefix += "└── " if ancestors_last[-1] else "├── "
            proc_copy = dict(proc)
            proc_copy["tree_prefix"] = prefix
            proc_copy["tree_depth"] = depth
            flat.append(proc_copy)

            kids = children.get(pid, [])
            for i, cpid in enumerate(kids):
                is_last = (i == len(kids) - 1)
                traverse(cpid, depth + 1, ancestors_last + [is_last])

        for root_pid in sorted([r["pid"] for r in roots]):
            traverse(root_pid, 0, [])

        return flat


# ──────────────────────────────────────────────────────────────
# Curses helpers
# ──────────────────────────────────────────────────────────────

# Color pair IDs
COL_GREEN = 1
COL_YELLOW = 2
COL_RED = 3
COL_HEADER = 4
COL_SELECTED = 5
COL_DIM = 6
COL_WHITE = 7
COL_CYAN = 8
COL_BAR_BG = 9
COL_HIGHLIGHT = 10


def init_colors():
    """Set up color pairs."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COL_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COL_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COL_RED, curses.COLOR_RED, -1)
    curses.init_pair(COL_HEADER, curses.COLOR_CYAN, -1)
    curses.init_pair(COL_SELECTED, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(COL_DIM, 8, -1)  # bright black = grey
    curses.init_pair(COL_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(COL_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COL_BAR_BG, 8, -1)
    curses.init_pair(COL_HIGHLIGHT, curses.COLOR_YELLOW, -1)


def color_for(usage: float) -> int:
    """Green <50%, Yellow 50-80%, Red >80%."""
    if usage < 0.5:
        return COL_GREEN
    elif usage < 0.8:
        return COL_YELLOW
    else:
        return COL_RED


def safe_addstr(win, y: int, x: int, text: str, attr=curses.A_NORMAL):
    """Add string, ignoring errors if out of bounds."""
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_bar(win, y: int, x: int, width: int, fraction: float,
             label: str = "", extra: str = ""):
    """Draw a horizontal progress bar with blocks."""
    bar_width = width - len(label) - len(extra) - 3
    if bar_width < 4:
        return
    filled = int(round(max(0.0, min(1.0, fraction)) * bar_width))
    empty = bar_width - filled
    c = color_for(fraction)
    bar = "█" * filled + "░" * empty
    text = f"{label}[{bar}]{extra}"
    safe_addstr(win, y, x, text[:width], curses.color_pair(c))


def draw_section_header(win, y: int, x: int, width: int, title: str):
    """Draw a section header with underline."""
    safe_addstr(win, y, x, f"── {title} ", curses.color_pair(COL_HEADER) | curses.A_BOLD)
    remaining = width - len(title) - 5
    if remaining > 0:
        safe_addstr(win, y, x + len(title) + 5, "─" * remaining,
                     curses.color_pair(COL_HEADER))


# ──────────────────────────────────────────────────────────────
# View classes
# ──────────────────────────────────────────────────────────────

class OverviewView:
    """CPU, memory, swap, uptime, load, battery."""

    def draw(self, win, data: Dict[str, Any], height: int, width: int):
        win.erase()
        y = 0

        # ── CPU per-core bars ──
        cpu_data = data.get("cpu", {})
        per_core = cpu_data.get("per_core", [])
        agg = cpu_data.get("aggregate", 0.0)
        history = cpu_data.get("history", [])

        draw_section_header(win, y, 0, width, "CPU Usage")
        y += 1

        max_cores = min(len(per_core), height - 22)
        for i in range(max_cores):
            usage = per_core[i]
            pct_str = f"{usage * 100:5.1f}%"
            draw_bar(win, y, 0, width - 8, usage, f"CPU{i:2d} ")
            safe_addstr(win, y, width - 7, pct_str, curses.color_pair(color_for(usage)))
            y += 1
        if len(per_core) > max_cores:
            safe_addstr(win, y, 0,
                        f"  ... plus {len(per_core) - max_cores} more cores",
                        curses.color_pair(COL_DIM))
            y += 1

        # ── Braille CPU history (last 60s) ──
        y += 1
        safe_addstr(win, y, 0, " CPU History (60s):", curses.color_pair(COL_HEADER) | curses.A_BOLD)
        y += 1

        graph_width = width - 4
        if graph_width > 0 and history:
            max_points = min(60, graph_width * 2)
            hist = history[-max_points:] if len(history) > max_points else history
            if len(hist) < max_points:
                hist = [0.0] * (max_points - len(hist)) + hist

            braille_line = ""
            for i in range(0, len(hist) - 1, 2):
                lv = hist[i]
                rv = hist[i + 1] if i + 1 < len(hist) else 0.0
                braille_line += braille_char(lv, rv)

            safe_addstr(win, y, 2, braille_line[:graph_width],
                       curses.color_pair(color_for(agg)))
        y += 1
        safe_addstr(win, y, 2, f"Total: {agg * 100:.1f}%",
                   curses.color_pair(color_for(agg)))
        y += 2

        # ── Memory ──
        mem = data.get("mem", {})
        mem_total = max(mem.get("MemTotal", 1), 1)
        mem_free = mem.get("MemFree", 0)
        mem_avail = mem.get("MemAvailable", 0)
        mem_cached = mem.get("Cached", 0)
        mem_buffers = mem.get("Buffers", 0)
        mem_used = mem_total - mem_free - mem_buffers - mem_cached
        mem_used = max(mem_used, 0)
        mem_frac = mem_used / mem_total

        draw_section_header(win, y, 0, width, "Memory")
        y += 1
        draw_bar(win, y, 0, width - 8, mem_frac, "RAM  ")
        safe_addstr(win, y, width - 7, f"{mem_frac * 100:5.1f}%",
                   curses.color_pair(color_for(mem_frac)))
        y += 1
        info = (f"  Total: {human_bytes(mem_total * 1024)}  "
                f"Used: {human_bytes(mem_used * 1024)}  "
                f"Free: {human_bytes(mem_free * 1024)}  "
                f"Avail: {human_bytes(mem_avail * 1024)}  "
                f"Cache: {human_bytes(mem_cached * 1024)}")
        safe_addstr(win, y, 0, info[:width], curses.color_pair(COL_WHITE))
        y += 2

        # ── Swap ──
        swap_total = max(mem.get("SwapTotal", 0), 0)
        swap_free = mem.get("SwapFree", 0)
        if swap_total > 0:
            swap_used = swap_total - swap_free
            swap_frac = swap_used / swap_total
            draw_section_header(win, y, 0, width, "Swap")
            y += 1
            draw_bar(win, y, 0, width - 8, swap_frac, "Swap ")
            safe_addstr(win, y, width - 7, f"{swap_frac * 100:5.1f}%",
                       curses.color_pair(color_for(swap_frac)))
            y += 1
            safe_addstr(win, y, 0,
                       f"  Total: {human_bytes(swap_total * 1024)}  "
                       f"Used: {human_bytes(swap_used * 1024)}  "
                       f"Free: {human_bytes(swap_free * 1024)}",
                       curses.color_pair(COL_WHITE))
            y += 2
        else:
            safe_addstr(win, y, 0, " Swap: none", curses.color_pair(COL_DIM))
            y += 2

        # ── System uptime & load ──
        draw_section_header(win, y, 0, width, "System")
        y += 1
        uptime_secs = data.get("uptime", 0.0)
        days = int(uptime_secs // 86400)
        hrs = int((uptime_secs % 86400) // 3600)
        mins = int((uptime_secs % 3600) // 60)
        secs = int(uptime_secs % 60)
        uptime_str = f"{days}d {hrs:02d}:{mins:02d}:{secs:02d}"

        load = data.get("load", (0.0, 0.0, 0.0, 0, 0))
        load_str = f"Load avg: {load[0]:.2f}  {load[1]:.2f}  {load[2]:.2f}"

        safe_addstr(win, y, 0, f"  Uptime: {uptime_str}    {load_str}"[:width],
                   curses.color_pair(COL_WHITE))
        y += 2

        # ── Battery ──
        battery = data.get("battery")
        if battery:
            draw_section_header(win, y, 0, width, "Battery")
            y += 1
            cap = battery["capacity"]
            status = battery["status"]
            frac = cap / 100.0
            draw_bar(win, y, 0, width - 20, frac, "BAT  ")
            extra = f" {cap}% {status}"
            remaining = battery.get("time_remaining")
            if remaining is not None and remaining > 0:
                h = int(remaining)
                m = int((remaining - h) * 60)
                extra += f"  {h}h{m:02d}m"
            safe_addstr(win, y, width - len(extra), extra,
                       curses.color_pair(color_for(1.0 - frac)))
            y += 2

        # Fill remaining space
        safe_addstr(win, height - 1, 0,
                   " Tab:Views │ F5:Refresh │ q:Quit",
                   curses.color_pair(COL_DIM))

        win.noutrefresh()


class ProcessView:
    """Scrollable process table with sorting, filtering, tree mode."""

    def __init__(self):
        self.scroll = 0
        self.sel = 0
        self.sort_key = "cpu_pct"
        self.sort_rev = True
        self.filter = ""
        self.tree = False
        self.max_rows = 0

    def _build_list(self, processes: List[Dict]) -> List[Dict]:
        """Build the display list (tree or flat, filtered, sorted)."""
        if self.tree:
            lst = ProcessCollector.build_tree(processes)
        else:
            lst = [dict(p) for p in processes]

        if self.filter:
            ft = self.filter.lower()
            lst = [p for p in lst
                   if ft in p.get("command", "").lower() or
                   ft in p.get("comm", "").lower()]

        if not self.tree:
            lst.sort(key=lambda x: x.get(self.sort_key, 0), reverse=self.sort_rev)

        return lst

    def draw(self, win, data: Dict[str, Any], height: int, width: int):
        win.erase()
        processes = data.get("processes", [])
        display = self._build_list(processes)

        # Clamp selection
        if display:
            self.sel = max(0, min(self.sel, len(display) - 1))
        else:
            self.sel = 0

        # Title line
        sort_name = {"cpu_pct": "CPU", "mem_pct": "MEM", "pid": "PID"}.get(self.sort_key, "CPU")
        arrow = "▼" if self.sort_rev else "▲"
        title = f"Processes [sort: {sort_name}{arrow}]"
        if self.tree:
            title += " [TREE]"
        if self.filter:
            title += f' [filter: "{self.filter}"]'
        draw_section_header(win, 0, 0, width, title)
        # Column headers
        col_hdr = f"  {'PID':>7} {'USER':<8} {'CPU%':>6} {'MEM%':>6} {'S':>1} {'NICE':>4}  COMMAND"
        safe_addstr(win, 1, 0, col_hdr[:width], curses.color_pair(COL_HEADER) | curses.A_BOLD)
        safe_addstr(win, 2, 0, "─" * width, curses.color_pair(COL_DIM))

        # Available rows
        self.max_rows = max(1, height - 5)  # title + col_hdr + sep + status

        # Adjust scroll
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + self.max_rows:
            self.scroll = max(0, self.sel - self.max_rows + 1)

        # Draw rows
        for i in range(self.max_rows):
            row_y = 3 + i
            idx = self.scroll + i
            if idx >= len(display):
                break

            p = display[idx]
            is_sel = (idx == self.sel)
            prefix = p.get("tree_prefix", "")
            cmd = prefix + p.get("command", p.get("comm", "?"))
            # Truncate command
            cmd_max = width - 40
            if len(cmd) > max(cmd_max, 5):
                cmd = cmd[:max(cmd_max, 5) - 1] + "…"

            line = (f"{p['pid']:>8} {p.get('user', '?'):<8} "
                    f"{p['cpu_pct']:5.1f}  {p['mem_pct']:5.1f}  "
                    f"{p['state']:>1} {p.get('nice', 0):>4}  {cmd}")

            attr = curses.A_NORMAL
            if is_sel:
                attr |= curses.color_pair(COL_SELECTED)
                line = line.ljust(width)

            safe_addstr(win, row_y, 0, line[:width], attr)

        # Status bar
        status = (f" {len(display)} processes"
                  f" │ c:CPU m:MEM p:PID sort  /:search  Esc:clear"
                  f"  t:tree  K:kill  r:renice  j/k:move")
        safe_addstr(win, height - 1, 0, status[:width], curses.color_pair(COL_DIM))
        safe_addstr(win, height - 2, 0, "─" * width, curses.color_pair(COL_DIM))

        win.noutrefresh()


class NetworkView:
    """Network I/O and connection states."""

    def draw(self, win, data: Dict[str, Any], height: int, width: int):
        win.erase()
        y = 0

        draw_section_header(win, y, 0, width, "Network Interfaces")
        y += 1

        net_data = data.get("network", {})
        safe_addstr(win, y, 0,
                   f"{'Interface':<12} {'RX/s':>12} {'TX/s':>12} {'Total RX':>14} {'Total TX':>14}"[:width],
                   curses.color_pair(COL_HEADER) | curses.A_BOLD)
        y += 1

        if not net_data:
            safe_addstr(win, y, 2, "(no data)", curses.color_pair(COL_DIM))
            y += 1
        else:
            for iface, info in sorted(net_data.items()):
                if y >= height - 6:
                    break
                rx_rate = human_rate(info["rx_rate"])
                tx_rate = human_rate(info["tx_rate"])
                total_rx = human_bytes(info["rx_bytes"])
                total_tx = human_bytes(info["tx_bytes"])
                line = f"{iface:<12} {rx_rate:>12} {tx_rate:>12} {total_rx:>14} {total_tx:>14}"
                safe_addstr(win, y, 0, line[:width])
                y += 1

        y += 1
        draw_section_header(win, y, 0, width, "Connection States")
        y += 1

        conns = data.get("connections", {})
        if not conns:
            safe_addstr(win, y, 2, "(no data)", curses.color_pair(COL_DIM))
        else:
            order = ["ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT",
                     "SYN_SENT", "SYN_RECV", "FIN_WAIT1", "FIN_WAIT2",
                     "CLOSE", "LAST_ACK", "CLOSING"]
            parts = []
            for state in order:
                c = conns.get(state, 0)
                if c > 0:
                    parts.append(f"{state}:{c}")
            line = "  ".join(parts)
            safe_addstr(win, y, 2, line[:width - 2])

        safe_addstr(win, height - 1, 0,
                   " Tab:Views │ F5:Refresh │ q:Quit",
                   curses.color_pair(COL_DIM))
        win.noutrefresh()


class DiskView:
    """Disk usage and I/O rates."""

    def draw(self, win, data: Dict[str, Any], height: int, width: int):
        win.erase()
        y = 0

        draw_section_header(win, y, 0, width, "Filesystems")
        y += 1

        mounts = data.get("mounts", [])
        safe_addstr(win, y, 0,
                   f"{'Mount':<20} {'Total':>10} {'Used':>10} {'Free':>10} {'Use%':>6}"[:width],
                   curses.color_pair(COL_HEADER) | curses.A_BOLD)
        y += 1

        half = height // 2 - 2
        if not mounts:
            safe_addstr(win, y, 2, "(no data)", curses.color_pair(COL_DIM))
            y += 1
        else:
            for m in mounts:
                if y >= half:
                    break
                pct = m["pct"]
                line = (f"{m['mount']:<20} {human_bytes(m['total']):>10} "
                        f"{human_bytes(m['used']):>10} {human_bytes(m['free']):>10} "
                        f"{pct:5.1f}%")
                safe_addstr(win, y, 0, line[:width], curses.color_pair(color_for(pct / 100.0)))
                y += 1

        y += 1
        draw_section_header(win, y, 0, width, "Disk I/O")
        y += 1

        disk_io = data.get("disk_io", {})
        safe_addstr(win, y, 0,
                   f"{'Device':<16} {'Read/s':>12} {'Write/s':>12}"[:width],
                   curses.color_pair(COL_HEADER) | curses.A_BOLD)
        y += 1

        if not disk_io:
            safe_addstr(win, y, 2, "(no data)", curses.color_pair(COL_DIM))
        else:
            for dev, info in sorted(disk_io.items()):
                if y >= height - 2:
                    break
                rr = human_rate(info["read_rate"])
                wr = human_rate(info["write_rate"])
                line = f"{dev:<16} {rr:>12} {wr:>12}"
                safe_addstr(win, y, 0, line[:width])
                y += 1

        safe_addstr(win, height - 1, 0,
                   " Tab:Views │ F5:Refresh │ q:Quit",
                   curses.color_pair(COL_DIM))
        win.noutrefresh()


# ──────────────────────────────────────────────────────────────
# Modal prompts
# ──────────────────────────────────────────────────────────────

def modal_confirm(scr, msg: str) -> bool:
    """Blocking confirmation prompt. Returns True on 'y'."""
    max_y, max_x = scr.getmaxyx()
    y = max_y - 2
    scr.move(y, 0)
    scr.clrtoeol()
    safe_addstr(scr, y, 1, f"{msg} (y/N)", curses.color_pair(COL_HIGHLIGHT) | curses.A_BOLD)
    scr.refresh()
    curses.curs_set(1)
    try:
        while True:
            ch = scr.getch()
            if ch in (ord("y"), ord("Y")):
                return True
            elif ch in (ord("n"), ord("N"), 27, ord("\n"), ord("\r")):
                return False
    finally:
        curses.curs_set(0)


def modal_input(scr, prompt: str, initial: str = "") -> Optional[str]:
    """Blocking text input. Returns string or None on Escape."""
    max_y, max_x = scr.getmaxyx()
    y = max_y - 2
    buf = list(initial)

    def redraw():
        scr.move(y, 0)
        scr.clrtoeol()
        display = f"{prompt}{''.join(buf)} "
        safe_addstr(scr, y, 1, display[:max_x - 2],
                    curses.color_pair(COL_HIGHLIGHT) | curses.A_BOLD)
        scr.refresh()

    redraw()
    curses.curs_set(1)
    try:
        while True:
            ch = scr.getch()
            if ch == 27:
                return None
            elif ch in (ord("\n"), ord("\r")):
                return "".join(buf)
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if buf:
                    buf.pop()
            elif 32 <= ch <= 126:
                buf.append(chr(ch))
            redraw()
    finally:
        curses.curs_set(0)


# ──────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────

class App:
    """Main curses application controller."""

    VIEW_OVERVIEW = 0
    VIEW_PROCESSES = 1
    VIEW_NETWORK = 2
    VIEW_DISK = 3
    VIEW_NAMES = ["Overview", "Processes", "Network", "Disk"]

    def __init__(self, interval: float):
        self.interval = max(0.1, interval)
        self.running = True
        self.view_idx = self.VIEW_OVERVIEW
        self.force_refresh = True

        # Collectors
        self.cpu = CPUCollector()
        self.mem = MemoryCollector()
        self.uptime_c = UptimeCollector()
        self.load_c = LoadCollector()
        self.net = NetworkCollector()
        self.conn = ConnectionCollector()
        self.disk = DiskCollector()
        self.bat = BatteryCollector()
        self.proc = ProcessCollector()

        # Views
        self.oview = OverviewView()
        self.pview = ProcessView()
        self.nview = NetworkView()
        self.dview = DiskView()

        self.data: Dict[str, Any] = {}

    def collect(self):
        """Gather all system data once."""
        d: Dict[str, Any] = {}
        d["cpu"] = self.cpu.update()
        d["mem"] = self.mem.update()
        d["uptime"] = self.uptime_c.update()
        d["load"] = self.load_c.update()
        d["network"] = self.net.update()
        d["connections"] = self.conn.update()
        d["mounts"] = self.disk.update_usage()
        d["disk_io"] = self.disk.update_io()
        d["battery"] = self.bat.update()
        d["processes"] = self.proc.update(d["mem"].get("MemTotal", 1))
        return d

    def run(self, scr):
        curses.curs_set(0)
        scr.timeout(int(self.interval * 1000))
        scr.keypad(True)
        init_colors()

        self.data = self.collect()
        last_tick = time.monotonic()

        while self.running:
            max_y, max_x = scr.getmaxyx()

            # Refresh data on interval or forced
            now = time.monotonic()
            if self.force_refresh or (now - last_tick >= self.interval):
                try:
                    self.data = self.collect()
                except Exception:
                    pass  # keep old data if collection fails
                last_tick = now
                self.force_refresh = False

            # Draw tab bar at top
            scr.erase()
            tab_line = ""
            for i, name in enumerate(self.VIEW_NAMES):
                if i == self.view_idx:
                    tab_line += f" [ {name} ] "
                else:
                    tab_line += f"   {name}   "
            safe_addstr(scr, 0, 1, tab_line[:max_x - 2],
                       curses.color_pair(COL_HEADER) | curses.A_BOLD)
            safe_addstr(scr, 1, 0, "═" * max_x, curses.color_pair(COL_HEADER))

            # Content area starts at line 2
            content_h = max(1, max_y - 2)
            content_w = max_x
            try:
                cwin = scr.derwin(content_h, content_w, 2, 0)
            except curses.error:
                cwin = scr

            # Draw active view
            if self.view_idx == self.VIEW_OVERVIEW:
                self.oview.draw(cwin, self.data, content_h, content_w)
            elif self.view_idx == self.VIEW_PROCESSES:
                self.pview.draw(cwin, self.data, content_h, content_w)
            elif self.view_idx == self.VIEW_NETWORK:
                self.nview.draw(cwin, self.data, content_h, content_w)
            elif self.view_idx == self.VIEW_DISK:
                self.dview.draw(cwin, self.data, content_h, content_w)

            scr.refresh()

            # Input
            try:
                ch = scr.getch()
            except KeyboardInterrupt:
                break
            if ch == -1:
                continue
            self._handle(ch, scr)

        curses.curs_set(1)

    def _handle(self, ch: int, scr):
        max_y, max_x = scr.getmaxyx()

        # ── Global keys ──
        if ch in (ord("q"), curses.KEY_F10):
            self.running = False
            return
        if ch == curses.KEY_F5:
            self.force_refresh = True
            return
        if ch == 9 or ch == ord("\t"):  # Tab
            self.view_idx = (self.view_idx + 1) % len(self.VIEW_NAMES)
            self.force_refresh = True
            return
        if ch == curses.KEY_RESIZE:
            self.force_refresh = True
            return

        # ── Process view keys ──
        if self.view_idx == self.VIEW_PROCESSES:
            self._process_keys(ch, scr)

    def _process_keys(self, ch: int, scr):
        pv = self.pview
        processes = self.data.get("processes", [])
        display = pv._build_list(processes)

        if ch == ord("j") or ch == curses.KEY_DOWN:
            if display:
                pv.sel = min(pv.sel + 1, len(display) - 1)
                if pv.sel >= pv.scroll + pv.max_rows:
                    pv.scroll = pv.sel - pv.max_rows + 1
        elif ch == ord("k") or ch == curses.KEY_UP:
            if display:
                pv.sel = max(pv.sel - 1, 0)
                if pv.sel < pv.scroll:
                    pv.scroll = pv.sel
        elif ch == ord("g"):
            pv.sel = 0
            pv.scroll = 0
        elif ch == ord("G"):
            if display:
                pv.sel = len(display) - 1
                pv.scroll = max(0, pv.sel - pv.max_rows + 1)
        elif ch == curses.KEY_NPAGE or ch == ord("\x04"):  # Ctrl-D / PageDown
            if display:
                pv.sel = min(pv.sel + pv.max_rows, len(display) - 1)
                pv.scroll = min(pv.scroll + pv.max_rows,
                                max(0, len(display) - pv.max_rows))
        elif ch == curses.KEY_PPAGE or ch == ord("\x15"):  # Ctrl-U / PageUp
            if display:
                pv.sel = max(pv.sel - pv.max_rows, 0)
                pv.scroll = max(pv.scroll - pv.max_rows, 0)
        elif ch == ord("c"):
            pv.sort_key = "cpu_pct"
            pv.sort_rev = True
            pv.tree = False
        elif ch == ord("m"):
            pv.sort_key = "mem_pct"
            pv.sort_rev = True
            pv.tree = False
        elif ch == ord("p"):
            pv.sort_key = "pid"
            pv.sort_rev = True
            pv.tree = False
        elif ch == ord("t"):
            pv.tree = not pv.tree
            pv.sel = 0
            pv.scroll = 0
        elif ch == ord("/"):
            result = modal_input(scr, "Search: ", pv.filter)
            if result is not None:
                pv.filter = result
            pv.sel = 0
            pv.scroll = 0
            self.force_refresh = True
        elif ch == 27:  # Escape
            if pv.filter:
                pv.filter = ""
                pv.sel = 0
                pv.scroll = 0
                self.force_refresh = True
        elif ch == ord("K"):
            if display and pv.sel < len(display):
                proc = display[pv.sel]
                if modal_confirm(scr,
                                 f"Send SIGKILL to PID {proc['pid']} "
                                 f"({proc.get('command', proc.get('comm', '?'))[:40]})?"):
                    try:
                        os.kill(proc["pid"], signal.SIGKILL)
                    except (PermissionError, ProcessLookupError, OSError):
                        pass
                    self.force_refresh = True
        elif ch == ord("r"):
            if display and pv.sel < len(display):
                proc = display[pv.sel]
                cur_nice = proc.get("nice", 0)
                result = modal_input(
                    scr,
                    f"New nice value [-20..19] for PID {proc['pid']} "
                    f"({proc.get('command', proc.get('comm', '?'))[:30]}): ",
                )
                if result is not None and result.strip():
                    try:
                        new_val = int(result.strip())
                        new_val = max(-20, min(19, new_val))
                        libc = ctypes.CDLL("libc.so.6")
                        # PRIO_PROCESS = 0
                        ret = libc.setpriority(0, proc["pid"], new_val)
                        if ret != 0:
                            # Fallback: try renice command
                            os.system(f"renice {new_val} -p {proc['pid']} >/dev/null 2>&1")
                    except (ValueError, OSError):
                        pass
                    self.force_refresh = True


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Terminal-based system monitor (htop-style) using /proc"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    app = App(interval=args.interval)

    try:
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
