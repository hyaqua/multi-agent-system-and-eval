"""Data collectors that read from /proc and /sys filesystems."""

import os
import pwd
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

# Cache for CPU delta calculations
_cpu_prev: Dict[str, Tuple[int, int]] = {}  # cpu_name -> (total, idle) from previous tick
_cpu_prev_time: float = 0.0

# Cache for process CPU calculations
_proc_prev: Dict[int, Tuple[int, int, float]] = {}  # pid -> (utime+stime, total_cpu_ticks, timestamp)
_proc_prev_time: float = 0.0

# Cache for network delta
_net_prev: Dict[str, Tuple[int, int, float]] = {}  # iface -> (rx_bytes, tx_bytes, timestamp)

# Cache for disk I/O delta
_disk_prev: Dict[str, Tuple[int, int, float]] = {}  # disk -> (sectors_read, sectors_write, timestamp)

# CPU history for sparkline
_cpu_history: deque = deque(maxlen=60)


def get_cpu_times() -> Dict[str, Dict[str, int]]:
    """Read /proc/stat and return per-CPU time values."""
    cpus = {}
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu"):
                    parts = line.strip().split()
                    name = parts[0]
                    # cpu line (aggregate) and cpu0, cpu1, ...
                    if len(parts) >= 8:
                        vals = [int(x) for x in parts[1:8]]
                        cpus[name] = {
                            "user": vals[0],
                            "nice": vals[1],
                            "system": vals[2],
                            "idle": vals[3],
                            "iowait": vals[4] if len(vals) > 4 else 0,
                            "irq": vals[5] if len(vals) > 5 else 0,
                            "softirq": vals[6] if len(vals) > 6 else 0,
                            "steal": vals[7] if len(vals) > 7 else 0,
                        }
                elif not line.startswith("cpu"):
                    break
    except (IOError, OSError, ValueError):
        pass
    return cpus


def get_cpu_percent() -> tuple:
    """Return (per_core_percents dict, overall_percent float)."""
    global _cpu_prev, _cpu_prev_time, _cpu_history

    cpus = get_cpu_times()
    now = time.time()

    per_core = {}
    overall = 0.0

    for name, times in cpus.items():
        total = sum(times.values())
        idle = times["idle"] + times.get("iowait", 0)
        if name in _cpu_prev:
            prev_total, prev_idle = _cpu_prev[name]
            delta_total = total - prev_total
            delta_idle = idle - prev_idle
            if delta_total > 0:
                usage = (1.0 - delta_idle / delta_total) * 100
            else:
                usage = 0.0
        else:
            usage = 0.0
        _cpu_prev[name] = (total, idle)
        per_core[name] = usage

    if "cpu" in per_core:
        overall = per_core["cpu"]
    else:
        # Calculate overall from per-core average
        core_usages = [v for k, v in per_core.items() if k != "cpu"]
        if core_usages:
            overall = sum(core_usages) / len(core_usages)

    _cpu_prev_time = now
    _cpu_history.append(overall)

    return per_core, overall


def get_memory() -> Dict[str, int]:
    """Read /proc/meminfo and return memory values in KiB."""
    mem = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                key = parts[0].rstrip(":")
                val = int(parts[1])
                mem[key] = val
    except (IOError, OSError, ValueError):
        return {}
    return mem


def get_memory_info() -> Dict[str, int]:
    """Get processed memory info in bytes."""
    mem = get_memory()
    result = {}
    result["total"] = mem.get("MemTotal", 0) * 1024
    result["free"] = mem.get("MemFree", 0) * 1024
    result["available"] = mem.get("MemAvailable", 0) * 1024
    result["buffers"] = mem.get("Buffers", 0) * 1024
    result["cached"] = (mem.get("Cached", 0) + mem.get("SReclaimable", 0)) * 1024
    result["used"] = result["total"] - result["available"]
    result["swap_total"] = mem.get("SwapTotal", 0) * 1024
    result["swap_free"] = mem.get("SwapFree", 0) * 1024
    result["swap_used"] = result["swap_total"] - result["swap_free"]
    return result


def get_uptime() -> float:
    """Read /proc/uptime and return uptime in seconds."""
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.readline().strip().split()[0])
    except (IOError, OSError, ValueError):
        return 0.0


