#!/usr/bin/env python3
"""File Organizer – organize files by extension, date, or size."""

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FILENAME = ".file_organizer_log.json"

EXTENSION_MAP = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".bmp": "Images", ".tiff": "Images",
    ".tif": "Images", ".webp": "Images", ".svg": "Images",
    ".ico": "Images", ".raw": "Images", ".heic": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".odt": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".csv": "Documents", ".md": "Documents",
    ".tex": "Documents", ".log": "Documents",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".aac": "Audio", ".ogg": "Audio", ".wma": "Audio",
    ".m4a": "Audio", ".opus": "Audio",
    # Video
    ".mp4": "Video", ".avi": "Video", ".mkv": "Video",
    ".mov": "Video", ".wmv": "Video", ".flv": "Video",
    ".webm": "Video", ".m4v": "Video",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code",
    ".html": "Code", ".css": "Code", ".scss": "Code",
    ".json": "Code", ".xml": "Code", ".yaml": "Code",
    ".yml": "Code", ".c": "Code", ".cpp": "Code",
    ".h": "Code", ".hpp": "Code", ".java": "Code",
    ".rs": "Code", ".go": "Code", ".rb": "Code",
    ".php": "Code", ".sql": "Code", ".sh": "Code",
    ".bat": "Code", ".ps1": "Code", ".toml": "Code",
    ".ini": "Code", ".cfg": "Code",
}

SIZE_THRESHOLDS = [
    (1 * 1024 * 1024, "Small"),       # < 1 MB
    (100 * 1024 * 1024, "Medium"),    # < 100 MB
    (float("inf"), "Large"),          # >= 100 MB
]

PROGRESS_INTERVAL = 10   # print progress every N files
PROGRESS_THRESHOLD = 20  # only show progress if more than this many files


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    name: str
    path: str           # absolute path
    extension: str      # lower-case, e.g. ".txt"
    category: str = ""  # extension category, set later by _assign_categories
    size: int = 0       # bytes
    mtime: float = 0.0  # epoch seconds


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_directory(target: str) -> list[FileInfo]:
    """Return a list of FileInfo for all regular, non-hidden files in *target*.

    Hidden files and directories (names starting with '.') are skipped.
    Permission errors are caught and reported to stderr.
    """
    files: list[FileInfo] = []
    target_path = Path(target).resolve()

    try:
        entries = sorted(target_path.iterdir())
    except PermissionError:
        print(f"Warning: cannot read directory '{target}'", file=sys.stderr)
        return files

    for entry in entries:
        # Skip hidden entries
        if entry.name.startswith("."):
            continue

        # Skip directories (we only organize files at the top level)
        if entry.is_dir():
            continue

        # Must be a regular file (or symlink to a regular file)
        if not entry.is_file():
            continue

        try:
            stat = entry.stat()
        except (PermissionError, OSError) as exc:
            print(f"Warning: cannot stat '{entry}': {exc}", file=sys.stderr)
            continue

        files.append(FileInfo(
            name=entry.name,
            path=str(entry),
            extension=entry.suffix.lower(),
            size=stat.st_size,
            mtime=stat.st_mtime,
        ))

    return files


# ---------------------------------------------------------------------------
# Per-file table helpers
# ---------------------------------------------------------------------------

def human_readable_size(size: int) -> str:
    """Convert a byte count into a human-readable string."""
    if size < 1024:
        return f"{size} B"
    for unit in ["KiB", "MiB", "GiB", "TiB"]:
        size /= 1024.0
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PiB"


def _assign_categories(files: list[FileInfo]) -> None:
    """Set the ``category`` field on every FileInfo based on extension."""
    for f in files:
        f.category = EXTENSION_MAP.get(f.extension, "Other")


def print_file_table(files: list[FileInfo], target: str) -> None:
    """Print the mandatory per-file listing with Name, Type, Size, Modified."""
    print(f"\nScanned {len(files)} files in {target}:")
    print(f"{'Name':<30} {'Type':<14} {'Size':>10}  {'Modified':<16}")
    print("-" * 72)

    for f in files:
        mtime_str = datetime.fromtimestamp(f.mtime).strftime("%Y-%m-%d %H:%M")
        print(
            f"{f.name:<30} {f.category:<14} "
            f"{human_readable_size(f.size):>10}  {mtime_str:<16}"
        )


# ---------------------------------------------------------------------------
# Categorizers
# ---------------------------------------------------------------------------

