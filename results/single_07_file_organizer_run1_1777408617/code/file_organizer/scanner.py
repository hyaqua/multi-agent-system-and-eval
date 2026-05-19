"""Directory scanner for listing files with metadata."""

import os
import sys
import datetime
from pathlib import Path


def scan_directory(target_path: Path) -> list[dict]:
    """Scan a directory and return a list of file metadata dicts.

    Skips hidden files/directories. Handles permission errors gracefully.
    Shows a progress indicator during scanning.

    Returns:
        List of dicts with keys: path, name, size, mtime, extension.
    """
    files: list[dict] = []
    target_path = target_path.resolve()

    # Count entries first for progress reporting
    try:
        all_entries = list(os.scandir(target_path))
    except PermissionError:
        print(f"Error: Permission denied accessing '{target_path}'.", file=sys.stderr)
        sys.exit(1)

    total = len(all_entries)
    scanned = 0
    warnings: list[str] = []

    for entry in all_entries:
        scanned += 1
        _show_progress(scanned, total, "Scanning")

        # Skip hidden files and directories
        if entry.name.startswith('.'):
            continue

        try:
            is_file = entry.is_file(follow_symlinks=False)
        except PermissionError:
            warnings.append(f"Warning: Permission denied: {entry.path}")
            continue

        if is_file:
            try:
                stat = entry.stat()
                ext = ''.join(Path(entry.name).suffixes).lower()
                # Normalize: if no compound extension, just use the last suffix
                if not ext:
                    ext = ''
                files.append({
                    'path': Path(entry.path).resolve(),
                    'name': entry.name,
                    'size': stat.st_size,
                    'mtime': datetime.datetime.fromtimestamp(stat.st_mtime),
                    'extension': ext,
                })
            except PermissionError:
                warnings.append(f"Warning: Permission denied reading: {entry.path}")
            except OSError as e:
                warnings.append(f"Warning: Could not read '{entry.path}': {e}")

    # Clear progress line
    if total > 30:
        sys.stderr.write('\r' + ' ' * 60 + '\r')
        sys.stderr.flush()

    # Print warnings
    for w in warnings:
        print(w, file=sys.stderr)

    return files


def _show_progress(current: int, total: int, label: str) -> None:
    """Show a progress indicator on stderr for large operations."""
    if total <= 30:
        return
    if current % max(1, total // 50) != 0 and current != total:
        return
    pct = current * 100 // total
    bar_len = 25
    filled = bar_len * current // total
    bar = '█' * filled + '░' * (bar_len - filled)
    sys.stderr.write(f'\r{label}: [{bar}] {pct:3d}% ({current}/{total})')
    sys.stderr.flush()
