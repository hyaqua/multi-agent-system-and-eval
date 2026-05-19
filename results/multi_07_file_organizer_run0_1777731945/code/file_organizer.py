#!/usr/bin/env python3
"""
File Organizer — organize files by extension, date, or size.

Usage:
    python file_organizer.py [TARGET] [--by-date | --by-size] [--dry-run] [--undo]
"""

import argparse
import collections
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

# ---------------------------------------------------------------------------
# Named tuple for representing a file discovered during scanning
# ---------------------------------------------------------------------------
FileItem = collections.namedtuple("FileItem", ["name", "path", "size", "mtime", "ext"])

# ---------------------------------------------------------------------------
# Extension → category mapping (all lower-case keys)
# ---------------------------------------------------------------------------
EXTENSION_CATEGORY_MAP = {
    # Images
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".bmp": "Images",
    ".tiff": "Images",
    ".tif": "Images",
    ".svg": "Images",
    ".webp": "Images",
    ".ico": "Images",
    ".heic": "Images",
    ".heif": "Images",
    ".raw": "Images",
    # Documents
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".txt": "Documents",
    ".rtf": "Documents",
    ".odt": "Documents",
    ".ods": "Documents",
    ".odp": "Documents",
    ".md": "Documents",
    ".csv": "Documents",
    ".log": "Documents",
    # Audio
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".wma": "Audio",
    ".m4a": "Audio",
    ".opus": "Audio",
    # Video
    ".mp4": "Video",
    ".mov": "Video",
    ".avi": "Video",
    ".mkv": "Video",
    ".wmv": "Video",
    ".flv": "Video",
    ".webm": "Video",
    ".m4v": "Video",
    ".mpg": "Video",
    ".mpeg": "Video",
    # Code
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".html": "Code",
    ".css": "Code",
    ".json": "Code",
    ".xml": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".h": "Code",
    ".java": "Code",
    ".rs": "Code",
    ".go": "Code",
    ".rb": "Code",
    ".sh": "Code",
    ".bat": "Code",
    ".sql": "Code",
    ".toml": "Code",
    ".ini": "Code",
    ".cfg": "Code",
    # Archives
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".7z": "Archives",
    ".rar": "Archives",
    ".xz": "Archives",
}

# ---------------------------------------------------------------------------
# Size thresholds (in bytes)
# ---------------------------------------------------------------------------
SIZE_SMALL_MAX = 1_000_000        # ≤ 1 MB
SIZE_MEDIUM_MAX = 100_000_000     # ≤ 100 MB,  > 1 MB
# Large: > 100 MB


# ===================================================================
# Utility helpers
# ===================================================================