def categorize_by_extension(files: list[FileInfo], base_dir: str) -> list[tuple[FileInfo, str]]:
    """Return list of (FileInfo, destination_path) for extension-based organisation."""
    result: list[tuple[FileInfo, str]] = []
    for f in files:
        category = EXTENSION_MAP.get(f.extension, "Other")
        dest_dir = os.path.join(base_dir, category)
        result.append((f, os.path.join(dest_dir, f.name)))
    return result


def categorize_by_date(files: list[FileInfo], base_dir: str) -> list[tuple[FileInfo, str]]:
    """Return list of (FileInfo, destination_path) for date-based organisation."""
    result: list[tuple[FileInfo, str]] = []
    for f in files:
        dt = datetime.fromtimestamp(f.mtime)
        dest_dir = os.path.join(base_dir, str(dt.year), f"{dt.month:02d}")
        result.append((f, os.path.join(dest_dir, f.name)))
    return result


def categorize_by_size(files: list[FileInfo], base_dir: str) -> list[tuple[FileInfo, str]]:
    """Return list of (FileInfo, destination_path) for size-based organisation."""
    result: list[tuple[FileInfo, str]] = []
    for f in files:
        category = "Large"
        for threshold, name in SIZE_THRESHOLDS:
            if f.size < threshold:
                category = name
                break
        dest_dir = os.path.join(base_dir, category)
        result.append((f, os.path.join(dest_dir, f.name)))
    return result


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------

def resolve_conflict(dest_path: str) -> str:
    """Return a free path by appending '_1', '_2', … before the extension."""
    if not os.path.exists(dest_path):
        return dest_path

    p = Path(dest_path)
    stem = p.stem
    suffix = p.suffix
    parent = p.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not os.path.exists(str(candidate)):
            return str(candidate)
        counter += 1


# ---------------------------------------------------------------------------
# Move & logging
# ---------------------------------------------------------------------------

def move_file(src: str, dest: str, dry_run: bool) -> str | None:
    """Move *src* to *dest*.  Return resolved destination path, or None on error.

    If *dry_run* is True, only print what would happen.
    """
    resolved = resolve_conflict(dest)

    if dry_run:
        if src != resolved:
            print(f"Would move: '{src}' -> '{resolved}' (conflict resolved)")
        else:
            print(f"Would move: '{src}' -> '{resolved}'")
        return resolved

    try:
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        shutil.move(src, resolved)
        return resolved
    except (PermissionError, OSError) as exc:
        print(f"Warning: cannot move '{src}' to '{resolved}': {exc}", file=sys.stderr)
        return None


def load_log(base_dir: str) -> list[dict]:
    """Load the JSON operation log.  Returns empty list if absent or corrupt."""
    log_path = os.path.join(base_dir, LOG_FILENAME)
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, "r") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, PermissionError):
        return []


def save_log(base_dir: str, entries: list[dict]) -> None:
    """Persist the log to disk."""
    log_path = os.path.join(base_dir, LOG_FILENAME)
    with open(log_path, "w") as fh:
        json.dump(entries, fh, indent=2)


def log_operation(base_dir: str, batch_id: str, source: str, dest: str) -> None:
    """Append a single move record to the JSON log."""
    entries = load_log(base_dir)
    entries.append({
        "batch_id": batch_id,
        "source": source,
        "destination": dest,
        "timestamp": datetime.now().isoformat(),
    })
    save_log(base_dir, entries)


# ---------------------------------------------------------------------------
# Organisation loop
# ---------------------------------------------------------------------------

def perform_organization(
    plan: list[tuple[FileInfo, str]],
    dry_run: bool,
    base_dir: str,
    batch_id: str,
) -> dict[str, int]:
    """Execute (or simulate) the moves in *plan*.

    Returns a dict mapping destination directory -> count of files moved.
    """
    total = len(plan)
    counts: dict[str, int] = {}

    for idx, (fi, dest) in enumerate(plan, start=1):
        # Progress indicator
        if total > PROGRESS_THRESHOLD and (idx % PROGRESS_INTERVAL == 0 or idx == total):
            print(f"\rMoving file {idx} of {total}…  ", end="", flush=True)

        moved_to = move_file(fi.path, dest, dry_run)
        if moved_to is not None:
            dest_dir = os.path.dirname(moved_to)
            counts[dest_dir] = counts.get(dest_dir, 0) + 1
            if not dry_run:
                log_operation(base_dir, batch_id, fi.path, moved_to)

    if total > PROGRESS_THRESHOLD:
        print()  # finish the progress line

    return counts


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(counts: dict[str, int], dry_run: bool) -> None:
    """Print a table showing files per destination directory."""
    if not counts:
        print("No files to organize.")
        return

    action = "Would be moved" if dry_run else "Moved"
    print(f"\n{'='*60}")
    print(f"  Summary ({action}):")
    print(f"{'-'*60}")
    total = 0
    for dest_dir in sorted(counts.keys()):
        c = counts[dest_dir]
        print(f"  {dest_dir:<50} {c:>6} file(s)")
        total += c
    print(f"{'-'*60}")
    print(f"  {'TOTAL':<50} {total:>6} file(s)")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

