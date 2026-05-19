"""Network view: network I/O and connections."""

import curses
from ..utils import human_readable_bytes


class NetworkView:
    """Renders the network monitoring view."""

    def draw(self, stdscr, top, height, width, ui):
        """Draw network view."""
        try:
            y = top
            net_data = ui.net_data  # Use cached data

            # Title
            stdscr.addstr(y, 1, "Network Interfaces - Bytes/sec", curses.A_BOLD | curses.color_pair(4))
            y += 1

            # Column headers
            header = f" {'Interface':<15} {'RX Rate':>14} {'TX Rate':>14} {'RX Total':>14} {'TX Total':>14}"
            stdscr.addstr(y, 0, header[:width], curses.color_pair(6))
            y += 1

            # Filter only interfaces with activity or common ones
            active_ifaces = []
            for iface, data in net_data.items():
                if iface == 'lo':
                    continue
                if data['rx_rate'] > 0 or data['tx_rate'] > 0 or data['rx_total'] > 0:
                    active_ifaces.append((iface, data))

            # Sort by total activity
            active_ifaces.sort(key=lambda x: x[1]['rx_rate'] + x[1]['tx_rate'], reverse=True)

            # Show loopback at end
            if 'lo' in net_data:
                active_ifaces.append(('lo', net_data['lo']))

            for iface, data in active_ifaces:
                if y >= top + height - 3:
                    break
                rx_rate = human_readable_bytes(data['rx_rate']) + "/s"
                tx_rate = human_readable_bytes(data['tx_rate']) + "/s"
                rx_total = human_readable_bytes(data['rx_total'])
                tx_total = human_readable_bytes(data['tx_total'])

                line = f" {iface:<15} {rx_rate:>14} {tx_rate:>14} {rx_total:>14} {tx_total:>14}"
                stdscr.addstr(y, 0, line[:width])
                y += 1

            # Connection counts section
            y += 1
            if y < top + height - 5:
                self._draw_connections(stdscr, y, width, ui)

        except curses.error:
            pass

    def _draw_connections(self, stdscr, y, width, ui):
        """Draw TCP connection summary."""
        try:
            stdscr.addstr(y, 1, "TCP Connection States", curses.A_BOLD | curses.color_pair(4))
            y += 1

            conn_counts = ui.conn_counts  # Use cached data

            col_width = 22
            cols = max(1, width // col_width)

            items = []
            for state in ['ESTABLISHED', 'LISTEN', 'TIME_WAIT', 'CLOSE_WAIT',
                          'SYN_SENT', 'SYN_RECV', 'FIN_WAIT1', 'FIN_WAIT2',
                          'LAST_ACK', 'CLOSING', 'CLOSE']:
                count = conn_counts.get(state, 0)
                if count > 0:
                    items.append(f"  {state}: {count}")

            if not items:
                stdscr.addstr(y, 1, "  No active TCP connections")
                return

            for i, item in enumerate(items):
                col = i % cols
                row = y + i // cols
                x = col * col_width
                try:
                    if x < width:
                        stdscr.addstr(row, x, item[:col_width - 1])
                except curses.error:
                    pass

        except curses.error:
            pass
