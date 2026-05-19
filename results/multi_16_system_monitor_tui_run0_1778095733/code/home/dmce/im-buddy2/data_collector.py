"""data_collector.py - System statistics collection from /proc and /sys."""

import os
import time
from collections import deque
from typing import List, Dict, Optional, Tuple, Deque


def _read_file(path: str) -> Optional[str]:
    """Read a file and return its content, or None on failure."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except (IOError, OSError, PermissionError):
        return None


def _read_file_lines(path: str) -> Optional[List[str]]:
    """Read a file and return its lines, or None on failure."""
    try:
        with open(path, 'r') as f:
            return f.readlines()
    except (IOError, OSError, PermissionError):
        return None


class DataCollector:
    """Collects and caches system statistics from /proc and /sys."""

    def __init__(self):
        # CPU tracking
        self._prev_cpu_times: Optional[List[List[int]]] = None
        self._prev_total_time: float = 0.0
        self._cpu_history: Deque[float] = deque(maxlen=60)

        # Per-process CPU tracking
        self._prev_proc_tick: float = 0.0
        self._prev_proc_total_cpu: float = 0.0
        self._prev_proc_times: Dict[int, int] = {}  # pid -> total_jiffies at last tick

        # Network tracking
        self._prev_net_time: float = 0.0
        self._prev_net_data: Dict[str, Tuple[int, int]] = {}  # iface -> (rx, tx)

        # Disk I/O tracking
        self._prev_disk_time: float = 0.0
        self._prev_disk_data: Dict[str, Tuple[int, int]] = {}  # dev -> (read_sectors, write_sectors)

        # Cached data
        self._last_update: float = 0.0
        self.cpu_per_core: List[Dict] = []
        self.cpu_total: float = 0.0
        self.memory: Dict = {}
        self.swap: Dict = {}
        self.uptime_seconds: float = 0.0
        self.loadavg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.processes: List[Dict] = []
        self.network: List[Dict] = []
        self.tcp_counts: Dict[str, int] = {}
        self.disk_usage: List[Dict] = []
        self.disk_io: List[Dict] = []
        self.battery: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Master update
    # ------------------------------------------------------------------
    def update(self) -> None:
        """Refresh all data. Call once per tick."""
        now = time.time()
        self._last_update = now
        self._update_cpu()
        self._update_memory()
        self._update_swap()
        self._update_uptime()
        self._update_loadavg()
        self._update_processes()
        self._update_network()
        self._update_tcp()
        self._update_disk_usage()
        self._update_disk_io()
        self._update_battery()

    # ------------------------------------------------------------------
    # CPU  (/proc/stat)
    # ------------------------------------------------------------------
    def _update_cpu(self) -> None:
        content = _read_file('/proc/stat')
        if not content:
            self.cpu_per_core = []
            self.cpu_total = 0.0
            return

        current_core_data: List[List[int]] = []
        for line in content.strip().split('\n'):
            if line.startswith('cpu'):
                parts = line.split()
                if parts[0] == 'cpu':
                    # total line – skip for per-core, keep for total
                    continue
                # per-core: cpu0, cpu1, ...
                try:
                    nums = [int(x) for x in parts[1:]]
                except ValueError:
                    nums = [0] * (len(parts) - 1)
                current_core_data.append(nums)

        # Build flat list of all ticks for total calculation
        all_ticks = []
        for core in current_core_data:
            all_ticks.extend(core)

        total_time = sum(all_ticks) if all_ticks else 0.0

        self.cpu_per_core = []
        if self._prev_cpu_times is not None and total_time > self._prev_total_time:
            delta = total_time - self._prev_total_time
            prev_flat = []
            for core in self._prev_cpu_times:
                prev_flat.extend(core)
            # Compute per-core usage
            prev_idx = 0
            for i, core in enumerate(current_core_data):
                core_ticks = sum(core)
                prev_core_ticks = sum(self._prev_cpu_times[i]) if i < len(self._prev_cpu_times) else 0
                # idle = iowait + idle + steal ... actually just idle
                # Use (total - idle) / delta
                idle = 0
                if len(core) >= 4:
                    idle = core[3]  # idle is index 3
                prev_idle = 0
                if self._prev_cpu_times and i < len(self._prev_cpu_times) and len(self._prev_cpu_times[i]) >= 4:
                    prev_idle = self._prev_cpu_times[i][3]
                core_delta = sum(core) - (sum(self._prev_cpu_times[i]) if i < len(self._prev_cpu_times) else 0)
                if core_delta > 0:
                    usage = 100.0 * (1.0 - (idle - prev_idle) / core_delta)
                else:
                    usage = 0.0
                self.cpu_per_core.append({
                    'core': i,
                    'percent': max(0.0, min(100.0, usage))
                })
        else:
            for i, core in enumerate(current_core_data):
                self.cpu_per_core.append({'core': i, 'percent': 0.0})

        # Compute total CPU usage percentage
        if self._prev_cpu_times is not None and len(current_core_data) > 0:
            # Sum idle across all cores
            total_idle = 0
            total_prev_idle = 0
            total_all = 0
            total_prev_all = 0
            for i, core in enumerate(current_core_data):
                total_all += sum(core)
                if len(core) >= 4:
                    total_idle += core[3]
                if self._prev_cpu_times and i < len(self._prev_cpu_times):
                    total_prev_all += sum(self._prev_cpu_times[i])
                    if len(self._prev_cpu_times[i]) >= 4:
                        total_prev_idle += self._prev_cpu_times[i][3]
            delta_all = total_all - total_prev_all
            delta_idle = total_idle - total_prev_idle
            if delta_all > 0:
                self.cpu_total = max(0.0, min(100.0, 100.0 * (1.0 - delta_idle / delta_all)))
            else:
                self.cpu_total = 0.0
        else:
            self.cpu_total = 0.0

        self._cpu_history.append(self.cpu_total)
        self._prev_cpu_times = current_core_data
        self._prev_total_time = total_time

    # ------------------------------------------------------------------
    # Memory  (/proc/meminfo)
    # ------------------------------------------------------------------
    def _update_memory(self) -> None:
        content = _read_file('/proc/meminfo')
        if not content:
            self.memory = {}
            return

        mem = {}
        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0].rstrip(':')
            try:
                val = int(parts[1])
            except ValueError:
                continue
            mem[key] = val  # keep in kB

        total = mem.get('MemTotal', 0)
        free = mem.get('MemFree', 0)
        available = mem.get('MemAvailable', 0)
        buffers = mem.get('Buffers', 0)
        cached = mem.get('Cached', 0) + mem.get('SReclaimable', 0)
        used = total - free - buffers - cached
        # convert to bytes for display
        kb = 1024
        self.memory = {
            'total': total * kb,
            'free': free * kb,
            'available': available * kb,
            'buffers': buffers * kb,
            'cached': cached * kb,
            'used': used * kb,
            'percent': (used / total * 100.0) if total > 0 else 0.0,
        }

    def _update_swap(self) -> None:
        content = _read_file('/proc/meminfo')
        if not content:
            self.swap = {}
            return

        mem = {}
        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) < 2:
                continue
            key = parts[0].rstrip(':')
            try:
                val = int(parts[1])
            except ValueError:
                continue
            mem[key] = val

        total = mem.get('SwapTotal', 0)
        free = mem.get('SwapFree', 0)
        used = total - free
        kb = 1024
        self.swap = {
            'total': total * kb,
            'free': free * kb,
            'used': used * kb,
            'percent': (used / total * 100.0) if total > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Uptime  (/proc/uptime)
    # ------------------------------------------------------------------
    def _update_uptime(self) -> None:
        content = _read_file('/proc/uptime')
        if not content:
            self.uptime_seconds = 0.0
            return
        try:
            self.uptime_seconds = float(content.split()[0])
        except (ValueError, IndexError):
            self.uptime_seconds = 0.0

    # ------------------------------------------------------------------
    # Load average  (/proc/loadavg)
    # ------------------------------------------------------------------
    def _update_loadavg(self) -> None:
        content = _read_file('/proc/loadavg')
        if not content:
            self.loadavg = (0.0, 0.0, 0.0)
            return
        try:
            parts = content.split()
            self.loadavg = (float(parts[0]), float(parts[1]), float(parts[2]))
        except (ValueError, IndexError):
            self.loadavg = (0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Processes  (/proc/[pid]/stat, /proc/[pid]/status)
    # ------------------------------------------------------------------
    def _update_processes(self) -> None:
        tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        now = time.time()
        procs = []

        # Read total CPU jiffies from /proc/stat once
        stat_content = _read_file('/proc/stat')
        total_cpu_jiffies = 0.0
        if stat_content:
            for line in stat_content.split('\n'):
                if line.startswith('cpu '):
                    parts = line.split()
                    total_cpu_jiffies = sum(int(x) for x in parts[1:])
                    break

        for pid_name in os.listdir('/proc'):
            if not pid_name.isdigit():
                continue
            pid = int(pid_name)
            stat_path = f'/proc/{pid}/stat'

            stat_content = _read_file(stat_path)
            if not stat_content:
                continue

            # Parse stat - need to handle comm field which may contain spaces
            # Format: pid (comm) state ppid ...
            try:
                # Split: before first '(', inside '()', after ')'
                pre, rest = stat_content.split('(', 1)
                comm, post = rest.rsplit(')', 1)
                post_parts = post.split()

                state = post_parts[0]
                ppid = int(post_parts[1])
                # fields after ppid: pgrp, session, tty_nr, tpgid, flags, minflt, cminflt,
                # majflt, cmajflt, utime(13-3=10), stime(11), cutime(12), cstime(13)
                utime = int(post_parts[11]) if len(post_parts) > 13 else 0
                stime = int(post_parts[12]) if len(post_parts) > 13 else 0
                # rss is field 23 (index 21 in post_parts after state=0)
                rss_idx = 22 if len(post_parts) > 22 else -1
                rss = int(post_parts[rss_idx]) if rss_idx >= 0 else 0

                proc_jiffies = utime + stime

            except (ValueError, IndexError):
                continue

            # Get user
            user = self._get_process_user(pid)

            # Get VSZ from status (VmSize)
            vsz = self._get_process_vsz(pid)

            # CPU%
            cpu_pct = 0.0
            if self._prev_proc_tick > 0 and pid in self._prev_proc_times:
                prev_jiffies = self._prev_proc_times[pid]
                proc_delta = proc_jiffies - prev_jiffies
                elapsed = now - self._prev_proc_tick
                cpu_total_delta = total_cpu_jiffies - self._prev_proc_total_cpu
                if elapsed > 0 and cpu_total_delta > 0:
                    # Number of CPUs
                    ncpus = os.cpu_count() or 1
                    cpu_pct = 100.0 * (proc_delta / tck) / elapsed / ncpus
                    if cpu_pct > 100.0 * ncpus:
                        cpu_pct = 100.0
                    cpu_pct = max(0.0, min(100.0, cpu_pct))

            # MEM% - rss is in pages (typically 4K)
            page_size = os.sysconf(os.sysconf_names['SC_PAGESIZE'])
            mem_bytes = rss * page_size
            total_mem = self.memory.get('total', 1)
            mem_pct = (mem_bytes / total_mem * 100.0) if total_mem > 0 else 0.0

            procs.append({
                'pid': pid,
                'user': user,
                'cpu': cpu_pct,
                'mem': mem_pct,
                'state': state,
                'command': comm,
                'ppid': ppid,
                'jiffies': proc_jiffies,
            })

        # Save for next tick
        self._prev_proc_tick = now
        self._prev_proc_total_cpu = total_cpu_jiffies
        self._prev_proc_times = {p['pid']: p['jiffies'] for p in procs}

        self.processes = procs

    def _get_process_user(self, pid: int) -> str:
        """Get the username for a given PID."""
        status_path = f'/proc/{pid}/status'
        content = _read_file(status_path)
        if content:
            for line in content.split('\n'):
                if line.startswith('Uid:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        uid = int(parts[1])
                        try:
                            import pwd
                            return pwd.getpwuid(uid).pw_name
                        except (KeyError, ImportError):
                            return str(uid)
                    break
        return '?'

    def _get_process_vsz(self, pid: int) -> int:
        """Get VmSize in kB from /proc/[pid]/status."""
        status_path = f'/proc/{pid}/status'
        content = _read_file(status_path)
        if content:
            for line in content.split('\n'):
                if line.startswith('VmSize:'):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            return int(parts[1])
                        except ValueError:
                            return 0
        return 0

    # ------------------------------------------------------------------
    # Network I/O  (/proc/net/dev)
    # ------------------------------------------------------------------
    def _update_network(self) -> None:
        content = _read_file('/proc/net/dev')
        if not content:
            self.network = []
            return

        now = time.time()
        current: Dict[str, Tuple[int, int]] = {}

        for line in content.strip().split('\n')[2:]:  # skip headers
            if ':' not in line:
                continue
            iface, rest = line.split(':', 1)
            iface = iface.strip()
            parts = rest.split()
            if len(parts) < 10:
                continue
            try:
                rx = int(parts[0])
                tx = int(parts[8])
            except (ValueError, IndexError):
                continue
            current[iface] = (rx, tx)

        result = []
        for iface, (rx, tx) in current.items():
            if iface == 'lo':
                continue  # skip loopback
            rx_rate = 0.0
            tx_rate = 0.0
            if self._prev_net_time > 0 and iface in self._prev_net_data:
                prev_rx, prev_tx = self._prev_net_data[iface]
                elapsed = now - self._prev_net_time
                if elapsed > 0:
                    rx_rate = max(0, (rx - prev_rx) / elapsed)
                    tx_rate = max(0, (tx - prev_tx) / elapsed)
            result.append({
                'interface': iface,
                'rx_rate': rx_rate,
                'tx_rate': tx_rate,
            })

        result.sort(key=lambda x: x['interface'])
        self.network = result
        self._prev_net_time = now
        self._prev_net_data = current

    # ------------------------------------------------------------------
    # TCP connections  (/proc/net/tcp)
    # ------------------------------------------------------------------
    def _update_tcp(self) -> None:
        content = _read_file('/proc/net/tcp')
        if not content:
            self.tcp_counts = {}
            return

        # State map (hex -> name)
        states = {
            '00': 'UNKNOWN', '01': 'ESTABLISHED', '02': 'SYN_SENT',
            '03': 'SYN_RECV', '04': 'FIN_WAIT1', '05': 'FIN_WAIT2',
            '06': 'TIME_WAIT', '07': 'CLOSE', '08': 'CLOSE_WAIT',
            '09': 'LAST_ACK', '0A': 'LISTEN', '0B': 'CLOSING',
        }

        counts: Dict[str, int] = {}
        for line in content.strip().split('\n')[1:]:  # skip header
            parts = line.split()
            if len(parts) < 4:
                continue
            st = parts[3]  # state hex
            state_name = states.get(st, st)
            counts[state_name] = counts.get(state_name, 0) + 1

        self.tcp_counts = counts

    # ------------------------------------------------------------------
    # Disk Usage  (/proc/mounts + statvfs)
    # ------------------------------------------------------------------
    VIRTUAL_FS = {
        'proc', 'sysfs', 'devtmpfs', 'tmpfs', 'devpts', 'cgroup',
        'cgroup2', 'debugfs', 'tracefs', 'securityfs', 'pstore',
        'configfs', 'fusectl', 'hugetlbfs', 'mqueue', 'bpf',
        'ramfs', 'overlay', 'binfmt_misc', 'rpc_pipefs',
        'nfsd', 'autofs', 'efivarfs',
    }

    def _update_disk_usage(self) -> None:
        content = _read_file('/proc/mounts')
        if not content:
            self.disk_usage = []
            return

        result = []
        seen = set()
        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) < 3:
                continue
            device, mount_point, fs_type = parts[0], parts[1], parts[2]

            # Filter virtual filesystems
            if any(virt in device or virt in fs_type.lower() or
                   fs_type.lower() in self.VIRTUAL_FS or
                   device in self.VIRTUAL_FS
                   for virt in self.VIRTUAL_FS):
                # But still try real block devices (e.g. /dev/sda1)
                if not device.startswith('/dev/'):
                    continue

            if device.startswith('/dev/loop'):
                continue
            if mount_point in seen:
                continue
            seen.add(mount_point)

            try:
                st = os.statvfs(mount_point)
            except (OSError, PermissionError):
                continue

            total = st.f_frsize * st.f_blocks
            free = st.f_frsize * st.f_bavail
            used = total - free
            pct = (used / total * 100.0) if total > 0 else 0.0

            result.append({
                'filesystem': mount_point,
                'device': device,
                'total': total,
                'used': used,
                'free': free,
                'percent': pct,
            })

        result.sort(key=lambda x: x['filesystem'])
        self.disk_usage = result

    # ------------------------------------------------------------------
    # Disk I/O  (/proc/diskstats)
    # ------------------------------------------------------------------
    def _update_disk_io(self) -> None:
        content = _read_file('/proc/diskstats')
        if not content:
            self.disk_io = []
            return

        now = time.time()
        current: Dict[str, Tuple[int, int]] = {}

        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) < 14:
                continue
            dev = parts[2]
            # Skip partitions (they have numbers after the base name)
            # Keep only whole-disk devices
            # Read sectors: field 5 (reads), field 9 (writes) - 1-indexed
            # Fields: 0=major, 1=minor, 2=name, 3=reads_ok, 4=reads_merged,
            #         5=read_sectors, 6=read_ms, 7=writes_ok, 8=writes_merged,
            #         9=write_sectors, 10=write_ms, 11=io_in_progress,
            #         12=io_ms, 13=weighted_io_ms
            try:
                read_sectors = int(parts[5])
                write_sectors = int(parts[9])
            except (ValueError, IndexError):
                continue

            # Filter out partitions: if dev ends with a digit and we see the base device
            # actually just keep all entries that look like whole disks
            current[dev] = (read_sectors, write_sectors)

        result = []
        for dev, (rd, wr) in current.items():
            rd_rate = 0.0
            wr_rate = 0.0
            if self._prev_disk_time > 0 and dev in self._prev_disk_data:
                prev_rd, prev_wr = self._prev_disk_data[dev]
                elapsed = now - self._prev_disk_time
                if elapsed > 0:
                    rd_rate = max(0, (rd - prev_rd) * 512 / elapsed)
                    wr_rate = max(0, (wr - prev_wr) * 512 / elapsed)
            result.append({
                'device': dev,
                'read_rate': rd_rate,
                'write_rate': wr_rate,
            })

        result.sort(key=lambda x: x['device'])
        self.disk_io = result
        self._prev_disk_time = now
        self._prev_disk_data = current

    # ------------------------------------------------------------------
    # Battery  (/sys/class/power_supply/BAT0)
    # ------------------------------------------------------------------
    def _update_battery(self) -> None:
        bat_path = '/sys/class/power_supply/BAT0'
        if not os.path.isdir(bat_path):
            # Try BAT1
            bat_path = '/sys/class/power_supply/BAT1'
            if not os.path.isdir(bat_path):
                self.battery = None
                return

        def _read_bat_file(name: str) -> Optional[str]:
            return _read_file(os.path.join(bat_path, name))

        capacity_str = _read_bat_file('capacity')
        status_str = _read_bat_file('status')
        energy_now_str = _read_bat_file('energy_now') or _read_bat_file('charge_now')
        power_now_str = _read_bat_file('power_now') or _read_bat_file('current_now')

        capacity = int(capacity_str.strip()) if capacity_str else None
        status = status_str.strip() if status_str else 'Unknown'

        bat = {
            'present': True,
            'capacity': capacity,
            'status': status,
            'time_remaining': None,
        }

        if energy_now_str and power_now_str:
            try:
                energy_now = float(energy_now_str)
                power_now = float(power_now_str)
                if power_now > 0:
                    if status == 'Discharging':
                        bat['time_remaining'] = energy_now / power_now  # hours
                    elif status == 'Charging':
                        bat['time_remaining'] = (100.0 - (capacity or 0)) / 100.0 * energy_now / power_now
            except (ValueError, ZeroDivisionError):
                pass

        self.battery = bat