def undo_last(base_dir: str) -> None:
    """Undo the most recent batch of moves recorded in the log."""
    entries = load_log(base_dir)

    if not entries:
        print("Nothing to undo – the operation log is empty.")
        return

    # Find the most recent batch_id
    batches: dict[str, list[dict]] = {}
    for e in entries:
        bid = e.get("batch_id", "unknown")
        batches.setdefault(bid, []).append(e)

    # Sort batch_ids by the maximum timestamp in each batch (most recent first)
    def batch_max_ts(bid: str) -> str:
        return max(e.get("timestamp", "") for e in batches[bid])

    sorted_bids = sorted(batches.keys(), key=batch_max_ts, reverse=True)
    last_bid = sorted_bids[0]
    batch_entries = batches[last_bid]

    print(f"Undoing batch '{last_bid}' ({len(batch_entries)} file(s))…")

    restored = 0
    for e in reversed(batch_entries):  # reverse to handle nested dirs correctly
        src = e["destination"]  # where the file currently is
        dst = e["source"]       # where it should go back to

        if not os.path.exists(src):
            print(f"  Warning: file no longer exists at '{src}', skipping.")
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            # If destination already exists, resolve conflict
            resolved_dst = resolve_conflict(dst)
            shutil.move(src, resolved_dst)
            if resolved_dst != dst:
                print(f"  Restored: '{src}' -> '{resolved_dst}' (renamed)")
            else:
                print(f"  Restored: '{src}' -> '{resolved_dst}'")
            restored += 1
        except (PermissionError, OSError) as exc:
            print(f"  Warning: cannot undo '{src}': {exc}", file=sys.stderr)

    # Remove the undone batch from the log
    remaining = [e for e in entries if e.get("batch_id") != last_bid]
    save_log(base_dir, remaining)

    print(f"Undo complete: {restored} file(s) restored.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by extension, date, or size.",
    )
    parser.add_argument(
        "directory",
        help="Target directory path to organize.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--by-date",
        action="store_true",
        help="Organize files by modification date (year/month).",
    )
    group.add_argument(
        "--by-size",
        action="store_true",
        help="Organize files by size: Small / Medium / Large.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without actually moving files.",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last organization operation recorded in the log.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve target directory
    target = os.path.abspath(args.directory)

    if not os.path.isdir(target):
        print(f"Error: '{target}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # --undo mode
    if args.undo:
        undo_last(target)
        return

    # Determine categorizer
    if args.by_date:
        categorizer = categorize_by_date
    elif args.by_size:
        categorizer = categorize_by_size
    else:
        categorizer = categorize_by_extension

    # Scan
    files = scan_directory(target)

    if not files:
        print("No files found to organize (hidden and directory entries are skipped).")
        return

    # Assign extension categories (needed for the per-file table)
    _assign_categories(files)

    # Per-file table (mandatory for normal and dry-run modes)
    print_file_table(files, target)

    # Build plan
    plan = categorizer(files, target)

    # Filter out files already in the right place
    plan = [(fi, dest) for fi, dest in plan if os.path.abspath(fi.path) != os.path.abspath(dest)]

    if not plan:
        print("All files are already organized. Nothing to do.")
        return

    # Batch ID
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")

    # Execute
    counts = perform_organization(plan, args.dry_run, target, batch_id)

    # Summary
    print_summary(counts, args.dry_run)

    if args.dry_run:
        print("\nDry-run mode: no files were actually moved.")
    else:
        print(f"\nOrganization complete.  Batch ID: {batch_id}")
        print(f"To undo, run:  python file_organizer.py '{target}' --undo")


if __name__ == "__main__":
    main()