def human_readable_size(size_bytes: int) -> str:
    """Convert a byte count to a human-readable string (e.g., '1.23 KB')."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def get_category(ext: str) -> str:
    """Return the category name for *ext* (lowercased extension, including dot)."""
    return EXTENSION_CATEGORY_MAP.get(ext, "Other")


def is_hidden(entry: os.DirEntry) -> bool:
    """Return True if the entry name starts with a dot."""
    return entry.name.startswith(".")


def resolve_conflict(dest_path: pathlib.Path) -> pathlib.Path:
    """
    If *dest_path* already exists, generate a unique name by appending _1, _2, ...
    before the extension.  Returns a path that is guaranteed **not** to exist
    at the time of the call (subject to TOCTOU, but acceptable here).
    """
    if not dest_path.exists():
        return dest_path

    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# ===================================================================
# Operation logger — persists a JSON log in a safe location (home / temp)
# ===================================================================


class OperationLogger:
    """Manages a JSON log file recording file-organisation runs.

    The log is **never** stored inside the target directory.  Instead the
    class derives a stable filename from the absolute target path and writes
    into the user's home directory or, as a fallback, the system temp dir.
    """

    def __init__(self, target_dir: pathlib.Path):
        self.log_path: pathlib.Path | None = None
        self.log_disabled = False
        self._data: dict = {"runs": []}
        self._determine_log_path(target_dir)
        if not self.log_disabled:
            self._data = self._load()

    # ------------------------------------------------------------------
    def _determine_log_path(self, target_dir: pathlib.Path) -> None:
        """Compute a stable, safe log-file location **outside** the target.

        The path is derived from a SHA-256 hash of the resolved target
        directory so that the same target always maps to the same log.
        Preference: ``Path.home()``, fallback: system temp directory.
        If neither is writable, logging is disabled.
        """
        resolved = str(target_dir.resolve())
        hash_suffix = hashlib.sha256(resolved.encode()).hexdigest()[:16]
        filename = f".file_organizer_log_{hash_suffix}.json"

        # Try home directory first
        candidate = pathlib.Path.home() / filename
        if self._path_is_writable(candidate):
            self.log_path = candidate
            return

        # Fall back to system temp directory
        candidate = pathlib.Path(tempfile.gettempdir()) / filename
        if self._path_is_writable(candidate):
            self.log_path = candidate
            return

        # Cannot write anywhere – disable logging
        self.log_disabled = True
        self.log_path = None
        print(
            "Warning: cannot write log file to home or temp directory; "
            "logging disabled. Undo will not be available.",
            file=sys.stderr,
        )

    @staticmethod
    def _path_is_writable(candidate: pathlib.Path) -> bool:
        """Return True if we can create/write *candidate*'s parent directory."""
        parent = candidate.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            # Try a quick write test
            test_file = candidate.with_suffix(".tmp")
            test_file.write_text("")
            test_file.unlink()
            return True
        except (PermissionError, OSError):
            return False

    # ------------------------------------------------------------------
    def _load(self) -> dict:
        """Load existing log data from disk, or return empty skeleton."""
        if self.log_disabled or self.log_path is None:
            return {"runs": []}
        try:
            with open(self.log_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"runs": []}

    # ------------------------------------------------------------------
    def _save(self) -> None:
        """Write in-memory log data back to disk (graceful on failure)."""
        if self.log_disabled or self.log_path is None:
            return
        try:
            with open(self.log_path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except (PermissionError, OSError) as exc:
            print(f"Warning: cannot write log file: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    def start_run(self) -> dict:
        """Create a new run entry, append to 'runs', and return it."""
        run = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operations": [],
        }
        if not self.log_disabled:
            self._data["runs"].append(run)
        return run

    # ------------------------------------------------------------------
    def log_operation(self, run: dict, source: str, dest: str) -> None:
        """Record a single move inside *run* (no-op when logging disabled)."""
        if self.log_disabled:
            return
        run["operations"].append({"source": source, "dest": dest})

    # ------------------------------------------------------------------
    def commit(self) -> None:
        """Persist the current state of the log."""
        self._save()

    # ------------------------------------------------------------------
    def last_run(self) -> dict | None:
        """Return the most recent run, or None."""
        runs = self._data.get("runs", [])
        return runs[-1] if runs else None

    # ------------------------------------------------------------------
    def pop_last_run(self) -> dict | None:
        """Remove and return the most recent run, or None."""
        runs = self._data.get("runs", [])
        if not runs:
            return None
        run = runs.pop()
        self._save()
        return run

    # ------------------------------------------------------------------
    def undo_last_run(self, target_dir: pathlib.Path) -> int:
        """
        Reverse the most recent logged run by moving each file from its
        `dest` back to its `source`.  Returns the number of undone moves.
        """
        run = self.pop_last_run()
        if run is None:
            print("Nothing to undo — the log is empty.")
            return 0

        ops = run.get("operations", [])
        print(f"Undoing {len(ops)} operation(s) from {run.get('timestamp', '?')} …")
        undone = 0
        for op in reversed(ops):
            src = pathlib.Path(op["source"])
            dst = pathlib.Path(op["dest"])
            try:
                if not dst.exists():
                    print(f"  Warning: destination file no longer exists, skipping: {dst}")
                    continue
                # If the original source spot is occupied, create a restored variant.
                if src.exists():
                    restored = pathlib.Path(str(src.parent / src.stem) + "_restored" + src.suffix)
                    restored = resolve_conflict(restored)
                    print(f"  Conflict at original source — restoring to: {restored.name}")
                    shutil.move(str(dst), str(restored))
                else:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
                undone += 1
            except PermissionError:
                print(f"  Warning: permission denied, cannot move: {dst}")
            except OSError as exc:
                print(f"  Warning: {exc}")
        # Clean up empty directories that were created during organization.
        # We walk bottom-up inside the categories that *might* have been created.
        self._cleanup_empty_dirs(target_dir)

        # The run was already popped & saved; we still need to save final state.
        self._save()
        return undone

    # ------------------------------------------------------------------
    @staticmethod
    def _cleanup_empty_dirs(root: pathlib.Path) -> None:
        """Remove empty sub-directories under *root* (excluding root itself)."""
        try:
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                dp = pathlib.Path(dirpath)
                if dp == root:
                    continue
                try:
                    # Only remove if truly empty (os.walk may have stale info)
                    if not any(dp.iterdir()):
                        dp.rmdir()
                except OSError:
                    pass  # not empty, or permission issue — ignore
        except PermissionError:
            pass


# ===================================================================
# File organizer
# ===================================================================

class FileOrganizer:
    """
    Scans a directory and produces move-plans for the three organisation
    rules: by-extension (default), by-date, by-size.
    """

    def __init__(self, target: pathlib.Path, rule: str = "extension"):
        self.target = target
        self.rule = rule  # "extension" | "date" | "size"
        self.files: list[FileItem] = []

    # ------------------------------------------------------------------
    # SCANNING
    # ------------------------------------------------------------------
    def scan_files(self) -> list[FileItem]:
        """
        Scan *self.target* non-recursively for regular files, skipping hidden
        entries and logging permission errors.  Populates *self.files*.
        """
        self.files = []
        print(f"Scanning directory: {self.target}")

        try:
            entries = list(os.scandir(self.target))
        except PermissionError:
            print(f"Error: permission denied reading directory: {self.target}")
            return []
        except OSError as exc:
            print(f"Error: cannot read directory: {exc}")
            return []

        total_entries = len(entries)
        show_progress = total_entries > 50
        count = 0
        processed = 0

        for entry in entries:
            processed += 1
            if show_progress and processed % 10 == 0:
                self._progress("Scanning", processed, total_entries)

            # Skip hidden files/directories
            if is_hidden(entry):
                continue
            # We only want regular files
            if not entry.is_file(follow_symlinks=False):
                continue

            try:
                stat = entry.stat()
            except PermissionError:
                print(f"\n  Warning: cannot stat file (permission denied): {entry.name}")
                continue
            except OSError as exc:
                print(f"\n  Warning: cannot stat file ({exc}): {entry.name}")
                continue

            name = entry.name
            path = entry.path
            size = stat.st_size
            mtime = stat.st_mtime
            ext = pathlib.Path(name).suffix.lower()

            self.files.append(FileItem(name=name, path=path, size=size, mtime=mtime, ext=ext))
            count += 1

        if show_progress:
            self._progress("Scanning", total_entries, total_entries, done=True)
        print(f"Found {len(self.files)} file(s) to process.\n")
        return self.files

    # ------------------------------------------------------------------
    # PLAN GENERATION
    # ------------------------------------------------------------------
    def build_plan(self) -> list[tuple[pathlib.Path, pathlib.Path]]:
        """
        Build a list of (source_path, dest_path) tuples according to the
        configured rule.  No filesystem changes are made here.
        """
        if self.rule == "extension":
            return self._plan_by_extension()
        elif self.rule == "date":
            return self._plan_by_date()
        elif self.rule == "size":
            return self._plan_by_size()
        else:
            raise ValueError(f"Unknown rule: {self.rule}")

    # ------------------------------------------------------------------
    def _plan_by_extension(self) -> list[tuple[pathlib.Path, pathlib.Path]]:
        plan = []
        for item in self.files:
            category = get_category(item.ext)
            dest_dir = self.target / category
            dest = dest_dir / item.name
            plan.append((pathlib.Path(item.path), dest))
        return plan

    # ------------------------------------------------------------------
    def _plan_by_date(self) -> list[tuple[pathlib.Path, pathlib.Path]]:
        plan = []
        for item in self.files:
            dt = datetime.datetime.fromtimestamp(item.mtime)
            year = f"{dt.year:04d}"
            month = f"{dt.month:02d}"
            dest_dir = self.target / year / month
            dest = dest_dir / item.name
            plan.append((pathlib.Path(item.path), dest))
        return plan

    # ------------------------------------------------------------------
    def _plan_by_size(self) -> list[tuple[pathlib.Path, pathlib.Path]]:
        plan = []
        for item in self.files:
            if item.size <= SIZE_SMALL_MAX:
                bucket = "Small"
            elif item.size <= SIZE_MEDIUM_MAX:
                bucket = "Medium"
            else:
                bucket = "Large"
            dest_dir = self.target / bucket
            dest = dest_dir / item.name
            plan.append((pathlib.Path(item.path), dest))
        return plan

    # ------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------
    def execute_plan(
        self,
        plan: list[tuple[pathlib.Path, pathlib.Path]],
        logger: OperationLogger,
    ) -> int:
        """
        Execute the move operations in *plan*:
          - Create destination directories on demand.
          - Resolve filename conflicts.
          - Log every successful move via *logger*.
        Returns the number of files actually moved.
        """
        run = logger.start_run()
        total = len(plan)
        moved = 0
        show_progress = total > 50

        for idx, (src, dest) in enumerate(plan, start=1):
            if show_progress and idx % 10 == 0:
                self._progress("Moving", idx, total)

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                print(f"\n  Warning: cannot create directory (permission denied): {dest.parent}")
                continue
            except OSError as exc:
                print(f"\n  Warning: cannot create directory ({exc}): {dest.parent}")
                continue

            # Resolve naming conflicts
            resolved_dest = resolve_conflict(dest)

            try:
                shutil.move(str(src), str(resolved_dest))
            except PermissionError:
                print(f"\n  Warning: permission denied moving: {src.name}")
                continue
            except OSError as exc:
                print(f"\n  Warning: cannot move {src.name} — {exc}")
                continue

            logger.log_operation(run, str(src), str(resolved_dest))
            moved += 1

        if show_progress:
            self._progress("Moving", total, total, done=True)

        logger.commit()
        return moved

    # ------------------------------------------------------------------
    # DRY-RUN REPORT
    # ------------------------------------------------------------------
    def dry_run_report(self, plan: list[tuple[pathlib.Path, pathlib.Path]]) -> None:
        """Print a summary of what *would* happen without moving files."""
        print("=== DRY-RUN REPORT ===")
        print(f"Rule: {self.rule}")
        print(f"Files that would be moved: {len(plan)}\n")

        # Aggregate by destination directory prefix (the immediate parent
        # relative to the target, or two-level for date-based).
        buckets: dict[str, list[str]] = {}

        for src, dest in plan:
            # Determine the logical "bucket" name for display.
            if self.rule == "date":
                # dest.parent.parent  → year, dest.parent → month
                rel = dest.relative_to(self.target)
                bucket_key = str(rel.parent)  # e.g. "2025/04"
            elif self.rule in ("extension", "size"):
                rel = dest.relative_to(self.target)
                bucket_key = rel.parts[0]  # e.g. "Images" or "Large"
            else:
                bucket_key = "unknown"

            buckets.setdefault(bucket_key, []).append(dest.name)

        # Print summary table
        col1_width = max(len(k) for k in buckets.keys()) if buckets else 10
        col1_width = max(col1_width, 8)
        print(f"{'Category':<{col1_width}}  Count")
        print("-" * (col1_width + 8))
        for bucket in sorted(buckets.keys()):
            print(f"{bucket:<{col1_width}}  {len(buckets[bucket])}")
        print("-" * (col1_width + 8))
        total_size = sum(f.size for f in self.files)
        print(f"{'TOTAL':<{col1_width}}  {len(plan)} file(s), {human_readable_size(total_size)}")

    # ------------------------------------------------------------------
    # REPORT AFTER REAL EXECUTION
    # ------------------------------------------------------------------
    def execution_report(self, moved: int, plan: list[tuple[pathlib.Path, pathlib.Path]]) -> None:
        """Print summary after files have been moved."""
        print("\n=== ORGANIZATION COMPLETE ===")
        print(f"Rule: {self.rule}")
        print(f"Files processed: {len(plan)}")
        print(f"Files moved: {moved}")
        if len(plan) - moved > 0:
            print(f"Files skipped (errors): {len(plan) - moved}")

    # ------------------------------------------------------------------
    @staticmethod
    def _progress(label: str, current: int, total: int, done: bool = False) -> None:
        """Print/update a progress line on stderr."""
        sys.stderr.write(f"\r{label} file {current}/{total}  ")
        sys.stderr.flush()
        if done:
            sys.stderr.write("\n")


# ===================================================================
# CLI
# ===================================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by extension, date, or size.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_organizer.py ~/Downloads
  python file_organizer.py . --by-date --dry-run
  python file_organizer.py /tmp/stuff --by-size
  python file_organizer.py . --undo
        """,
    )

    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target directory to organize (default: current directory).",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--by-date",
        action="store_true",
        help="Organize files by modification date into year/month subdirectories.",
    )
    group.add_argument(
        "--by-size",
        action="store_true",
        help="Organize files by size into Small/Medium/Large subdirectories.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without actually moving any files.",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the most recent organization operation using the log file.",
    )

    return parser.parse_args(argv)


def validate_target(raw: str) -> pathlib.Path:
    target = pathlib.Path(raw).resolve()
    if not target.exists():
        sys.exit(f"Error: target directory does not exist: {target}")
    if not target.is_dir():
        sys.exit(f"Error: target path is not a directory: {target}")
    return target


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    target = validate_target(args.target)

    # ------------------------------------------------------------------
    # Undo mode — handled separately
    # ------------------------------------------------------------------
    if args.undo:
        logger = OperationLogger(target)
        undone = logger.undo_last_run(target)
        print(f"Undo complete — {undone} file(s) restored.")
        return

    # ------------------------------------------------------------------
    # Determine the organization rule
    # ------------------------------------------------------------------
    if args.by_date:
        rule = "date"
    elif args.by_size:
        rule = "size"
    else:
        rule = "extension"

    # ------------------------------------------------------------------
    # Scan files
    # ------------------------------------------------------------------
    organizer = FileOrganizer(target, rule=rule)
    files = organizer.scan_files()

    if not files:
        print("No files to organize.")
        return

    # ------------------------------------------------------------------
    # Build move plan
    # ------------------------------------------------------------------
    plan = organizer.build_plan()

    if not plan:
        print("No moves to perform.")
        return

    # ------------------------------------------------------------------
    # Dry-run mode
    # ------------------------------------------------------------------
    if args.dry_run:
        organizer.dry_run_report(plan)
        return

    # ------------------------------------------------------------------
    # Execute moves
    # ------------------------------------------------------------------
    logger = OperationLogger(target)
    moved = organizer.execute_plan(plan, logger)
    organizer.execution_report(moved, plan)


if __name__ == "__main__":
    main()
