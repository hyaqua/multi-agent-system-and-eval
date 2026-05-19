"""Core Organizer: scan a directory, apply rules, resolve conflicts,
perform (or simulate) moves, and produce a summary.
"""

import os
import shutil
import sys
from typing import Callable

from rules import get_ext_category, get_date_path, get_size_category
from logger import Logger
from utils import ProgressTicker, format_size


class Organizer:
    """Orchestrates file organisation for a single directory."""

    def __init__(
        self,
        directory: str,
        *,
        dry_run: bool = False,
        by_date: bool = False,
        by_size: bool = False,
        logger: Logger | None = None,
    ):
        self._dir = os.path.abspath(directory)
        self._dry_run = dry_run
        self._by_date = by_date
        self._by_size = by_size
        self._logger = logger

        # Choose the rule function
        if by_date:
            self._rule: Callable[[str, int, float], str] = self._rule_date
        elif by_size:
            self._rule = self._rule_size
        else:
            self._rule = self._rule_ext

        # Collected file info: list of (name, size, mtime)
        self._files: list[tuple[str, int, float]] = []

    # ------------------------------------------------------------------
    # Rule helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _rule_ext(name: str, size: int, mtime: float) -> str:
        ext = os.path.splitext(name)[1].lower()
        return get_ext_category(ext)

    @staticmethod
    def _rule_date(name: str, size: int, mtime: float) -> str:
        return get_date_path(mtime)

    @staticmethod
    def _rule_size(name: str, size: int, mtime: float) -> str:
        return get_size_category(size)

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def scan(self) -> list[tuple[str, int, float]]:
        """Scan the target directory for non-hidden files.

        Returns a list of ``(name, size, mtime)`` tuples.
        Populates ``self._files`` as a side-effect.
        """
        self._files = []
        try:
            with os.scandir(self._dir) as entries:
                for entry in entries:
                    # Skip hidden files/directories
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_file(follow_symlinks=False):
                            stat = entry.stat()
                            self._files.append(
                                (entry.name, stat.st_size, stat.st_mtime)
                            )
                    except PermissionError:
                        print(
                            f"Warning: Cannot access {entry.name}",
                            file=sys.stderr,
                        )
        except PermissionError:
            print(
                f"Warning: Cannot access directory {self._dir}",
                file=sys.stderr,
            )
        except FileNotFoundError:
            print(
                f"Error: Directory not found: {self._dir}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Sort by name for consistent output
        self._files.sort(key=lambda x: x[0])
        return self._files

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def list_files(self) -> None:
        """Print a formatted table of scanned files to stdout."""
        if not self._files:
            print("No files found.")
            return
        print(f"Files in {self._dir}:\n")
        print(f"{'Name':<40} {'Type':<12} {'Size':>10}  {'Modified'}")
        print("-" * 80)
        for name, size, mtime in self._files:
            ext = os.path.splitext(name)[1].lower()
            cat = get_ext_category(ext)
            print(
                f"{name:<40} {cat:<12} {format_size(size):>10}  "
                f"{get_date_path(mtime)}"
            )
        print()

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_conflict(dest_path: str) -> str:
        """Given an intended *dest_path*, return a non-existing path by
        appending ``_1``, ``_2``, … before the extension.
        """
        if not os.path.lexists(dest_path):
            return dest_path

        root, ext = os.path.splitext(dest_path)
        counter = 1
        while True:
            candidate = f"{root}_{counter}{ext}"
            if not os.path.lexists(candidate):
                return candidate
            counter += 1

    # ------------------------------------------------------------------
    # Organize
    # ------------------------------------------------------------------
    def organize(self) -> dict[str, int]:
        """Execute moves (or simulate in dry-run mode).

        Returns a dict mapping destination folder → count of files
        moved there.
        """
        if not self._files:
            print("No files to organize.")
            return {}

        # Reset the log so that only *this* run's moves are recorded,
        # making undo reverse exactly the last organisation operation.
        if not self._dry_run and self._logger:
            self._logger.reset()

        ticker = ProgressTicker(step=10)
        summary: dict[str, int] = {}

        for name, size, mtime in self._files:
            src = os.path.join(self._dir, name)
            sub = self._rule(name, size, mtime)  # relative sub-folder
            dest_dir = os.path.join(self._dir, sub)
            dest = os.path.join(dest_dir, name)

            # Resolve conflicts
            dest = self._resolve_conflict(dest)
            # Recompute the actual dest_dir in case suffix changed dir
            actual_dest_dir = os.path.dirname(dest)
            rel_folder = os.path.relpath(actual_dest_dir, self._dir)

            if self._dry_run:
                dest_name = os.path.basename(dest)
                if dest_name != name:
                    print(
                        f"[DRY RUN] {src}  →  {actual_dest_dir}/"
                        f"  (renamed to {dest_name})"
                    )
                else:
                    print(f"[DRY RUN] {src}  →  {actual_dest_dir}/")
                summary[rel_folder] = summary.get(rel_folder, 0) + 1
                ticker.tick()
                continue

            # --- Actual move ---
            try:
                os.makedirs(actual_dest_dir, exist_ok=True)
                shutil.move(src, dest)
                if self._logger:
                    self._logger.append(src, dest)
                summary[rel_folder] = summary.get(rel_folder, 0) + 1
            except PermissionError:
                print(
                    f"Warning: Permission denied for {src}", file=sys.stderr
                )
            except OSError as exc:
                print(f"Warning: {exc}", file=sys.stderr)

            ticker.tick()

        ticker.finish()
        return summary

    # ------------------------------------------------------------------
    # Summary display
    # ------------------------------------------------------------------
    @staticmethod
    def print_summary(summary: dict[str, int]) -> None:
        """Print a count-per-destination table."""
        if not summary:
            print("\nNo files were processed.")
            return

        print("\nSummary:")
        print(f"{'Destination':<40} {'Count':>6}")
        print("-" * 48)
        for dest, count in sorted(summary.items()):
            print(f"{dest:<40} {count:>6}")
        print("-" * 48)
        print(f"{'TOTAL':<40} {sum(summary.values()):>6}")
