"""Curses drawing functions for each view."""

import curses
import math
import time


# Braille dot patterns for CPU history graph
# Each braille character represents 8 dots in a 2x4 grid:
# dot 1: 0x01, dot 2: 0x02, dot 3: 0x04, dot 4: 0x08
# dot 5: 0x10, dot 6: 0x20, dot 7: 0x40, dot 8: 0x80
# We map percentage (0-100) to dots from bottom to top:
# 0-12.5%: dot 4, 12.5-25%: dots 4+8, ... up to all 8 dots for 87.5-100%

BRAILLE_BASE = 0x2800

# Dot mapping for 8 levels (bottom to top)
DOT_MAP = [
    0x00,       # 0%
    0x40,       # dot 7
    0x44,       # dots 7+8
    0x46,       # dots 7+8+3
    0x47,       # dots 7+8+3+4
    0x47 | 0x80,  # + dot 8? Actually let's do proper mapping
]

# Better: map 8 levels to braille dots
# Standard braille dot positions (1-based):
# 1 4
# 2 5
# 3 6
# 7 8
# We fill from bottom: 7,8,3,6,2,5,1,4
BRAILLE_LEVELS = [
    0x00,     # 0/8
    0x40,     # dot 7
    0xC0,     # dots 7+8
    0xC4,     # dots 7+8+3
    0xC6,     # dots 7+8+3+6
    0xE6,     # dots 7+8+3+6+2
    0xF6,     # dots 7+8+3+6+2+5
    0xF7,     # dots 7+8+3+6+2+5+1
    0xFF,     # all 8 dots
]


def _braille_char(percentage):
    """Convert a percentage (0-100) to a braille character."""
    level = int(percentage / 100 * 8)
    level = max(0, min(8, level))
    return chr(BRAILLE_BASE + BRAILLE_LEVELS[level])


def _fmt_bytes(n):
    """Format bytes to human-readable string."""
    if n < 1024:
        return f'{n:.0f} B'
    elif n < 1024 * 1024:
        return f'{n / 1024:.1f} KiB'
    elif n < 1024 * 1024 * 1024:
        return f'{n / (1024*1024):.1f} MiB'
    else:
        return f'{n / (1024*1024*1024):.2f} GiB'


def _fmt_speed(bytes_per_sec):
    """Format bytes/s to human-readable string."""
    if abs(bytes_per_sec) < 1024:
        return f'{bytes_per_sec:.0f} B/s'
    elif abs(bytes_per_sec) < 1024 * 1024:
        return f'{bytes_per_sec / 1024:.1f} KiB/s'
    elif abs(bytes_per_sec) < 1024 * 1024 * 1024:
        return f'{bytes_per_sec / (1024*1024):.1f} MiB/s'
    else:
        return f'{bytes_per_sec / (1024*1024*1024):.2f} GiB/s'


def _fmt_uptime(seconds):
    """Format seconds to 'd hh:mm:ss'."""
    seconds = int(seconds)
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    secs = seconds % 60
    if days > 0:
        return f'{days}d {hours:02d}:{minutes:02d}:{secs:02d}'
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


def _color_for_percent(pct):
    """Return color pair number based on percentage thresholds."""
    if pct < 50:
        return 1  # green
    elif pct < 80:
        return 2  # yellow
    return 3  # red


def _draw_progress_bar(win, y, x, width, percent, label=''):
    """Draw a labeled progress bar: [====    ] 50.0%"""
    bar_width = width - 10  # leave room for percentage
    if bar_width < 5:
        bar_width = 5

    filled = int(percent / 100 * bar_width)
    filled = max(0, min(bar_width, filled))

    bar = '█' * filled + '░' * (bar_width - filled)
    color = _color_for_percent(percent)

    try:
        win.addstr(y, x, f'{label}{bar} {percent:5.1f}%', curses.color_pair(color))
    except curses.error:
        pass


def _draw_hbar(win, y, x, width, used, total, label, used_label='Used'):
    """Draw a horizontal usage bar with used/free/total labels."""
    try:
        if total > 0:
            pct = used / total * 100
        else:
            pct = 0.0

        bar_width = width - 2
        filled = int(pct / 100 * bar_width)
        filled = max(0, min(bar_width, filled))

        bar = '█' * filled + '░' * (bar_width - filled)
        color = _color_for_percent(pct)
        win.addstr(y, x, f'[{bar}]', curses.color_pair(color))

        # Labels on next line
        info = f'{used_label}: {_fmt_bytes(used)} / Total: {_fmt_bytes(total)} | Free: {_fmt_bytes(total - used)}'
        win.addstr(y + 1, x, info)
    except curses.error:
        pass


