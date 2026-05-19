#!/usr/bin/env python3
"""
File Organizer - A command-line file system organizer.

Organizes files in a target directory into subdirectories based on
configurable rules: by file type, modification date, or file size.

Supports dry-run mode, undo, conflict resolution, and progress reporting.
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ── Category definitions ──────────────────────────────────────────────

EXTENSION_CATEGORIES = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".tiff": "Images", ".tif": "Images", ".webp": "Images",
    ".svg": "Images", ".ico": "Images", ".heic": "Images", ".heif": "Images",
    ".raw": "Images", ".cr2": "Images", ".nef": "Images", ".psd": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".txt": "Documents", ".md": "Documents",
    ".csv": "Documents", ".rtf": "Documents", ".odt": "Documents",
    ".ods": "Documents", ".odp": "Documents", ".epub": "Documents",
    ".mobi": "Documents", ".pages": "Documents", ".numbers": "Documents",
    ".key": "Documents", ".tex": "Documents",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".wma": "Audio", ".m4a": "Audio", ".opus": "Audio",
    ".mid": "Audio", ".midi": "Audio", ".aiff": "Audio", ".alac": "Audio",
    # Video
    ".mp4": "Video", ".avi": "Video", ".mkv": "Video", ".mov": "Video",
    ".wmv": "Video", ".flv": "Video", ".webm": "Video", ".m4v": "Video",
    ".mpg": "Video", ".mpeg": "Video", ".3gp": "Video", ".ogv": "Video",
    # Code
    ".py": "Code", ".js": "Code", ".html": "Code", ".htm": "Code",
    ".css": "Code", ".java": "Code", ".cpp": "Code", ".c": "Code",
    ".h": "Code", ".hpp": "Code", ".json": "Code", ".xml": "Code",
    ".yaml": "Code", ".yml": "Code", ".sh": "Code", ".bash": "Code",
    ".bat": "Code", ".ps1": "Code", ".ts": "Code", ".jsx": "Code",
    ".tsx": "Code", ".rs": "Code", ".go": "Code", ".rb": "Code",
    ".php": "Code", ".sql": "Code", ".r": "Code", ".swift": "Code",
    ".kt": "Code", ".scala": "Code", ".lua": "Code", ".pl": "Code",
    ".ino": "Code", ".toml": "Code", ".cfg": "Code", ".ini": "Code",
    ".makefile": "Code", ".cmake": "Code", ".dockerfile": "Code",
    # Archives
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".bz2": "Archives", ".xz": "Archives", ".7z": "Archives",
    ".rar": "Archives", ".tgz": "Archives", ".lz": "Archives",
}

# Size thresholds in bytes
SIZE_SMALL_MAX = 1_048_576        # 1 MB
SIZE_MEDIUM_MAX = 104_857_600     # 100 MB


def get_category_by_extension(ext: str) -> str:
    """Return the category name for a given file extension."""
    ext_lower = ext.lower()
    return EXTENSION_CATEGORIES.get(ext_lower, "Other")


def get_category_by_size(size_bytes: int) -> str:
    """Return the size category for a given file size in bytes."""
    if size_bytes < SIZE_SMALL_MAX:
        return "Small"
    elif size_bytes < SIZE_MEDIUM_MAX:
        return "Medium"
    else:
        return "Large"


def get_category_by_date(mtime: float) -> str:
    """Return year/month subdirectory path based on modification time."""
    dt = datetime.fromtimestamp(mtime)
    return f"{dt.year:04d}/{dt.month:02d}"


def format_size(size_bytes: int) -> str:
    """Format a byte size into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1_048_576:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1_073_741_824:
        return f"{size_bytes / 1_048_576:.1f} MB"
    else:
        return f"{size_bytes / 1_073_741_824:.1f} GB"


# ── File scanner ──────────────────────────────────────────────────────

