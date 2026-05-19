"""Curses UI helpers: colors, progress bars, braille sparkline, formatted tables."""

import curses
from collections import deque
from typing import List, Tuple

# Color pair constants
COLOR_GREEN = 1
COLOR_YELLOW = 2
COLOR_RED = 3
COLOR_WHITE = 4
COLOR_CYAN = 5
COLOR_MAGENTA = 6
COLOR_BLUE = 7

# Braille dot patterns for 8 vertical levels (0-8 dots)
# Unicode braille starts at U+2800. Each dot is a bit:
# Dot 1: 0x01, Dot 2: 0x02, Dot 3: 0x04, Dot 4: 0x08
# Dot 5: 0x10, Dot 6: 0x20, Dot 7: 0x40, Dot 8: 0x80
# We use left column (dots 1,2,3,4) for each position, 4 bits = 0-15 levels
# But simpler: use bottom-up filling of dots 1,2,3,4,5,6,7,8

# Map height 0-8 to braille char
_BRAILLE_LEVELS = [
    0x2800,  # 0 dots
    0x2801,  # dot 1
    0x2803,  # dots 1+2
    0x2807,  # dots 1+2+3
    0x280F,  # dots 1+2+3+4
    0x281F,  # dots 1+2+3+4+5
    0x283F,  # dots 1+2+3+4+5+6
    0x287F,  # dots 1+2+3+4+5+6+7
    0x28FF,  # all 8 dots
]


def init_colors():
    """Initialize color pairs."""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_RED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_BLUE, curses.COLOR_BLUE, -1)


def draw_tab_bar(stdscr, active_idx: int, view_names: list):
    """Draw a full-width tab bar on line 0.

    Active tab is highlighted with A_REVERSE.
    Inactive tabs use normal color (COLOR_WHITE).
    Fills remaining space with spaces to ensure full-width coverage.
    """
    height, width = stdscr.getmaxyx()
    if height < 1:
        return

    # Build tab segments: list of (text, is_active)
    tabs = []
    for i, name in enumerate(view_names):
        if i == active_idx:
            tabs.append((f" {name} ", True))
        else:
            tabs.append((f" {name} ", False))

    try:
        # First clear the entire line
        stdscr.addstr(0, 0, " " * width)

        x = 0
        for text, is_active in tabs:
            if x + len(text) > width:
                break
            attr = curses.A_REVERSE if is_active else curses.color_pair(COLOR_WHITE)
            stdscr.addstr(0, x, text, attr)
            x += len(text)

        # Fill the rest of the line with spaces (with normal attribute)
        if x < width:
            stdscr.addstr(0, x, " " * (width - x))
    except curses.error:
        pass


def get_color_for_percent(percent: float) -> int:
    """Return color pair number for a percentage value."""
    if percent < 50:
        return COLOR_GREEN
    elif percent < 80:
        return COLOR_YELLOW
    return COLOR_RED


def draw_bar(win, y: int, x: int, width: int, percent: float, label: str = ""):
    """Draw a horizontal progress bar at position (y, x).

    Args:
        win: Curses window
        y, x: Position
        width: Total width of the bar (including brackets)
        percent: 0-100 value
        label: Optional label displayed inside or next to bar
    """
    if width < 5:
        return

    color = get_color_for_percent(percent)

    # Calculate bar inner width
    bar_width = width - 2  # for [ and ]
    filled = int(bar_width * percent / 100)
    if filled > bar_width:
        filled = bar_width
    if filled < 0:
        filled = 0

    bar = "█" * filled + " " * (bar_width - filled)

    # Format label with percentage
    pct_str = f"{percent:5.1f}%"
    if label:
        display = f" {label} {pct_str} ".strip()
    else:
        display = f" {pct_str} "

    # Center display in bar
    if len(display) <= bar_width:
        start = (bar_width - len(display)) // 2
        bar = bar[:start] + display + bar[start + len(display):]

    try:
        win.addstr(y, x, "[", curses.color_pair(color))
        win.addstr(y, x + 1, bar, curses.color_pair(color) | curses.A_BOLD)
        win.addstr(y, x + 1 + bar_width, "]", curses.color_pair(color))
    except curses.error:
        pass


def draw_labeled_bar(win, y: int, x: int, width: int, label_width: int,
                     label: str, percent: float, used_str: str, total_str: str):
    """Draw a bar with a left label, bar, and right usage text.

    Layout: [label] [====bar====] [used/total]

    Args:
        label_width: width of the label column
    """
    # Draw label
    try:
        win.addstr(y, x, label[:label_width].ljust(label_width))
    except curses.error:
        pass

    bar_x = x + label_width + 1
    bar_width = width - label_width - 1 - 20  # Reserve 20 for usage text
    if bar_width < 5:
        bar_width = width - label_width - 1

    draw_bar(win, y, bar_x, bar_width, percent)

    # Usage text
    usage_text = f"{used_str} / {total_str}"
    usage_x = bar_x + bar_width + 2
    try:
        win.addstr(y, usage_x, usage_text[:width - usage_x + x])
    except curses.error:
        pass


def draw_sparkline(win, y: int, x: int, width: int, history: deque):
    """Draw a braille sparkline showing CPU history.

    Each column is a single braille character encoding 8 levels.
    """
    if not history or width < 2:
        return

    data = list(history)
    # If we have more data than width, downsample
    if len(data) > width:
        # Take evenly spaced samples
        step = len(data) / width
        sampled = [data[int(i * step)] for i in range(width)]
        data = sampled

    line = ""
    for val in data:
        # Map 0-100 to 0-8
        level = int(round(val / 100 * 8))
        level = max(0, min(8, level))
        line += chr(_BRAILLE_LEVELS[level])

    # Right-align the sparkline
    if len(line) < width:
        line = " " * (width - len(line)) + line

    try:
        win.addstr(y, x, line[:width])
    except curses.error:
        pass


def draw_table_header(win, y: int, x: int, columns: List[Tuple[str, int]]):
    """Draw a table header row.

    Args:
        columns: list of (name, width) tuples
    """
    try:
        header = ""
        for name, w in columns:
            header += name.ljust(w) + " "
        win.addstr(y, x, header, curses.A_BOLD | curses.A_UNDERLINE)
    except curses.error:
        pass


def draw_table_row(win, y: int, x: int, columns: List[Tuple[str, int]],
                   highlight: bool = False, color: int = COLOR_WHITE):
    """Draw a table row.

    Args:
        columns: list of (value, width) tuples
        highlight: if True, draw with reversed colors
        color: base color pair
    """
    try:
        row = ""
        for val, w in columns:
            row += str(val)[:w].ljust(w) + " "
        attr = curses.color_pair(color)
        if highlight:
            attr |= curses.A_REVERSE
        win.addstr(y, x, row, attr)
    except curses.error:
        pass


def draw_section_header(win, y: int, x: int, title: str, width: int):
    """Draw a section header with horizontal lines."""
    try:
        line = "─" * width
        text = f" {title} "
        start = (width - len(text)) // 2
        header_line = line[:start] + text + line[start + len(text):]
        win.addstr(y, x, header_line[:width], curses.A_BOLD)
    except curses.error:
        pass


def safe_addstr(win, y: int, x: int, text: str, attr=0):
    """Add string safely, ignoring errors if out of bounds."""
    try:
        win.addstr(y, x, text[:], attr)
    except curses.error:
        pass
