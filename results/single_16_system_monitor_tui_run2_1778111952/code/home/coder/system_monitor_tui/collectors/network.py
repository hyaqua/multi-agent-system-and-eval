"""Network data collector from /proc/net/dev and /proc/net/tcp."""

import time
from ..utils import safe_read, safe_readlines, safe_int


class NetworkCollector:
    """Collects network I/O statistics per interface."""

    def __init__(self):
        self._prev_bytes = {}   # interface -> (rx, tx, timestamp)
        self._prev_time = None
        self.interfaces = {}

    def update(self):
        """Update network stats. Returns dict of interface -> {rx_rate, tx_rate, rx_total, tx_total}."""
        content = safe_read("/proc/net/dev")
        if not content:
            return {}

        now = time.time()
        result = {}
        current_bytes = {}

        for line in content.strip().split('\n')[2:]:  # Skip headers
            if ':' not in line:
                continue
            iface, stats = line.split(':', 1)
            iface = iface.strip()
            parts = stats.split()
            if len(parts) < 10:
                continue

            rx_bytes = safe_int(parts[0])
            tx_bytes = safe_int(parts[8])
            current_bytes[iface] = (rx_bytes, tx_bytes)

            rx_rate = 0.0
            tx_rate = 0.0

            if iface in self._prev_bytes and self._prev_time:
                prev_rx, prev_tx, prev_ts = self._prev_bytes[iface]
                dt = now - prev_ts
                if dt > 0:
                    rx_rate = (rx_bytes - prev_rx) / dt
                    tx_rate = (tx_bytes - prev_tx) / dt
                else:
                    rx_rate = 0
                    tx_rate = 0

            result[iface] = {
                'rx_rate': max(0, rx_rate),  # bytes per second
                'tx_rate': max(0, tx_rate),
                'rx_total': rx_bytes,
                'tx_total': tx_bytes,
            }

        self._prev_bytes = {
            iface: (rx, tx, now)
            for iface, (rx, tx) in current_bytes.items()
        }
        self._prev_time = now
        self.interfaces = result
        return result

    def get_connection_counts(self):
        """Parse /proc/net/tcp and return counts by connection state."""
        states = {
            'ESTABLISHED': 0,
            'SYN_SENT': 0,
            'SYN_RECV': 0,
            'FIN_WAIT1': 0,
            'FIN_WAIT2': 0,
            'TIME_WAIT': 0,
            'CLOSE': 0,
            'CLOSE_WAIT': 0,
            'LAST_ACK': 0,
            'LISTEN': 0,
            'CLOSING': 0,
        }

        state_map = {
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

        for proto_file in ['/proc/net/tcp', '/proc/net/tcp6']:
            content = safe_read(proto_file)
            if not content:
                continue
            lines = content.strip().split('\n')[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) < 4:
                    continue
                # State is the 4th field (index 3)
                st_hex = parts[3]
                state_name = state_map.get(st_hex, 'UNKNOWN')
                states[state_name] = states.get(state_name, 0) + 1

        return states
