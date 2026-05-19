"""CLI argument parsing and main entry point."""

import argparse
import os
import sys

from file_organizer.scanner import scan_directory
from file_organizer.categorizer import get_categorizer
from file_organizer.organizer import organize
from file_organizer.undo_manager import undo_last


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file_organizer",
        description="Organize files in a directory by type, date, or size.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory to organize (default: current directory).",
    )
    parser.add_argument(
        "--by-date",
        action="store_true",
        help="Organize files into year/month subdirectories based on modification date.",
    )
    parser.add_argument(
        "--by-size",
        action="store_true",
        help="Organize files into Small/Medium/Large subdirectories based on file size.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be moved without actually moving any files.",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last organization operation (reads from the log file).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = os.path.abspath(args.directory)

    if not os.path.isdir(target):
        print(f"Error: '{target}' is not a directory or does not exist.")
        sys.exit(1)

    # --undo mode: reverse last operation
    if args.undo:
        success = undo_last(target)
        sys.exit(0 if success else 1)

    # Validate flags
    if args.by_date and args.by_size:
        print("Error: --by-date and --by-size are mutually exclusive.")
        sys.exit(1)

    categorizer = get_categorizer(by_date_flag=args.by_date, by_size_flag=args.by_size)

    # Scan
    print(f"Scanning '{target}'…")
    files = scan_directory(target)

    if not files:
        print("No files found to organize.")
        return

    # Organize (or dry-run)
    organize(files, target, categorizer, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