def scan_files(target_dir: Path) -> list[dict]:
    """
    Scan the target directory and return a list of file info dicts.
    Skips hidden files/dirs and the organizer's own log files.
    """
    files = []
    try:
        entries = sorted(target_dir.iterdir())
    except PermissionError as e:
        print(f"WARNING: Cannot read directory '{target_dir}': {e}", file=sys.stderr)
        return files
    except OSError as e:
        print(f"WARNING: OS error reading '{target_dir}': {e}", file=sys.stderr)
        return files

    for entry in entries:
        # Skip hidden files and directories
        if entry.name.startswith('.'):
            continue

        # Skip the organizer's own log files
        if entry.name.startswith('organizer_log_') and entry.name.endswith('.json'):
            continue

        try:
            if entry.is_file():
                stat = entry.stat()
                files.append({
                    'path': entry,
                    'name': entry.name,
                    'size': stat.st_size,
                    'mtime': stat.st_mtime,
                    'ext': entry.suffix,
                })
            elif entry.is_dir():
                # Skip directories that look like organizer output (e.g. "Images", "Documents", etc.)
                known_categories = set(EXTENSION_CATEGORIES.values())
                known_categories.update(["Small", "Medium", "Large", "Other", "Archives"])
                # Also skip year-pattern dirs (4 digits)
                is_year_dir = entry.name.isdigit() and len(entry.name) == 4
                is_month_dir = entry.name.isdigit() and len(entry.name) == 2
                if entry.name not in known_categories and not is_year_dir and not is_month_dir:
                    # Recurse into non-organizer subdirectories
                    files.extend(scan_files(entry))
        except PermissionError as e:
            print(f"WARNING: Permission denied accessing '{entry}': {e}", file=sys.stderr)
        except OSError as e:
            print(f"WARNING: Cannot access '{entry}': {e}", file=sys.stderr)

    return files


# ── Progress indicator ────────────────────────────────────────────────

class ProgressIndicator:
    """Simple progress indicator that prints to stderr."""

    def __init__(self, total: int, label: str = "Processing"):
        self.total = total
        self.current = 0
        self.label = label
        self.start_time = time.time()
        self.bar_width = 40
        self._last_update = 0

    def update(self, n: int = 1):
        """Advance progress by n steps."""
        self.current += n
        now = time.time()
        # Throttle updates to ~10 per second
        if now - self._last_update < 0.1 and self.current < self.total:
            return
        self._last_update = now
        self._print()

    def _print(self):
        if self.total == 0:
            return
        pct = self.current / self.total
        filled = int(self.bar_width * pct)
        bar = "█" * filled + "░" * (self.bar_width - filled)
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = ""
        print(
            f"\r  {self.label} [{bar}] {self.current}/{self.total} "
            f"({pct * 100:.0f}%) {eta_str}   ",
            end="", file=sys.stderr, flush=True
        )

    def finish(self):
        """Complete the progress display."""
        self._last_update = 0
        self.current = self.total
        self._print()
        print(file=sys.stderr)


# ── Conflict resolution ───────────────────────────────────────────────

def resolve_conflict(dest_path: Path) -> Path:
    """
    If dest_path already exists, append a numeric suffix like file_1.txt, file_2.txt.
    Returns a non-conflicting path.
    """
    if not dest_path.exists():
        return dest_path

    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent
    counter = 1

    # Check if stem already ends with _N pattern
    # We'll just append our own counter regardless
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1
        if counter > 10000:
            # Safety limit
            raise FileExistsError(f"Too many conflicts for {dest_path}")


# ── Core organizer ────────────────────────────────────────────────────

