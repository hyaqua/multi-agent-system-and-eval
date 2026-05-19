"""CPU data collector from /proc/stat."""

from ..utils import safe_read, safe_int


class CPUCollector:
    """Collects CPU usage statistics from /proc/stat."""

    def __init__(self):
        self._prev_total = {}
        self._prev_idle = {}
        self._prev_global_total = 0
        self._prev_global_idle = 0
        self._cpu_count = 0
        self._cpu_history = []  # List of overall CPU percentages (last 60)
        self._per_cpu_history = {}  # per-core histories

    def _parse_stat(self):
        """Parse /proc/stat and return cpu data."""
        content = safe_read("/proc/stat")
        if not content:
            return None, {}

        global_total = 0
        global_idle = 0
        per_cpu = {}

        for line in content.strip().split('\n'):
            if not line.startswith('cpu'):
                continue
            parts = line.split()
            name = parts[0]
            if name == 'cpu':  # overall
                values = [safe_int(x) for x in parts[1:]]
                if len(values) >= 4:
                    global_total = sum(values)
                    global_idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
            elif name.startswith('cpu'):  # per-core
                core_name = name
                values = [safe_int(x) for x in parts[1:]]
                if len(values) >= 4:
                    total = sum(values)
                    idle = values[3] + (values[4] if len(values) > 4 else 0)
                    per_cpu[core_name] = (total, idle)

        self._cpu_count = len(per_cpu)
        return (global_total, global_idle), per_cpu

    def update(self):
        """Update CPU usage. Returns (global_pct, per_core_pcts, per_core_histories)."""
        (global_total, global_idle), per_cpu = self._parse_stat()
        if global_total is None:
            return 0.0, {}, self._cpu_history, self._per_cpu_history

        # Calculate global CPU usage
        global_pct = 0.0
        if self._prev_global_total > 0:
            total_diff = global_total - self._prev_global_total
            idle_diff = global_idle - self._prev_global_idle
            if total_diff > 0:
                global_pct = 100.0 * (1.0 - idle_diff / total_diff)

        self._prev_global_total = global_total
        self._prev_global_idle = global_idle

        # Calculate per-core usage
        per_core_pcts = {}
        for core_name, (total, idle) in per_cpu.items():
            pct = 0.0
            if core_name in self._prev_total:
                prev_total = self._prev_total[core_name]
                prev_idle = self._prev_idle[core_name]
                total_diff = total - prev_total
                idle_diff = idle - prev_idle
                if total_diff > 0:
                    pct = 100.0 * (1.0 - idle_diff / total_diff)
            per_core_pcts[core_name] = pct
            self._prev_total[core_name] = total
            self._prev_idle[core_name] = idle

        # Update history (keep last 60 entries for global)
        self._cpu_history.append(global_pct)
        if len(self._cpu_history) > 60:
            self._cpu_history = self._cpu_history[-60:]

        # Update per-core history
        for core_name, pct in per_core_pcts.items():
            if core_name not in self._per_cpu_history:
                self._per_cpu_history[core_name] = []
            self._per_cpu_history[core_name].append(pct)
            if len(self._per_cpu_history[core_name]) > 60:
                self._per_cpu_history[core_name] = self._per_cpu_history[core_name][-60:]

        return global_pct, per_core_pcts, self._cpu_history, self._per_cpu_history

    @property
    def cpu_count(self):
        return self._cpu_count