# ============================================================
# View drawing functions
# ============================================================

def draw_overview(win, cpu_history, cpu_percents, mem, swap, uptime, load):
    """Draw the overview (CPU, Memory, Swap, Uptime, Load)."""
    h, w = win.getmaxyx()
    y = 0

    # Title
    try:
        win.addstr(y, 0, ' SYSTEM MONITOR — Overview ', curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass
    y += 2

    # --- CPU Section ---
    try:
        win.addstr(y, 0, ' CPU Usage', curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    if cpu_percents and len(cpu_percents) > 1:
        cores = cpu_percents[1:]  # skip total
        bar_w = min(40, w - 15)
        for i, pct in enumerate(cores):
            if y >= h - 1:
                break
            label = f'  Core {i:2d}: '
            _draw_progress_bar(win, y, 0, bar_w + len(label) + 10, pct, label)
            y += 1

        # Total CPU
        if y < h - 1:
            total_pct = cpu_percents[0]
            _draw_progress_bar(win, y, 0, bar_w + len('  Total: ') + 10, total_pct, '  Total: ')
            y += 1
    y += 1

    # --- CPU History Graph ---
    if cpu_history:
        try:
            win.addstr(y, 0, ' CPU History (60s)', curses.A_BOLD)
        except curses.error:
            pass
        y += 1

        # cpu_history is a list (ring buffer) of lists: each element is [core0_pct, core1_pct, ...]
        # We'll render each core as a row of braille characters
        if cpu_history and len(cpu_history) > 0:
            num_cores = len(cpu_history[0])
            for core_idx in range(num_cores):
                if y >= h - 1:
                    break
                try:
                    win.addstr(y, 2, f'C{core_idx}:', curses.color_pair(4))
                except curses.error:
                    pass
                row = ''
                for snap in cpu_history:
                    if core_idx < len(snap):
                        row += _braille_char(snap[core_idx])
                    else:
                        row += ' '
                try:
                    win.addstr(y, 7, row)
                except curses.error:
                    pass
                y += 1
        y += 1

    # --- Memory Section ---
    if y < h - 4:
        try:
            win.addstr(y, 0, ' Memory', curses.A_BOLD)
        except curses.error:
            pass
        y += 1

        mem_total = mem.get('mem_total', 0)
        mem_used = mem_total - mem.get('mem_free', 0)
        mem_avail = mem.get('mem_available', 0)
        cached = mem.get('cached', 0)

        bar_w = min(50, w - 4)
        _draw_hbar(win, y, 2, bar_w, mem_used, mem_total, 'RAM')
        y += 2
        try:
            win.addstr(y, 2, f'Available: {_fmt_bytes(mem_avail)}  Cached: {_fmt_bytes(cached)}')
        except curses.error:
            pass
        y += 2

    # --- Swap Section ---
    if y < h - 4:
        try:
            win.addstr(y, 0, ' Swap', curses.A_BOLD)
        except curses.error:
            pass
        y += 1
        swap_total = swap.get('swap_total', 0)
        swap_used = swap_total - swap.get('swap_free', 0)
        _draw_hbar(win, y, 2, bar_w, swap_used, swap_total, 'Swap')
        y += 2

    # --- Uptime & Load ---
    if y < h - 1:
        try:
            win.addstr(y, 0, f' Uptime: {_fmt_uptime(uptime)}', curses.A_BOLD)
        except curses.error:
            pass
        y += 1

    if y < h - 1:
        try:
            win.addstr(y, 0, f' Load Avg: {load[0]:.2f} (1m)  {load[1]:.2f} (5m)  {load[2]:.2f} (15m)',
                       curses.A_BOLD)
        except curses.error:
            pass
        y += 1

    # Help bar at bottom
    try:
        win.addstr(h - 1, 0, ' Tab:Next View  q/F10:Quit  F5:Refresh', curses.color_pair(4))
    except curses.error:
        pass


def draw_processes(win, process_list, selected, scroll_offset, sort_col, search_str):
    """Draw the scrollable process table."""
    h, w = win.getmaxyx()
    y = 0

    # Title
    try:
        win.addstr(y, 0, ' PROCESSES ', curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass
    y += 1

    # Search indicator
    if search_str:
        try:
            win.addstr(y, 0, f' Search: "{search_str}"  (ESC to clear)', curses.color_pair(3))
        except curses.error:
            pass
        y += 1

    # Sort indicator
    sort_names = {'cpu': 'CPU%', 'mem': 'MEM%', 'pid': 'PID'}
    try:
        win.addstr(y, 0, f' Sort: {sort_names.get(sort_col, sort_col)}  (c=CPU, m=MEM, p=PID, t=Tree)',
                   curses.color_pair(4))
    except curses.error:
        pass
    y += 1

    # Header
    header = f'{"PID":>7} {"USER":<10} {"CPU%":>6} {"MEM%":>6} {"STATE":<6} COMMAND'
    try:
        win.addstr(y, 0, header, curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    y += 1

    # Process rows
    visible_rows = h - y - 1  # leave one line for help
    if visible_rows <= 0:
        return

    # Adjust scroll
    total = len(process_list)
    if selected >= total:
        selected = total - 1
    if selected < 0:
        selected = 0

    # Keep selected in view
    if selected < scroll_offset:
        scroll_offset = selected
    elif selected >= scroll_offset + visible_rows:
        scroll_offset = selected - visible_rows + 1

    if scroll_offset < 0:
        scroll_offset = 0

    for i in range(visible_rows):
        idx = scroll_offset + i
        if idx >= total:
            break
        p = process_list[idx]

        # Truncate command to fit
        cmd_w = w - 40
        cmd = p.cmdline[:cmd_w] if cmd_w > 0 else p.cmdline

        line = f'{p.pid:>7} {p.user:<10} {p.cpu_percent:>5.1f} {p.mem_percent:>5.1f} {p.state:<6} {cmd}'

        attr = curses.A_NORMAL
        if idx == selected:
            attr = curses.A_REVERSE

        # Color code CPU and MEM
        color = _color_for_percent(max(p.cpu_percent, p.mem_percent))

        try:
            win.addstr(y + i, 0, line[:w], attr | curses.color_pair(color))
        except curses.error:
            pass

    # Help bar
    try:
        win.addstr(h - 1, 0, ' j/k/arrows:Navigate  c/m/p:Sort  /:Search  K:Kill  r:Renice  t:Tree  Tab:Next',
                   curses.color_pair(4))
    except curses.error:
        pass


def draw_process_tree(win, tree, selected, scroll_offset):
    """Draw the process tree view with ASCII tree lines."""
    h, w = win.getmaxyx()
    y = 0

    # Title
    try:
        win.addstr(y, 0, ' PROCESS TREE ', curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass
    y += 1

    # Header
    header = f'{"PID":>7} {"USER":<10} {"CPU%":>6} {"MEM%":>6} {"STATE":<6} TREE'
    try:
        win.addstr(y, 0, header, curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    y += 1

    visible_rows = h - y - 1
    if visible_rows <= 0:
        return

    total = len(tree)
    if selected >= total:
        selected = total - 1
    if selected < 0:
        selected = 0

    if selected < scroll_offset:
        scroll_offset = selected
    elif selected >= scroll_offset + visible_rows:
        scroll_offset = selected - visible_rows + 1

    if scroll_offset < 0:
        scroll_offset = 0

    for i in range(visible_rows):
        idx = scroll_offset + i
        if idx >= total:
            break
        proc, depth, is_last_stack = tree[idx]

        # Build tree prefix
        prefix = ''
        for d in range(depth):
            if d < len(is_last_stack):
                if is_last_stack[d]:
                    prefix += '    '
                else:
                    prefix += '│   '
            else:
                prefix += '    '

        if depth > 0:
            if is_last_stack[-1] if is_last_stack else True:
                prefix += '└── '
            else:
                prefix += '├── '

        # Build line
        cmd_w = w - len(prefix) - 40
        if cmd_w < 5:
            cmd_w = 5
        cmd = proc.cmdline[:cmd_w]

        line = f'{proc.pid:>7} {proc.user:<10} {proc.cpu_percent:>5.1f} {proc.mem_percent:>5.1f} {proc.state:<6} {prefix}{cmd}'

        attr = curses.A_NORMAL
        if idx == selected:
            attr = curses.A_REVERSE

        color = _color_for_percent(max(proc.cpu_percent, proc.mem_percent))

        try:
            win.addstr(y + i, 0, line[:w], attr | curses.color_pair(color))
        except curses.error:
            pass

    # Help bar
    try:
        win.addstr(h - 1, 0, ' j/k/arrows:Navigate  t:Table View  Tab:Next',
                   curses.color_pair(4))
    except curses.error:
        pass


def draw_network(win, net_io, connections):
    """Draw network I/O and connection summary."""
    h, w = win.getmaxyx()
    y = 0

    try:
        win.addstr(y, 0, ' NETWORK ', curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass
    y += 2

    # Interface table
    try:
        win.addstr(y, 0, ' Interfaces', curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    header = f'{"Interface":<12} {"RX Speed":>14} {"TX Speed":>14} {"RX Total":>14} {"TX Total":>14}'
    try:
        win.addstr(y, 0, header, curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    y += 1

    for iface in net_io:
        if y >= h - 10:
            break
        name = iface['name']
        rx_speed = _fmt_speed(iface['rx_speed'])
        tx_speed = _fmt_speed(iface['tx_speed'])
        rx_total = _fmt_bytes(iface['rx_bytes'])
        tx_total = _fmt_bytes(iface['tx_bytes'])

        line = f'{name:<12} {rx_speed:>14} {tx_speed:>14} {rx_total:>14} {tx_total:>14}'
        try:
            win.addstr(y, 0, line[:w])
        except curses.error:
            pass
        y += 1

    y += 1

    # Connection summary
    try:
        win.addstr(y, 0, ' TCP Connections by State', curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    if connections:
        max_count_width = max(len(str(c)) for c in connections.values()) if connections else 3
        col_w = max_count_width + 18
        cols = max(1, w // col_w)
        states = sorted(connections.items(), key=lambda x: -x[1])

        for i, (state, count) in enumerate(states):
            if count == 0:
                continue
            col = i % cols
            row = i // cols
            cx = col * col_w
            try:
                if y + row < h - 1:
                    text = f'{state:<15} {count:>5}'
                    win.addstr(y + row, cx, text)
            except curses.error:
                pass

    # Help bar
    try:
        win.addstr(h - 1, 0, ' Tab:Next View', curses.color_pair(4))
    except curses.error:
        pass


def draw_disk(win, disk_usage, disk_io):
    """Draw disk usage and I/O speeds."""
    h, w = win.getmaxyx()
    y = 0

    try:
        win.addstr(y, 0, ' DISK ', curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass
    y += 2

    # Disk Usage
    try:
        win.addstr(y, 0, ' Filesystems', curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    for fs in disk_usage:
        if y >= h - 12:
            break
        mount = fs['mountpoint']
        pct = fs['percent']
        total = _fmt_bytes(fs['total'])
        used = _fmt_bytes(fs['used'])
        free = _fmt_bytes(fs['free'])

        label = f' {mount} '
        try:
            win.addstr(y, 0, f'{label}', curses.A_BOLD)
        except curses.error:
            pass

        # Draw bar
        bar_width = min(40, w - 30)
        filled = int(pct / 100 * bar_width)
        filled = max(0, min(bar_width, filled))
        bar = '█' * filled + '░' * (bar_width - filled)
        color = _color_for_percent(pct)

        try:
            win.addstr(y, len(label), f'[{bar}] {pct:5.1f}%', curses.color_pair(color))
        except curses.error:
            pass
        y += 1

        try:
            win.addstr(y, 2, f'Used: {used}  Free: {free}  Total: {total}')
        except curses.error:
            pass
        y += 1

    y += 1

    # Disk I/O
    if y < h - 1:
        try:
            win.addstr(y, 0, ' Disk I/O Speeds', curses.A_BOLD)
        except curses.error:
            pass
        y += 1

        header = f'{"Device":<12} {"Read":>14} {"Write":>14}'
        try:
            win.addstr(y, 0, header, curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass
        y += 1

        for disk in disk_io:
            if y >= h - 2:
                break
            name = disk['device']
            read_s = _fmt_speed(disk['read_speed'])
            write_s = _fmt_speed(disk['write_speed'])
            line = f'{name:<12} {read_s:>14} {write_s:>14}'
            try:
                win.addstr(y, 0, line[:w])
            except curses.error:
                pass
            y += 1

    # Help bar
    try:
        win.addstr(h - 1, 0, ' Tab:Next View', curses.color_pair(4))
    except curses.error:
        pass


def draw_battery_popup(win, battery):
    """Draw a small battery info popup (called from monitor)."""
    if not battery or not battery.get('has_battery'):
        return

    h, w = win.getmaxyx()
    # Draw in upper right corner
    bx = max(w - 35, 0)
    by = 0
    bw = 35
    bh = 5

    # Background
    for i in range(bh):
        try:
            win.addstr(by + i, bx, ' ' * bw, curses.A_REVERSE)
        except curses.error:
            pass

    try:
        win.addstr(by, bx, ' BATTERY ', curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    pct = battery.get('percentage', 0)
    status = battery.get('status', 'Unknown')
    time_rem = battery.get('time_remaining_sec', -1)

    try:
        win.addstr(by + 1, bx + 1, f'Charge:  {pct}%', curses.A_REVERSE)
    except curses.error:
        pass

    try:
        win.addstr(by + 2, bx + 1, f'Status:  {status}', curses.A_REVERSE)
    except curses.error:
        pass

    if time_rem > 0:
        hours = int(time_rem // 3600)
        minutes = int((time_rem % 3600) // 60)
        try:
            win.addstr(by + 3, bx + 1, f'Remaining: {hours}h {minutes}m', curses.A_REVERSE)
        except curses.error:
            pass
    elif status.lower() == 'discharging' and time_rem == -1:
        try:
            win.addstr(by + 3, bx + 1, 'Remaining: estimating...', curses.A_REVERSE)
        except curses.error:
            pass


def draw_confirmation_popup(win, message):
    """Draw a confirmation popup and return True if 'y' pressed, False otherwise."""
    h, w = win.getmaxyx()
    pw = len(message) + 6
    ph = 4
    px = (w - pw) // 2
    py = (h - ph) // 2

    # Draw popup
    for i in range(ph):
        try:
            win.addstr(py + i, px, ' ' * pw, curses.A_REVERSE)
        except curses.error:
            pass

    try:
        win.addstr(py, px, message.center(pw), curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass
    try:
        win.addstr(py + 2, px, ' Press y to confirm, n to cancel '.center(pw), curses.A_REVERSE)
    except curses.error:
        pass

    win.refresh()

    while True:
        ch = win.getch()
        if ch in (ord('y'), ord('Y')):
            return True
        elif ch in (ord('n'), ord('N'), 27):  # ESC also cancels
            return False


def draw_input_popup(win, message):
    """Draw an input popup and return the entered string."""
    h, w = win.getmaxyx()
    pw = max(50, len(message) + 10)
    ph = 4
    px = (w - pw) // 2
    py = (h - ph) // 2

    input_str = ''

    while True:
        # Draw popup
        for i in range(ph):
            try:
                win.addstr(py + i, px, ' ' * pw, curses.A_REVERSE)
            except curses.error:
                pass

        try:
            win.addstr(py, px, message.center(pw), curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass
        try:
            display_str = (input_str + '_') if len(input_str) < pw - 4 else input_str[-pw+5:] + '_'
            win.addstr(py + 2, px + 2, display_str, curses.A_REVERSE)
        except curses.error:
            pass
        try:
            win.addstr(py + 3, px, ' Enter to confirm, ESC to cancel '.center(pw), curses.A_REVERSE)
        except curses.error:
            pass

        win.refresh()

        ch = win.getch()
        if ch == 10 or ch == 13:  # Enter
            return input_str
        elif ch == 27:  # ESC
            return None
        elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
            input_str = input_str[:-1]
        elif 32 <= ch <= 126:
            input_str += chr(ch)


def draw_message_popup(win, message):
    """Draw a temporary message popup."""
    h, w = win.getmaxyx()
    pw = len(message) + 6
    ph = 3
    px = (w - pw) // 2
    py = (h - ph) // 2

    for i in range(ph):
        try:
            win.addstr(py + i, px, ' ' * pw, curses.A_REVERSE)
        except curses.error:
            pass

    try:
        win.addstr(py + 1, px, message.center(pw), curses.A_BOLD | curses.A_REVERSE)
    except curses.error:
        pass

    win.refresh()
    time.sleep(1.5)