class FileOrganizer:
    """Handles scanning, planning, and executing file organization."""

    def __init__(self, target_dir: Path, dry_run: bool = False,
                 by_date: bool = False, by_size: bool = False):
        self.target_dir = target_dir.resolve()
        self.dry_run = dry_run
        self.by_date = by_date
        self.by_size = by_size
        self.operations: list[dict] = []
        self.summary: dict[str, int] = defaultdict(int)

    def get_destination(self, file_info: dict) -> Path:
        """Determine the destination subdirectory and filename for a file."""
        if self.by_date:
            subdir = get_category_by_date(file_info['mtime'])
        elif self.by_size:
            subdir = get_category_by_size(file_info['size'])
        else:
            subdir = get_category_by_extension(file_info['ext'])

        dest_dir = self.target_dir / subdir
        dest_path = dest_dir / file_info['name']

        # Resolve conflicts
        dest_path = resolve_conflict(dest_path)

        return dest_path

    def plan(self, files: list[dict]) -> list[dict]:
        """Build a list of planned move operations."""
        planned = []
        seen_destinations: set[Path] = set()

        for fi in files:
            dest = self.get_destination(fi)

            # Resolve conflicts against both existing files and planned destinations
            dest = self._resolve_all_conflicts(dest, seen_destinations)

            seen_destinations.add(dest)

            planned.append({
                'source': str(fi['path']),
                'destination': str(dest),
                'action': 'move',
            })

            self.summary[str(dest.parent.relative_to(self.target_dir))] += 1

        self.operations = planned
        return planned

    def _resolve_all_conflicts(self, dest: Path, seen: set[Path]) -> Path:
        """Resolve conflicts against filesystem and already-planned destinations."""
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        counter = 1

        while dest.exists() or dest in seen:
            dest = parent / f"{stem}_{counter}{suffix}"
            counter += 1
            if counter > 10000:
                raise FileExistsError(f"Too many conflicts for {parent / stem}{suffix}")

        return dest

    def execute(self) -> bool:
        """Execute the planned operations. Returns True on success."""
        if not self.operations:
            print("No files to organize.")
            return True

        if self.dry_run:
            print("\n[Dry-run] The following operations would be performed:\n")
            for op in self.operations:
                src_rel = Path(op['source']).relative_to(self.target_dir)
                dst_rel = Path(op['destination']).relative_to(self.target_dir)
                print(f"  {src_rel}  →  {dst_rel}")
            print()
            return True

        # Create all needed destination directories first
        dest_dirs = {Path(op['destination']).parent for op in self.operations}
        for d in dest_dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(f"ERROR: Cannot create directory '{d}': {e}", file=sys.stderr)
                return False

        progress = ProgressIndicator(len(self.operations), label="Moving files")

        success_count = 0
        fail_count = 0
        executed_ops = []  # Track successfully executed ops for logging

        for op in self.operations:
            src = Path(op['source'])
            dst = Path(op['destination'])

            # Re-check conflict at execution time (in case files appeared)
            dst = resolve_conflict(dst)

            try:
                shutil.move(str(src), str(dst))
                executed_ops.append({
                    'source': str(src),
                    'destination': str(dst),
                    'action': 'move',
                })
                success_count += 1
            except PermissionError as e:
                print(f"\nWARNING: Permission denied moving '{src.name}': {e}", file=sys.stderr)
                fail_count += 1
            except OSError as e:
                print(f"\nWARNING: Cannot move '{src.name}': {e}", file=sys.stderr)
                fail_count += 1

            progress.update(1)

        progress.finish()

        # Log to JSON
        self._write_log(executed_ops)

        print(f"\nDone! {success_count} files moved, {fail_count} failed.")
        return fail_count == 0

    def _write_log(self, executed_ops: list[dict]):
        """Write operation log to a JSON file in the target directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.target_dir / f"organizer_log_{timestamp}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "target_directory": str(self.target_dir),
            "mode": "date" if self.by_date else ("size" if self.by_size else "type"),
            "operations": executed_ops,
        }

        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2)
            print(f"Log written to: {log_path.name}")
        except OSError as e:
            print(f"WARNING: Could not write log file: {e}", file=sys.stderr)

    def print_summary(self):
        """Print a summary of planned operations."""
        if not self.summary:
            print("No files to organize.")
            return

        print("\n── Summary ──")
        total = sum(self.summary.values())
        for dest, count in sorted(self.summary.items()):
            print(f"  {dest}: {count} file(s)")
        print(f"  ─────────────────────")
        print(f"  Total: {total} file(s)")
        print()

        if self.dry_run:
            print("[Dry-run mode] No files were actually moved.")


# ── Undo functionality ────────────────────────────────────────────────

def undo_last_operation(target_dir: Path) -> bool:
    """
    Find the most recent organizer log in the target directory
    and reverse all operations in it.
    """
    log_files = sorted(target_dir.glob("organizer_log_*.json"))
    if not log_files:
        print("No organizer log found in this directory. Nothing to undo.")
        return False

    latest_log = log_files[-1]

    try:
        with open(latest_log, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: Cannot read log file '{latest_log}': {e}", file=sys.stderr)
        return False

    operations = log_data.get('operations', [])
    if not operations:
        print("Log contains no operations. Nothing to undo.")
        latest_log.unlink(missing_ok=True)
        return True

    print(f"Undoing {len(operations)} operation(s) from log: {latest_log.name}")
    timestamp = log_data.get('timestamp', 'unknown')
    print(f"Original operation timestamp: {timestamp}")

    success = 0
    failed = 0

    progress = ProgressIndicator(len(operations), label="Undoing moves")

    # Reverse operations: move files back from destination to source
    for op in reversed(operations):
        src = Path(op['destination'])   # where the file was moved TO
        dst = Path(op['source'])        # where the file came FROM

        if not src.exists():
            print(f"\nWARNING: File not found (may have been moved already): {src.name}",
                  file=sys.stderr)
            failed += 1
            progress.update(1)
            continue

        # Ensure the destination parent directory exists
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"\nERROR: Cannot create directory '{dst.parent}': {e}", file=sys.stderr)
            failed += 1
            progress.update(1)
            continue

        # Handle conflict if something is already at the original location
        if dst.exists():
            dst = resolve_conflict(dst)

        try:
            shutil.move(str(src), str(dst))
            success += 1
        except PermissionError as e:
            print(f"\nWARNING: Permission denied undoing '{src.name}': {e}", file=sys.stderr)
            failed += 1
        except OSError as e:
            print(f"\nWARNING: Cannot undo move for '{src.name}': {e}", file=sys.stderr)
            failed += 1

        progress.update(1)

    progress.finish()

    # Remove the log file after successful undo
    if failed == 0:
        try:
            latest_log.unlink()
        except OSError:
            pass
    else:
        # Write updated log with remaining operations
        # Keep the log but mark it as partially undone
        print(f"Log kept (partial undo): {latest_log.name}")

    print(f"\nUndo complete: {success} files restored, {failed} failed.")
    return failed == 0


# ── List files mode ────────────────────────────────────────────────────

def list_files(target_dir: Path):
    """List all files in the target directory with type, size, and date."""
    files = scan_files(target_dir)
    if not files:
        print("No files found in the directory.")
        return

    print(f"\nFiles in: {target_dir}\n")
    print(f"{'Name':<40} {'Type':<12} {'Size':>10} {'Modified':>20}")
    print("-" * 85)

    for fi in files:
        name = fi['name'][:39]
        ext_type = fi['ext'] if fi['ext'] else "(none)"
        size_str = format_size(fi['size'])
        mtime_str = datetime.fromtimestamp(fi['mtime']).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{name:<40} {ext_type:<12} {size_str:>10} {mtime_str:>20}")

    print(f"\nTotal: {len(files)} file(s)")


# ── CLI argument parsing ──────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by type, date, or size.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Downloads                    # Organize by file type
  %(prog)s ~/Downloads --dry-run          # Preview without moving
  %(prog)s ~/Downloads --by-date          # Organize by year/month
  %(prog)s ~/Downloads --by-size          # Organize by Small/Medium/Large
  %(prog)s ~/Downloads --undo             # Undo last organization
  %(prog)s ~/Downloads --list             # List files in directory
        """
    )

    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Target directory to organize (default: current directory)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List files with type, size, and date instead of organizing'
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--by-date',
        action='store_true',
        help='Organize files by modification date into year/month subdirectories'
    )
    mode_group.add_argument(
        '--by-size',
        action='store_true',
        help='Organize files by size into Small/Medium/Large subdirectories'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would happen without moving any files'
    )

    parser.add_argument(
        '--undo',
        action='store_true',
        help='Undo the last organization operation using the log file'
    )

    return parser.parse_args()


# ── Main entry point ──────────────────────────────────────────────────

def main():
    args = parse_args()

    target_dir = Path(args.directory).resolve()

    if not target_dir.exists():
        print(f"ERROR: Directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not target_dir.is_dir():
        print(f"ERROR: '{target_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # --list mode: just show files
    if args.list:
        list_files(target_dir)
        return

    # --undo mode: reverse last operation
    if args.undo:
        success = undo_last_operation(target_dir)
        sys.exit(0 if success else 1)

    # Default: organize
    print(f"Scanning directory: {target_dir}")
    files = scan_files(target_dir)

    if not files:
        print("No files found to organize.")
        return

    print(f"Found {len(files)} file(s).")

    organizer = FileOrganizer(
        target_dir=target_dir,
        dry_run=args.dry_run,
        by_date=args.by_date,
        by_size=args.by_size,
    )

    organizer.plan(files)
    organizer.print_summary()
    organizer.execute()


if __name__ == '__main__':
    main()