def get_loadavg() -> Tuple[float, float, float]:
    """Read /proc/loadavg and return (1min, 5min, 15min)."""
    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.readline().strip().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except (IOError, OSError, ValueError):
        return 0.0, 0.0, 0.0


def get_total_cpu_ticks() -> int:
    """Get total CPU ticks from /proc/stat."""
    cpus = get_cpu_times()
    if "cpu" in cpus:
        return sum(cpus["cpu"].values())
    return 0


def _parse_stat(stat_str: str) -> dict:
    """Parse /proc/[pid]/stat handling the comm field with spaces and parens."""
    # stat format: pid (comm) state ppid ...
    # Find the closing paren
    close_paren = stat_str.rfind(")")
    if close_paren == -1:
        return {}
    before_comm = stat_str[:close_paren + 1]
    after_comm = stat_str[close_paren + 1:].strip()
    # Extract comm
    open_paren = before_comm.find("(")
    if open_paren == -1:
        return {}
    pid_str = before_comm[:open_paren].strip().split()
    comm = before_comm[open_paren + 1:close_paren]
    pid = int(pid_str[0])
    fields = after_comm.split()
    return {
        "pid": pid,
        "comm": comm,
        "fields": fields,
    }


def get_processes(mem_total_bytes: int) -> List[Dict]:
    """Scan /proc and return process info list."""
    global _proc_prev, _proc_prev_time

    processes = []
    now = time.time()
    total_cpu_ticks = get_total_cpu_ticks()

    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        proc_dir = f"/proc/{entry}"
        try:
            # Read stat
            with open(f"{proc_dir}/stat", "r") as f:
                stat_str = f.read()
        except (IOError, OSError):
            continue

        parsed = _parse_stat(stat_str)
        if not parsed:
            continue
        fields = parsed.get("fields", [])
        if len(fields) < 20:
            continue

        try:
            state = fields[0]
            ppid = int(fields[1])
            utime = int(fields[11])
            stime = int(fields[12])
            cutime = int(fields[13])
            cstime = int(fields[14])
            starttime = int(fields[19])
            # RSS is field 21 (0-indexed from after comm: state=0, ppid=1, ..., rss=21)
            # Actually: state=0, ppid=1, pgrp=2, session=3, tty=4, tpgid=5, flags=6,
            # minflt=7, cminflt=8, majflt=9, cmajflt=10, utime=11, stime=12,
            # cutime=13, cstime=14, priority=15, nice=16, num_threads=17,
            # itrealvalue=18, starttime=19, vsize=20, rss=21
            rss = int(fields[21]) if len(fields) > 21 else 0
        except (IndexError, ValueError):
            continue

        # Read status for Uid and VmRSS (more reliable RSS)
        uid = 0
        vmrss_kb = 0
        try:
            with open(f"{proc_dir}/status", "r") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        parts = line.strip().split()
                        if len(parts) > 1:
                            uid = int(parts[1])
                    elif line.startswith("VmRSS:"):
                        parts = line.strip().split()
                        if len(parts) > 1:
                            vmrss_kb = int(parts[1])
        except (IOError, OSError):
            pass

        # Get username
        try:
            user = pwd.getpwuid(uid).pw_name
        except (KeyError, OSError):
            user = str(uid)

        # Get command
        command = parsed.get("comm", "")
        try:
            with open(f"{proc_dir}/cmdline", "r") as f:
                cmdline = f.read().replace('\0', ' ').strip()
                if cmdline:
                    command = cmdline
        except (IOError, OSError):
            pass

        # CPU% calculation
        proc_total = utime + stime + cutime + cstime
        if pid in _proc_prev:
            prev_total, prev_cpu_ticks, prev_time = _proc_prev[pid]
            delta_proc = proc_total - prev_total
            delta_cpu = total_cpu_ticks - prev_cpu_ticks
            if delta_cpu > 0:
                cpu_percent = (delta_proc / delta_cpu) * 100
            else:
                cpu_percent = 0.0
        else:
            cpu_percent = 0.0
        _proc_prev[pid] = (proc_total, total_cpu_ticks, now)

        # MEM%
        mem_bytes = vmrss_kb * 1024
        mem_percent = (mem_bytes / mem_total_bytes * 100) if mem_total_bytes > 0 else 0.0

        processes.append({
            "pid": pid,
            "ppid": ppid,
            "user": user,
            "cpu_percent": cpu_percent,
            "mem_percent": mem_percent,
            "mem_bytes": mem_bytes,
            "state": state,
            "command": command,
        })

    # Clean old entries from _proc_prev
    current_pids = {p["pid"] for p in processes}
    _proc_prev = {k: v for k, v in _proc_prev.items() if k in current_pids}
    _proc_prev_time = now

    return processes


