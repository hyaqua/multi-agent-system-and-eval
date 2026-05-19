"""Disk data collector from /proc/diskstats and /proc/mounts."""

import os
import time
from ..utils import safe_read, safe_readlines, safe_int, safe_float


class DiskCollector:
    """Collects disk usage and I/O statistics."""

    def __init__(self):
        self._prev_io = {}  # device -> (read_sectors, write_sectors, timestamp)
        self._prev_time = None
        self._sector_size = 512  # Standard sector size

    def get_mounts(self):
        """Get mounted filesystems from /proc/mounts.
        Returns list of (device, mountpoint, fstype)."""
        mounts = []
        content = safe_read("/proc/mounts")
        if not content:
            return mounts

        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                device = parts[0]
                mountpoint = parts[1]
                fstype = parts[2]
                # Filter out pseudo filesystems
                if fstype in ('proc', 'sysfs', 'devtmpfs', 'devpts', 'tmpfs',
                              'cgroup', 'cgroup2', 'pstore', 'bpf', 'fuse.gvfsd-fuse',
                              'securityfs', 'debugfs', 'tracefs', 'hugetlbfs',
                              'mqueue', 'configfs', 'fusectl'):
                    continue
                # Filter some common small filesystems
                if mountpoint.startswith('/proc') or mountpoint.startswith('/sys'):
                    continue
                if mountpoint.startswith('/snap/'):
                    continue

                mounts.append((device, mountpoint, fstype))

        return mounts

    def get_usage(self, mountpoint):
        """Get disk usage for a mountpoint using os.statvfs.
        Returns dict with total, used, free, percent in bytes."""
        try:
            st = os.statvfs(mountpoint)
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - (st.f_bfree * st.f_frsize)
            if total > 0:
                percent = (used / total) * 100.0
            else:
                percent = 0.0
            return {
                'total': total,
                'used': used,
                'free': free,
                'percent': percent,
            }
        except (PermissionError, FileNotFoundError, OSError):
            return {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0.0,
            }

    def get_all_usage(self):
        """Get disk usage for all mounted filesystems."""
        mounts = self.get_mounts()
        results = []
        seen = set()
        for device, mountpoint, fstype in mounts:
            if mountpoint in seen:
                continue
            seen.add(mountpoint)
            usage = self.get_usage(mountpoint)
            # Only include filesystems with actual data
            if usage['total'] > 0:
                results.append({
                    'device': device,
                    'mountpoint': mountpoint,
                    'fstype': fstype,
                    **usage,
                })
        return results

    def get_io_stats(self):
        """Get disk I/O stats from /proc/diskstats.
        Returns dict of device -> {read_rate, write_rate, ...} in bytes/sec."""
        content = safe_read("/proc/diskstats")
        if not content:
            return {}

        now = time.time()
        result = {}
        current_io = {}
        seen_devices = set()

        for line in content.strip().split('\n'):
            parts = line.split()
            if len(parts) < 14:
                continue

            # Format: major minor name rio rmerge rsect ruse wio wmerge wsect wuse ...
            device = parts[2]
            # Skip partitions (contain digits after device name)
            # Skip loop devices, ram devices
            if any(device.startswith(p) for p in ('loop', 'ram', 'dm-')):
                continue
            # Simple check: if there's a digit in position after common prefix, it might be a partition
            # Better: check /sys/block/<device>
            if not os.path.exists(f"/sys/block/{device}"):
                continue

            read_sectors = safe_int(parts[5])
            write_sectors = safe_int(parts[9])

            current_io[device] = (read_sectors, write_sectors)
            seen_devices.add(device)

            read_rate = 0.0
            write_rate = 0.0

            if device in self._prev_io and self._prev_time:
                prev_read, prev_write, prev_ts = self._prev_io[device]
                dt = now - prev_ts
                if dt > 0:
                    read_rate = (read_sectors - prev_read) * self._sector_size / dt
                    write_rate = (write_sectors - prev_write) * self._sector_size / dt

            result[device] = {
                'read_rate': max(0, read_rate),
                'write_rate': max(0, write_rate),
                'read_sectors': read_sectors,
                'write_sectors': write_sectors,
            }

        # Remove stale devices from prev_io
        self._prev_io = {
            dev: (rs, ws, now)
            for dev, (rs, ws) in current_io.items()
        }
        # Keep old ones that might momentarily disappear
        for dev, (rs, ws, ts) in self._prev_io.items():
            if dev not in current_io:
                self._prev_io[dev] = (rs, ws, ts)  # Keep as-is

        self._prev_time = now
        return result
