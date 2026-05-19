"""File scanner: walks a directory and collects file metadata."""

import os
import os.path
from datetime import datetime
from typing import Iterator


class FileInfo:
    """Holds metadata about a single file."""

    __slots__ = ("path", "name", "size", "mtime", "ext")

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        stat = os.stat(path)
        self.size = stat.st_size
        self.mtime = datetime.fromtimestamp(stat.st_mtime)
        _, self.ext = os.path.splitext(self.name)
        self.ext = self.ext.lower()  # normalize


def scan_directory(
    target: str,
    *,
    skip_hidden: bool = True,
    on_progress=None,
) -> list[FileInfo]:
    """Walk *target* (non‑recursive) and return a list of FileInfo objects.

    Parameters
    ----------
    target : str
        Absolute or relative path to the directory.
    skip_hidden : bool
        If True, files and folders whose name starts with '.' are ignored.
    on_progress : callable or None
        Called after each visible file is processed; signature ``on_progress(current_count)``.

    Returns
    -------
    list[FileInfo]
        Sorted by name for deterministic output.
    """
    files: list[FileInfo] = []
    count = 0

    try:
        entries = os.listdir(target)
    except PermissionError:
        print(f"⚠  Permission denied: cannot list directory '{target}'")
        return []
    except OSError as exc:
        print(f"⚠  Error reading directory '{target}': {exc}")
        return []

    for entry in sorted(entries, key=str.lower):
        full = os.path.join(target, entry)

        # Skip hidden
        if skip_hidden and entry.startswith("."):
            continue

        # We only organise *files* (not directories)
        if not os.path.isfile(full):
            continue

        try:
            info = FileInfo(full)
        except PermissionError:
            print(f"⚠  Permission denied: cannot stat '{full}' — skipping.")
            continue
        except OSError as exc:
            print(f"⚠  Error reading '{full}': {exc} — skipping.")
            continue

        files.append(info)
        count += 1
        if on_progress:
            on_progress(count)

    return files
