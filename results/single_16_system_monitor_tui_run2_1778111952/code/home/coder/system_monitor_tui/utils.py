"""Utility functions for system_monitor_tui."""

import os
import time


def human_readable_bytes(n: int) -> str:
    """Convert bytes to human-readable string."""
    if n < 1024:
        return f"{n}B"
    for unit in ['K', 'M', 'G', 'T', 'P']:
        n /= 1024.0
        if n < 1024 or unit == 'P':
            if n < 10:
                return f"{n:.1f}{unit}"
            return f"{int(round(n))}{unit}"
    return f"{n:.1f}P"


def human_readable_bits(n: int) -> str:
    """Convert bits to human-readable string (for network)."""
    return human_readable_bytes(n * 8).replace('B', 'b')


def format_uptime(seconds: float) -> str:
    """Format uptime seconds into days, hours, minutes, seconds."""
    days = int(seconds) // 86400
    hours = (int(seconds) % 86400) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def format_percent(val: float) -> str:
    """Format a float as a percentage string."""
    return f"{val:5.1f}%"


def make_bar(fraction: float, width: int, fill_char: str = '#') -> str:
    """Create a text progress bar."""
    if fraction < 0:
        fraction = 0.0
    if fraction > 1:
        fraction = 1.0
    filled = int(round(fraction * width))
    return fill_char * filled + ' ' * (width - filled)


def get_color_for_usage(usage: float) -> int:
    """Return a color index: 0=low (green), 1=medium (yellow), 2=high (red)."""
    if usage < 50:
        return 0
    elif usage < 80:
        return 1
    else:
        return 2


def braille_dot(val: float) -> int:
    """
    Map a value 0.0-1.0 to a dot mask for a single column of a braille character.
    A braille column has 4 dots (positions 1,2,3,7 for left; 4,5,6,8 for right).
    Returns a bitmask with the appropriate dots set.
    
    Dots from bottom to top:
    - val 0.0-0.25: dot 7 (bottom) for left, dot 8 for right
    - val 0.25-0.5: dots 7+3 for left, dots 8+6 for right
    - val 0.5-0.75: dots 7+3+2 for left, dots 8+6+5 for right
    - val 0.75-1.0: dots 7+3+2+1 for left, dots 8+6+5+4 for right
    """
    if val < 0:
        val = 0.0
    if val > 1:
        val = 1.0
    level = int(val * 4)
    if level >= 4:
        level = 4
    # Left column dots: 1(top), 2, 3, 7(bottom)
    # Right column dots: 4(top), 5, 6, 8(bottom)
    # We'll handle mapping in the braille_graph function
    return level


# Braille character base
BRAILLE_BASE = 0x2800

# Dot positions in braille (left column: 1,2,3,7; right column: 4,5,6,8)
LEFT_DOTS = [0x01, 0x02, 0x04, 0x40]   # dots 1,2,3,7 (top to bottom)
RIGHT_DOTS = [0x08, 0x10, 0x20, 0x80]   # dots 4,5,6,8 (top to bottom)


def braille_graph(values: list, max_width: int, max_value: float = 100.0) -> str:
    """
    Create a braille character line graph.
    Each braille character encodes 2 time points (left and right columns),
    with 4 vertical levels each.
    values: list of floats (0-max_value)
    max_width: max number of braille characters (so 2*max_width data points)
    """
    if not values:
        return ""
    
    # Take the most recent values, up to 2*max_width
    chunk_size = max_width * 2
    recent = values[-chunk_size:] if len(values) > chunk_size else values
    
    # Pad to fill the width
    padding = chunk_size - len(recent)
    
    result = []
    
    # Process pairs of values into braille characters
    for i in range(0, len(recent), 2):
        left_val = 0
        right_val = 0
        if i < len(recent):
            left_val = recent[i] / max_value if max_value > 0 else 0
        if i + 1 < len(recent):
            right_val = recent[i + 1] / max_value if max_value > 0 else 0
        
        left_level = braille_dot(left_val)
        right_level = braille_dot(right_val)
        
        code = BRAILLE_BASE
        for j in range(left_level):
            code |= LEFT_DOTS[j]
        for j in range(right_level):
            code |= RIGHT_DOTS[j]
        
        result.append(chr(code))
    
    # Pad with empty braille on the left
    while len(result) < max_width:
        result.insert(0, chr(BRAILLE_BASE))
    
    return "".join(result)


def safe_read(path: str) -> str:
    """Safely read a file, returning empty string on failure."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except (IOError, PermissionError, FileNotFoundError):
        return ""


def safe_readlines(path: str) -> list:
    """Safely read lines from a file."""
    try:
        with open(path, 'r') as f:
            return f.readlines()
    except (IOError, PermissionError, FileNotFoundError):
        return []


def safe_int(val, default=0):
    """Safely convert to int."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    """Safely convert to float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
