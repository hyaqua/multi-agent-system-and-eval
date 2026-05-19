"""Data collector - reads from /proc and /sys, returns snapshots."""

import os
import time
import struct


def _read_file(path):
    """Read a file and return its contents as a string, or empty string on failure."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except (IOError, OSError, PermissionError):
        return ''


def _read_file_lines(path):
    """Read a file and return lines, or empty list on failure."""
    try:
        with open(path, 'r') as f:
            return f.readlines()
    except (IOError, OSError, PermissionError):
        return []


class Collector:
    """Collects system statistics from /proc and /sys."""

    def __init__(self):
        # CPU tracking
        self._prev_cpu_times = None  # dict: 'cpuN' -> list of fields
        self._prev_cpu_total = None
        self._prev_proc_times = {}   # pid -> (utime, stime, cutime, cstime, timestamp)

        # Network tracking
        self._prev_net = {}  # interface -> (rx_bytes, tx_bytes, timestamp)

        # Disk I/O tracking
        self._prev_disk = {}  # device -> (reads, writes, timestamp)

        # Total RAM for process MEM%
        self._total_ram = self._get_total_ram()

    # ---------- CPU ----------

    def _get_total_ram(self):
        """Get total RAM in bytes."""
        meminfo = _read_file('/proc/meminfo')
        for line in meminfo.split('\n'):
            if line.startswith('MemTotal:'):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) * 1024
        return 1  # avoid division by zero

    def get_cpu_percent(self, interval):
        """
        Returns per-core CPU usage as percentages.
        First call returns zeros; subsequent calls compute deltas.
        Returns list of floats: [total, core0, core1, ...]
        """
        content = _read_file('/proc/stat')
        if not content:
            return [0.0]

        current = {}
        for line in content.split('\n'):
            if line.startswith('cpu'):
                parts = line.split()
                name = parts[0]
                fields = [int(x) for x in parts[1:]]
                current[name] = fields

        if self._prev_cpu_times is None:
            self._prev_cpu_times = current
            return [0.0] * len(current)

        result = []
        for name in sorted(current.keys(), key=lambda x: (x != 'cpu', x)):
            if name not in self._prev_cpu_times:
                result.append(0.0)
                continue
            prev_fields = self._prev_cpu_times[name]
            curr_fields = current[name]

            prev_total = sum(prev_fields)
            curr_total = sum(curr_fields)
            prev_idle = prev_fields[3] + (prev_fields[4] if len(prev_fields) > 4 else 0)
            curr_idle = curr_fields[3] + (curr_fields[4] if len(curr_fields) > 4 else 0)

            total_delta = curr_total - prev_total
            idle_delta = curr_idle - prev_idle

            if total_delta > 0:
                usage = (total_delta - idle_delta) / total_delta * 100.0
            else:
                usage = 0.0
            result.append(round(usage, 1))

        self._prev_cpu_times = current
        return result

    def get_cpu_raw(self):
        """Return raw CPU times for process CPU% calculation."""
        content = _read_file('/proc/stat')
        if not content:
            return None
        for line in content.split('\n'):
            if line.startswith('cpu '):
                parts = line.split()
                return [int(x) for x in parts[1:]]
        return None

    # ---------- Memory ----------

    def get_memory(self):
        """Returns dict with RAM and swap info in bytes."""
        meminfo = _read_file('/proc/meminfo')
        result = {
            'mem_total': 0,
            'mem_free': 0,
            'mem_available': 0,
            'cached': 0,
            'buffers': 0,
            'swap_total': 0,
            'swap_free': 0,
        }
        mapping = {
            'MemTotal:': 'mem_total',
            'MemFree:': 'mem_free',
            'MemAvailable:': 'mem_available',
            'Cached:': 'cached',
            'Buffers:': 'buffers',
            'SwapTotal:': 'swap_total',
            'SwapFree:': 'swap_free',
        }
        for line in meminfo.split('\n'):
            for key, field in mapping.items():
                if line.startswith(key):
                    parts = line.split()
                    if len(parts) >= 2:
                        result[field] = int(parts[1]) * 1024
        return result

    # ---------- Uptime ----------

    def get_uptime(self):
        """Returns uptime in seconds as float."""
        content = _read_file('/proc/uptime')
        if content:
            parts = content.split()
            if parts:
                return float(parts[0])
        return 0.0

    # ---------- Load Average ----------

    def get_loadavg(self):
        """Returns (load1, load5, load15) as floats."""
        content = _read_file('/proc/loadavg')
        if content:
            parts = content.split()
            if len(parts) >= 3:
                return (float(parts[0]), float(parts[1]), float(parts[2]))
        return (0.0, 0.0, 0.0)

    # ---------- Network ----------

    def get_network_io(self, interval):
        """
        Returns list of dicts per interface:
        {name, rx_bytes_total, tx_bytes_total, rx_speed, tx_speed}
        """
        content = _read_file('/proc/net/dev')
        if not content:
            return []

        lines = content.split('\n')
        now = time.time()
        result = []

        for line in lines[2:]:  # skip headers
            if ':' not in line:
                continue
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[0].rstrip(':')
            rx_bytes = int(parts[1])
            tx_bytes = int(parts[9])

            rx_speed = 0.0
            tx_speed = 0.0
            if name in self._prev_net:
                prev_rx, prev_tx, prev_time = self._prev_net[name]
                dt = now - prev_time
                if dt > 0:
                    rx_speed = (rx_bytes - prev_rx) / dt
                    tx_speed = (tx_bytes - prev_tx) / dt

            self._prev_net[name] = (rx_bytes, tx_bytes, now)
            result.append({
                'name': name,
                'rx_bytes': rx_bytes,
                'tx_bytes': tx_bytes,
                'rx_speed': rx_speed,
                'tx_speed': tx_speed,
            })

        return result

    # ---------- TCP Connections ----------

    def get_tcp_connections(self):
        """
        Returns dict of state -> count.
        States: ESTABLISHED, SYN_SENT, SYN_RECV, FIN_WAIT1, FIN_WAIT2,
                TIME_WAIT, CLOSE, CLOSE_WAIT, LAST_ACK, LISTEN, CLOSING
        """
        state_names = {
            '01': 'ESTABLISHED',
            '02': 'SYN_SENT',
            '03': 'SYN_RECV',
            '04': 'FIN_WAIT1',
            '05': 'FIN_WAIT2',
            '06': 'TIME_WAIT',
            '07': 'CLOSE',
            '08': 'CLOSE_WAIT',
            '09': 'LAST_ACK',
            '0A': 'LISTEN',
            '0B': 'CLOSING',
        }
        counts = {v: 0 for v in state_names.values()}

        for proto in ['/proc/net/tcp', '/proc/net/tcp6']:
            content = _read_file(proto)
            if not content:
                continue
            lines = content.split('\n')[1:]  # skip header
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                state_hex = parts[3]
                state_name = state_names.get(state_hex, 'UNKNOWN')
                if state_name not in counts:
                    counts[state_name] = 0
                counts[state_name] += 1

        return counts

    # ---------- Disk ----------

    def get_disk_usage(self):
        """
        Returns list of dicts: {device, mountpoint, fstype, total, used, free, percent}
        """
        mounts = _read_file_lines('/proc/mounts')
        if not mounts:
            # fallback
            mounts = _read_file_lines('/proc/self/mountinfo')
        result = []
        seen = set()

        # Real filesystem types to include
        real_fs = {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'zfs', 'ntfs',
                    'ntfs3', 'vfat', 'fat32', 'fat16', 'fuse', 'fuseblk',
                    'hfs', 'hfsplus', 'apfs', 'tmpfs', 'overlay'}

        for line in mounts:
            parts = line.split()
            if len(parts) < 6:
                continue
            device = parts[0]
            mountpoint = parts[1]
            fstype = parts[2]

            # Skip pseudo filesystems
            if fstype not in real_fs and not fstype.startswith('fuse'):
                continue
            if mountpoint in seen:
                continue
            seen.add(mountpoint)

            try:
                st = os.statvfs(mountpoint)
                total = st.f_frsize * st.f_blocks
                free = st.f_frsize * st.f_bavail
                used = total - st.f_frsize * st.f_bfree
                if total > 0:
                    percent = (used / total) * 100.0
                else:
                    percent = 0.0

                result.append({
                    'device': device,
                    'mountpoint': mountpoint,
                    'fstype': fstype,
                    'total': total,
                    'used': used,
                    'free': free,
                    'percent': percent,
                })
            except (OSError, PermissionError):
                continue

        return result

    def get_disk_io(self, interval):
        """
        Returns list of dicts: {device, read_speed, write_speed}
        Speeds in bytes/s based on delta.
        """
        content = _read_file('/proc/diskstats')
        if not content:
            return []

        now = time.time()
        result = []
        lines = content.split('\n')

        for line in lines:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 14:
                continue
            # fields: major minor name reads reads_merged sectors_read ms_read
            #         writes writes_merged sectors_written ms_write ...
            device = parts[2]
            # Only include real block devices (sd*, nvme*, hd*, vd*, xvd*, mmcblk*)
            if not any(device.startswith(p) for p in ('sd', 'nvme', 'hd', 'vd', 'xvd', 'mmcblk')):
                continue
            # skip partitions
            # sdX: sd[a-z]+ is disk, sd[a-z]+[0-9]+ is partition
            # nvmeXnY: nvme[0-9]+n[0-9]+ is disk, nvme[0-9]+n[0-9]+p[0-9]+ is partition
            if any(device.startswith(p) for p in ('sd', 'hd', 'vd', 'xvd')):
                # disk: e.g. sda, sdb; partition: sda1, sdb2
                if device[-1].isdigit():
                    # But 'sd' + digit could be like 'sda' - check if after prefix there are non-digits
                    base = device.rstrip('0123456789')
                    if base != device:
                        continue
            elif device.startswith('nvme'):
                # nvme0n1 = disk, nvme0n1p1 = partition
                if 'p' in device:
                    continue
            elif device.startswith('mmcblk'):
                # mmcblk0 = disk, mmcblk0p1 = partition
                if 'p' in device:
                    continue

            sectors_read = int(parts[5])
            sectors_written = int(parts[9])

            read_speed = 0.0
            write_speed = 0.0
            if device in self._prev_disk:
                prev_read, prev_write, prev_time = self._prev_disk[device]
                dt = now - prev_time
                if dt > 0:
                    read_speed = ((sectors_read - prev_read) * 512) / dt
                    write_speed = ((sectors_written - prev_write) * 512) / dt

            self._prev_disk[device] = (sectors_read, sectors_written, now)
            result.append({
                'device': device,
                'read_speed': read_speed,
                'write_speed': write_speed,
            })

        return result

    # ---------- Battery ----------

    def get_battery(self):
        """
        Returns dict: {present, percentage, status, time_remaining_sec, has_battery}
        or None if no battery found.
        """
        base = '/sys/class/power_supply'
        if not os.path.exists(base):
            return None

        # Find battery device
        for entry in os.listdir(base):
            if entry.startswith('BAT'):
                bat_path = os.path.join(base, entry)
                capacity = _read_file(os.path.join(bat_path, 'capacity')).strip()
                status = _read_file(os.path.join(bat_path, 'status')).strip()
                energy_now = _read_file(os.path.join(bat_path, 'energy_now')).strip()
                energy_full = _read_file(os.path.join(bat_path, 'energy_full')).strip()
                power_now = _read_file(os.path.join(bat_path, 'power_now')).strip()

                result = {
                    'present': True,
                    'has_battery': True,
                    'percentage': 0,
                    'status': status or 'Unknown',
                    'time_remaining_sec': -1,
                }

                if capacity:
                    result['percentage'] = int(capacity)

                # Calculate remaining time if discharging
                if status and status.lower() == 'discharging':
                    if power_now and energy_now:
                        try:
                            power = float(power_now) / 1_000_000  # microwatts to watts
                            energy = float(energy_now) / 1_000_000  # microwatt-hours to watt-hours
                            if power > 0:
                                result['time_remaining_sec'] = (energy / power) * 3600
                        except (ValueError, ZeroDivisionError):
                            pass
                    elif energy_now and energy_full:
                        # Fallback: no power_now, can't estimate time
                        pass

                return result

        return None

    def update_total_ram(self):
        """Refresh total RAM (in case it changed, unlikely)."""
        self._total_ram = self._get_total_ram()