def get_network_interfaces() -> List[Dict]:
    """Read /proc/net/dev and return per-interface network stats."""
    global _net_prev

    interfaces = []
    now = time.time()
    try:
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return interfaces

    # Skip header lines
    for line in lines[2:]:
        line = line.strip()
        parts = line.split()
        if len(parts) < 10:
            continue
        iface = parts[0].rstrip(":")
        try:
            rx_bytes = int(parts[1])
            tx_bytes = int(parts[9])
        except (IndexError, ValueError):
            continue

        rx_rate = 0.0
        tx_rate = 0.0
        if iface in _net_prev:
            prev_rx, prev_tx, prev_time = _net_prev[iface]
            dt = now - prev_time
            if dt > 0:
                rx_rate = (rx_bytes - prev_rx) / dt
                tx_rate = (tx_bytes - prev_tx) / dt

        _net_prev[iface] = (rx_bytes, tx_bytes, now)

        interfaces.append({
            "name": iface,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "rx_rate": max(0, rx_rate),
            "tx_rate": max(0, tx_rate),
        })

    # Clean old interfaces
    current = {i["name"] for i in interfaces}
    _net_prev = {k: v for k, v in _net_prev.items() if k in current}

    return interfaces


def get_mounts() -> List[Dict]:
    """Read /proc/mounts and return real filesystem mount points."""
    mounts = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                device, mountpoint, fstype, _ = parts[:4]
                # Skip pseudo filesystems
                if fstype in (
                    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs",
                    "cgroup", "cgroup2", "pstore", "bpf", "debugfs",
                    "tracefs", "securityfs", "configfs", "hugetlbfs",
                    "fusectl", "mqueue", "rpc_pipefs", "binfmt_misc",
                    "autofs", "ramfs",
                ):
                    continue
                # Skip these prefix types (keep overlay, nfs, fuse for network)
                if fstype.startswith("nfs"):
                    pass  # keep network filesystems
                mounts.append({
                    "device": device,
                    "mountpoint": mountpoint,
                    "fstype": fstype,
                })
    except (IOError, OSError):
        pass
    return mounts


def get_disk_usage(mounts: List[Dict]) -> List[Dict]:
    """Get disk usage for each mount point using os.statvfs."""
    results = []
    for m in mounts:
        try:
            stat = os.statvfs(m["mountpoint"])
        except (OSError, PermissionError):
            continue
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bavail
        used = total - free
        percent = (used / total * 100) if total > 0 else 0.0
        results.append({
            "device": m["device"],
            "mountpoint": m["mountpoint"],
            "fstype": m["fstype"],
            "total": total,
            "used": used,
            "free": free,
            "percent": percent,
        })
    return results


def get_disk_io() -> List[Dict]:
    """Read /proc/diskstats and return disk I/O stats with rates."""
    global _disk_prev

    disks = []
    now = time.time()
    try:
        with open("/proc/diskstats", "r") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return disks

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 14:
            continue
        try:
            name = parts[2]
            sectors_read = int(parts[5])
            sectors_write = int(parts[9])
        except (IndexError, ValueError):
            continue

        # Skip loop and ram devices
        if name.startswith("loop") or name.startswith("ram"):
            continue

        bytes_read = sectors_read * 512
        bytes_write = sectors_write * 512

        read_rate = 0.0
        write_rate = 0.0
        if name in _disk_prev:
            prev_read_sectors, prev_write_sectors, prev_time = _disk_prev[name]
            dt = now - prev_time
            if dt > 0:
                read_rate = (sectors_read - prev_read_sectors) * 512 / dt
                write_rate = (sectors_write - prev_write_sectors) * 512 / dt

        _disk_prev[name] = (sectors_read, sectors_write, now)

        disks.append({
            "name": name,
            "read_rate": max(0, read_rate),
            "write_rate": max(0, write_rate),
            "bytes_read": bytes_read,
            "bytes_write": bytes_write,
        })

    current = {d["name"] for d in disks}
    _disk_prev = {k: v for k, v in _disk_prev.items() if k in current}

    return disks


