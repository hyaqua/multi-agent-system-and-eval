"""Battery data collector from /sys/class/power_supply."""

import os
from ..utils import safe_read, safe_int, safe_float


class BatteryCollector:
    """Collects battery status information."""

    def __init__(self):
        self.battery_path = None
        self._find_battery()

    def _find_battery(self):
        """Find the first battery in /sys/class/power_supply."""
        base = "/sys/class/power_supply"
        if not os.path.exists(base):
            return
        try:
            for entry in os.listdir(base):
                if entry.startswith('BAT'):
                    self.battery_path = os.path.join(base, entry)
                    break
        except (PermissionError, FileNotFoundError):
            pass

    def update(self):
        """Update battery status. Returns dict with battery info or None."""
        if not self.battery_path:
            return None

        def read_val(name):
            path = os.path.join(self.battery_path, name)
            content = safe_read(path).strip()
            return content

        try:
            # Capacity / percentage
            capacity = safe_int(read_val("capacity"), -1)
            if capacity < 0:
                return None

            status = read_val("status") or "Unknown"

            # Energy values (in µWh or µAh depending on system)
            energy_now = safe_float(read_val("energy_now"), 0)
            energy_full = safe_float(read_val("energy_full"), 0)
            power_now = safe_float(read_val("power_now"), 0)

            # Also try charge-based (in µAh)
            if energy_now == 0:
                energy_now = safe_float(read_val("charge_now"), 0)
            if energy_full == 0:
                energy_full = safe_float(read_val("charge_full"), 0)
            if power_now == 0:
                power_now = safe_float(read_val("current_now"), 0)

            # Calculate time remaining
            time_remaining = None
            if status == "Discharging" and power_now > 0 and energy_now > 0:
                time_remaining = energy_now / power_now  # hours

            elif status == "Charging" and power_now > 0 and energy_full > energy_now:
                time_remaining = (energy_full - energy_now) / power_now

            result = {
                'percentage': capacity,
                'status': status,
                'time_remaining': time_remaining,
                'energy_now': energy_now,
                'energy_full': energy_full,
                'power_now': power_now,
            }
            return result

        except Exception:
            return None
