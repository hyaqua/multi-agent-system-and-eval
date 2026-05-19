"""ui_utils.py - Helper functions for formatting, drawing, colors."""

import curses
import math
from typing import List, Tuple, Deque, Optional

# Color pair IDs
COLOR_GREEN = 1
COLOR_YELLOW = 2
COLOR_RED = 3
COLOR_CYAN = 4
COLOR_WHITE = 5
COLOR_BLUE = 6
COLOR_MAGENTA = 7


def setup_colors() -> None:
    """Initialize curses color pairs."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_MAGENTA, curses.COLOR_MAGENTA, -1)


def get_usage_color(percent: float) -> int:
    """Return color pair index based on usage percentage thresholds."""
    if percent < 50.0:
        return COLOR_GREEN
    elif percent < 80.0:
        return COLOR_YELLOW
    else:
        return COLOR_RED


def format_bytes(num_bytes: float) -> str:
    """Convert bytes to human-readable string."""
    if num_bytes < 0:
        return "N/A"
    if num_bytes == 0:
        return "0 B"
    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    i = 0
    while num_bytes >= 1024.0 and i < len(units) - 1:
        num_bytes /= 1024.0
        i += 1
    if i == 0:
        return f"{int(num_bytes)} {units[i]}"
    return f"{num_bytes:.1f} {units[i]}"


def format_bytes_per_sec(bytes_per_sec: float) -> str:
    """Convert bytes/sec to human-readable rate string."""
    return format_bytes(bytes_per_sec) + "/s"


def format_uptime(seconds: float) -> str:
    """Convert uptime seconds to Dd HH:MM:SS format."""
    if seconds < 0:
        return "N/A"
    s = int(seconds)
    days = s // 86400
    s %= 86400
    hours = s // 3600
    s %= 3600
    minutes = s // 60
    secs = s % 60
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """Add a string safely, truncating if needed to fit within window bounds."""
    if win is None:
        return
    max_y, max_x = win.getmaxyx()
    if y < 0 or y >= max_y or x >= max_x:
        return
    remaining = max_x - x
    if remaining <= 0:
        return
    if len(text) > remaining:
        text = text[:remaining]
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_progress_bar(win, y: int, x: int, width: int, percent: float,
                      label: str = "", show_percent: bool = True) -> None:
    """Draw a horizontal progress bar with color coding."""
    color = get_usage_color(percent)
    bar_char = "█"
    prefix = f"{label} " if label else ""
    suffix = f" {percent:5.1f}%" if show_percent else ""
    bar_width = width - len(prefix) - len(suffix)
    if bar_width < 2:
        bar_width = 2

    filled = int(round(percent / 100.0 * bar_width))
    filled = max(0, min(filled, bar_width))
    empty = bar_width - filled

    bar = bar_char * filled + " " * empty
    full_line = prefix + bar + suffix
    safe_addstr(win, y, x, full_line, curses.color_pair(color))


def draw_box(win, y: int, x: int, height: int, width: int, title: str = "") -> None:
    """Draw an ASCII box."""
    safe_addstr(win, y, x, "┌" + "─" * (width - 2) + "┐")
    if title:
        safe_addstr(win, y, x + 2, f" {title} ")
    for row in range(1, height - 1):
        safe_addstr(win, y + row, x, "│")
        safe_addstr(win, y + row, x + width - 1, "│")
    safe_addstr(win, y + height - 1, x, "└" + "─" * (width - 2) + "┘")


def draw_table_header(win, y: int, x: int, columns: List[Tuple[str, int]],
                      sort_key: str = "", sort_reverse: bool = True) -> None:
    """Draw a highlighted table header row."""
    offset = x
    for name, w in columns:
        if name == sort_key:
            arrow = "▼" if sort_reverse else "▲"
            header = f"{name}{arrow}"
        else:
            header = name
        header = header[:w].ljust(w)
        safe_addstr(win, y, offset, header, curses.A_BOLD | curses.A_REVERSE)
        offset += w


def draw_braille_graph(win, y: int, x: int, width: int,
                       data: Deque[float], max_value: float = 100.0,
                       height: int = 4) -> None:
    """Draw a scrolling braille graph. Each column uses 2x4 dot matrix.

    height: number of text rows (each row = 4 dots).
    width: number of columns (each column = 2 dots wide).
    """
    if not data or height < 1 or width < 1:
        return

    # We work with data points directly; width columns, each 2 dots wide
    vals = list(data)
    if len(vals) > width:
        vals = vals[-width:]

    # Pad to width
    while len(vals) < width:
        vals.insert(0, 0.0)

    dot_rows = height * 4  # total vertical dots

    # Build dot matrix: columns of vals mapped to dot columns
    # Each braille char covers 2 horizontal dots × 4 vertical dots
    chars_per_col = (height * 4 + 3) // 4  # rows of braille chars needed
    # Actually, height = number of braille chars vertically, each covers 4 dots

    for row in range(height):
        line = ""
        for col in range(width):
            val = vals[col]
            # Determine which dots in this 2-wide × 4-high block are lit
            # Dots from bottom to top:
            #   dot0 = bit0 (0x01), dot1 = bit1 (0x02), dot2 = bit2 (0x04),
            #   dot3 = bit3 (0x08), dot4 = bit4 (0x10), dot5 = bit5 (0x20),
            #   dot6 = bit6 (0x40), dot7 = bit7 (0x80)
            # Layout: LSB = top-left? No, standard braille:
            # 1(0x01) 4(0x08)
            # 2(0x02) 5(0x10)
            # 3(0x04) 6(0x20)
            # 7(0x40) 8(0x80)

            # This row of chars covers vertical dots [row*4 .. row*4+3]
            top = row * 4
            code = 0
            # Dot 1: top-left  (0x01)
            # Dot 2: middle-left (0x02)
            # Dot 3: bottom-left (0x04)
            # Dot 7: top-right (0x40) -- actually no, standard:
            # 1 4
            # 2 5
            # 3 6
            # 7 8
            # Left column dots: 1(0x01), 2(0x02), 3(0x04), 7(0x40)
            # Right column dots: 4(0x08), 5(0x10), 6(0x20), 8(0x80)

            # Map vertical position to dot:
            # bottom dot (dot 7) = full, top dot (dot 1) = 1/4
            # We have 8 dots total for 2 columns, 4 high each
            # Let's fill dots proportionally from bottom:
            # If val/max fills fraction f of bar:
            # We have 8 dots. Fill from bottom up.
            rank = int(round((val / max_value) * 8))
            rank = max(0, min(rank, 8))

            # Dot numbering (bottom to top, left then right column):
            # bottom-left = dot3 (0x04)
            # bottom-right= dot6 (0x20)
            # mid-low-left= dot2 (0x02)
            # mid-low-right=dot5 (0x10)
            # mid-hi-left = dot1 (0x01)
            # mid-hi-right= dot4 (0x08)
            # top-left    = dot7 (0x40)
            # top-right   = dot8 (0x80)

            # Let's use top-to-bottom ordering:
            # top-left=dot1(0x01), top-right=dot4(0x08)
            # mid-hi-left=dot2(0x02), mid-hi-right=dot5(0x10)
            # mid-lo-left=dot3(0x04), mid-lo-right=dot6(0x20)
            # bot-left=dot7(0x40), bot-right=dot8(0x80)

            dot_positions = [0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80]
            for d in range(rank):
                code |= dot_positions[d]

            line += chr(0x2800 + code)
        safe_addstr(win, y + row, x, line)
