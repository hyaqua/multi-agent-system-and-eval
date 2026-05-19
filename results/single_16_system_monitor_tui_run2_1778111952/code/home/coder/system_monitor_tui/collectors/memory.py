"""Memory data collector from /proc/meminfo."""

from ..utils import safe_read, safe_int


class MemoryCollector:
    """Collects memory statistics from /proc/meminfo."""

    def __init__(self):
        self.meminfo = {}

    def update(self):
        """Parse /proc/meminfo and return a dict of memory values in KB."""
        content = safe_read("/proc/meminfo")
        if not content:
            self.meminfo = {}
            return self.meminfo

        meminfo = {}
        for line in content.strip().split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().split()[0]  # Get the number, drop "kB"
                meminfo[key] = safe_int(val)

        self.meminfo = meminfo
        return self.meminfo

    def get_summary(self):
        """Return a dict with computed memory summary in KB."""
        m = self.meminfo
        if not m:
            return {
                'total': 0, 'used': 0, 'free': 0,
                'available': 0, 'cached': 0, 'buffers': 0
            }

        total = m.get('MemTotal', 0)
        free = m.get('MemFree', 0)
        available = m.get('MemAvailable', 0)
        buffers = m.get('Buffers', 0)
        cached = m.get('Cached', 0) + m.get('SReclaimable', 0)

        # Used = total - free - buffers - cached (approximation used by htop)
        # But 'available' is a better metric when available
        if available > 0:
            used = total - available
        else:
            used = total - free - buffers - cached

        return {
            'total': total,
            'used': max(0, used),
            'free': free,
            'available': available if available > 0 else (total - used),
            'cached': cached,
            'buffers': buffers
        }

    def get_swap(self):
        """Return swap totals in KB."""
        m = self.meminfo
        total = m.get('SwapTotal', 0)
        free = m.get('SwapFree', 0)
        used = total - free
        return {
            'total': total,
            'used': used,
            'free': free
        }