def get_battery() -> Optional[Dict]:
    """Read battery info from /sys/class/power_supply."""
    base = "/sys/class/power_supply"
    if not os.path.exists(base):
        return None

    for entry in os.listdir(base):
        path = os.path.join(base, entry)
        type_path = os.path.join(path, "type")
        if not os.path.exists(type_path):
            continue
        try:
            with open(type_path, "r") as f:
                ptype = f.read().strip()
        except (IOError, OSError):
            continue

        if ptype != "Battery":
            continue

        capacity = None
        status = "Unknown"
        energy_now = None
        energy_full = None
        power_now = None
        charge_now = None
        charge_full = None
        current_now = None

        # Read capacity
        cap_path = os.path.join(path, "capacity")
        if os.path.exists(cap_path):
            try:
                with open(cap_path, "r") as f:
                    capacity = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass

        # Read status
        stat_path = os.path.join(path, "status")
        if os.path.exists(stat_path):
            try:
                with open(stat_path, "r") as f:
                    status = f.read().strip()
            except (IOError, OSError):
                pass

        # Try energy (µWh)
        energy_now_path = os.path.join(path, "energy_now")
        energy_full_path = os.path.join(path, "energy_full")
        power_now_path = os.path.join(path, "power_now")

        if os.path.exists(energy_now_path):
            try:
                with open(energy_now_path, "r") as f:
                    energy_now = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass
        if os.path.exists(energy_full_path):
            try:
                with open(energy_full_path, "r") as f:
                    energy_full = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass
        if os.path.exists(power_now_path):
            try:
                with open(power_now_path, "r") as f:
                    power_now = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass

        # Try charge (µAh) if energy not available
        charge_now_path = os.path.join(path, "charge_now")
        charge_full_path = os.path.join(path, "charge_full")
        current_now_path = os.path.join(path, "current_now")

        if os.path.exists(charge_now_path):
            try:
                with open(charge_now_path, "r") as f:
                    charge_now = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass
        if os.path.exists(charge_full_path):
            try:
                with open(charge_full_path, "r") as f:
                    charge_full = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass
        if os.path.exists(current_now_path):
            try:
                with open(current_now_path, "r") as f:
                    current_now = int(f.read().strip())
            except (IOError, OSError, ValueError):
                pass

        # Estimate time remaining
        time_remaining = None
        if status == "Discharging":
            if power_now and power_now > 0 and energy_now and energy_now > 0:
                time_remaining = energy_now / power_now  # hours, convert to seconds
                time_remaining *= 3600
            elif current_now and current_now > 0 and charge_now and charge_now > 0:
                time_remaining = charge_now / current_now * 3600

        return {
            "capacity": capacity,
            "status": status,
            "time_remaining": time_remaining,
        }

    return None


def get_tcp_connections() -> Dict[str, int]:
    """Count TCP connections by state from /proc/net/tcp and /proc/net/tcp6."""
    state_names = {
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

    counts = {}
    for fname in ["/proc/net/tcp", "/proc/net/tcp6"]:
        try:
            with open(fname, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 4 or parts[0] == "sl":
                        continue
                    state = parts[3]
                    name = state_names.get(state, state)
                    counts[name] = counts.get(name, 0) + 1
        except (IOError, OSError):
            pass

    return counts


def get_cpu_history() -> deque:
    """Return the global CPU history deque."""
    return _cpu_history


def reset_cache():
    """Reset all cached data (for F5 force refresh)."""
    global _cpu_prev, _cpu_prev_time, _proc_prev, _proc_prev_time
    global _net_prev, _disk_prev, _cpu_history
    _cpu_prev = {}
    _cpu_prev_time = 0.0
    _proc_prev = {}
    _proc_prev_time = 0.0
    _net_prev = {}
    _disk_prev = {}
    _cpu_history = deque(maxlen=60)
