"""Utility functions for system_monitor_tui."""

import math
from typing import List, Optional


def format_bytes(size_bytes: float) -> str:
    """Convert bytes to human-readable string (base-1024)."""
    if size_bytes < 0:
        return "0.0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    unit_idx = 0
    value = float(size_bytes)
    while value >= 1024 and unit_idx < len(units) - 1:
        value /= 1024
        unit_idx += 1
    if unit_idx == 0:
        return f"{value:.0f} {units[unit_idx]}"
    return f"{value:.1f} {units[unit_idx]}"


def format_bits_per_sec(bits_per_sec: float) -> str:
    """Convert bits/sec to human-readable string (base-1000 for networking)."""
    if bits_per_sec < 0:
        return "0 bps"
    units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"]
    unit_idx = 0
    value = float(bits_per_sec)
    while value >= 1000 and unit_idx < len(units) - 1:
        value /= 1000
        unit_idx += 1
    return f"{value:.1f} {units[unit_idx]}"


def format_bytes_per_sec(bytes_per_sec: float) -> str:
    """Convert bytes/sec to human-readable string (base-1024)."""
    if bytes_per_sec < 0:
        return "0 B/s"
    units = ["B/s", "KiB/s", "MiB/s", "GiB/s", "TiB/s"]
    unit_idx = 0
    value = float(bytes_per_sec)
    while value >= 1024 and unit_idx < len(units) - 1:
        value /= 1024
        unit_idx += 1
    return f"{value:.1f} {units[unit_idx]}"


def format_uptime(seconds: float) -> str:
    """Format seconds as 'D days, HH:MM:SS'."""
    seconds = int(seconds)
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_time_remaining(seconds: Optional[float]) -> str:
    """Format remaining seconds as HH:MM or 'N/A'."""
    if seconds is None or seconds <= 0 or math.isinf(seconds):
        return "N/A"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def sort_processes(processes: list, key: str, reverse: bool = True) -> list:
    """Sort process list by given key."""
    if key == "cpu":
        return sorted(processes, key=lambda p: p.get("cpu_percent", 0.0), reverse=reverse)
    elif key == "mem":
        return sorted(processes, key=lambda p: p.get("mem_percent", 0.0), reverse=reverse)
    elif key == "pid":
        return sorted(processes, key=lambda p: p.get("pid", 0), reverse=not reverse)
    return processes


def strip_null(s: str) -> str:
    """Strip null bytes and surrounding whitespace."""
    return s.replace('\0', '').strip()
