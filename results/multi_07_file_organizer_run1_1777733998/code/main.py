#!/usr/bin/env python3
"""file_organizer – organise files by extension, date, or size.

Usage examples
--------------

    # Show what would happen (dry-run)
    python main.py /path/to/dir --dry-run

    # Organise by extension category (default)
    python main.py /path/to/dir

    # Organise by modification date
    python main.py /path/to/dir --by-date

    # Organise by file size
    python main.py /path/to/dir --by-size

    # Undo the last operation
    python main.py /path/to/dir --undo
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

from organizer import Organizer
from logger import Logger

LOG_FILE_NAME = "organizer_log.jsonl"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Organise files in a directory by extension, date, or size."
    )
    p.add_argument(
        "directory",
        type=Path,
        help="Target directory to scan and organise.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended moves without actually moving files.",
    )
    p.add_argument(
        "--by-date",
        action="store_true",
        help="Organise files into year/month subdirectories based on "
        "modification time.",
    )
    p.add_argument(
        "--by-size",
        action="store_true",
        help="Organise files into Small/Medium/Large subdirectories "
        "based on file size.",
    )
    p.add_argument(
        "--undo",
        action="store_true",
        help="Reverse the last organisation operation using the log file.",
    )
    return p


def do_undo(directory: str) -> None:
    """Read the log and move every file back to its original location."""
    log_path = os.path.join(directory, LOG_FILE_NAME)
    logger = Logger(log_path)
    entries = logger.read_all()

    if not entries:
        print(f"No log entries found in {log_path} – nothing to undo.")
        return

    print(f"Undoing {len(entries)} operation(s)…")
    reversed_entries = list(reversed(entries))
    success = 0
    skipped = 0

    for entry in reversed_entries:
        src = entry["source"]
        dst = entry["destination"]

        if not os.path.lexists(dst):
            print(
                f"Warning: destination no longer exists, skipping: {dst}",
                file=sys.stderr,
            )
            skipped += 1
            continue

        # If the original source already exists, rename the moved-back
        # file to avoid overwriting something that was recreated.
        final_src = src
        if os.path.lexists(src):
            root, ext = os.path.splitext(src)
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            final_src = f"{root}_restored_{ts}{ext}"
            print(
                f"Note: original path already exists; renaming to "
                f"{os.path.basename(final_src)}",
                file=sys.stderr,
            )

        try:
            os.makedirs(os.path.dirname(final_src), exist_ok=True)
            shutil.move(dst, final_src)
            success += 1
        except OSError as exc:
            print(f"Warning: cannot undo {dst}: {exc}", file=sys.stderr)
            skipped += 1

    print(f"Undo complete: {success} restored, {skipped} skipped.")
    logger.clear()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    directory = str(args.directory.resolve())

    if args.undo:
        do_undo(directory)
        return

    # --by-date and --by-size are mutually exclusive with each other
    if args.by_date and args.by_size:
        print("Error: --by-date and --by-size cannot be used together.",
              file=sys.stderr)
        sys.exit(1)

    log_path = os.path.join(directory, LOG_FILE_NAME)
    logger = Logger(log_path)

    organizer = Organizer(
        directory,
        dry_run=args.dry_run,
        by_date=args.by_date,
        by_size=args.by_size,
        logger=logger,
    )

    # 1. Scan
    organizer.scan()

    # 2. List files
    organizer.list_files()

    # 3. Organize
    summary = organizer.organize()

    # 4. Summary
    if args.dry_run:
        print("\n--- Dry-run summary ---")
    organizer.print_summary(summary)


if __name__ == "__main__":
    main()
