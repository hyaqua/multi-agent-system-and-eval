"""System data collector: uptime, loadavg."""

import os
from ..utils import safe_read, safe_readlines, safe_float


class SystemCollector:
    """Collects system uptime and load averages."""

    def __init__(self):
        self.uptime = 0.0
        self.loadavg = [0.0, 0.0, 0.0]
        self.boot_time = None
        self._get_boot_time()

    def _get_boot_time(self):
        """Get boot time from /proc/stat btime."""
        content = safe_read("/proc/stat")
        if content:
            for line in content.split('\n'):
                if line.startswith('btime'):
                    parts = line.split()
                    if len(parts) > 1:
                        self.boot_time = safe_float(parts[1])
                        break

    def update(self):
        """Update uptime and loadavg."""
        # Uptime from /proc/uptime
        content = safe_read("/proc/uptime")
        if content:
            parts = content.split()
            if parts:
                self.uptime = safe_float(parts[0])

        # Load averages from /proc/loadavg
        content = safe_read("/proc/loadavg")
        if content:
            parts = content.split()
            if len(parts) >= 3:
                self.loadavg = [
                    safe_float(parts[0]),
                    safe_float(parts[1]),
                    safe_float(parts[2])
                ]

        return {
            'uptime': self.uptime,
            'loadavg': self.loadavg,
            'boot_time': self.boot_time
        }
