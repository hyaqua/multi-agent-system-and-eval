"""Command-line interface for the file organizer."""

import argparse
import shutil
import sys
from pathlib import Path

from file_organizer.scanner import scan_directory
from file_organizer.organizer import (
    compute_plan,
    execute_plan,
    display_summary,
)
from file_organizer.logger import (
    log_operations,
    get_last_run,
    pop_last_run,
    load_log,
    save_log,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='file-organizer',
        description='Organize files in a directory by type, date, or size.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  file-organizer ~/Downloads
  file-organizer ~/Downloads --by-date --dry-run
  file-organizer ~/Downloads --by-size
  file-organizer ~/Downloads --undo
        """,
    )

    parser.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='Target directory to organize (default: current directory)',
    )
    parser.add_argument(
        '--by-date',
        action='store_true',
        help='Organize files by modification date into year/month subdirectories',
    )
    parser.add_argument(
        '--by-size',
        action='store_true',
        help='Organize files by size into Small/Medium/Large subdirectories',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without actually moving files',
    )
    parser.add_argument(
        '--undo',
        action='store_true',
        help='Undo the most recent organization operation',
    )

    args = parser.parse_args()

    target_dir = Path(args.directory).resolve()

    # Handle undo
    if args.undo:
        _undo_operation(target_dir)
        return

    # Determine strategy
    strategy = 'type'  # default
    if args.by_date and args.by_size:
        print("Warning: Both --by-date and --by-size specified. Using --by-date.", file=sys.stderr)
        strategy = 'date'
    elif args.by_date:
        strategy = 'date'
    elif args.by_size:
        strategy = 'size'

    # Scan
    if not target_dir.is_dir():
        print(f"Error: '{target_dir}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)
    print(f"\nScanning directory: {target_dir}")
    files = scan_directory(target_dir)

    if not files:
        print("No files found to organize.")
        return

    print(f"Found {len(files)} file(s).\n")

    # Compute plan
    operations = compute_plan(files, strategy, target_dir)

    if not operations:
        print("No files to move.")
        return

    # Execute
    if args.dry_run:
        print("DRY-RUN MODE — No files will be moved.\n")
        completed = execute_plan(operations, dry_run=True, target_dir=target_dir)
    else:
        completed = execute_plan(operations, dry_run=False, target_dir=target_dir)

    # Display summary
    display_summary(completed, strategy)

    # Log
    log_operations(target_dir, completed, strategy, dry_run=args.dry_run)

    if args.dry_run:
        print("Dry-run complete. Run without --dry-run to apply changes.")
    else:
        moved = sum(1 for op in completed if op.get('success') and not op.get('dry_run'))
        skipped = sum(1 for op in completed if not op.get('success'))
        print(f"Done. {moved} file(s) moved, {skipped} skipped.")
        if moved > 0:
            print(f"Log saved in {target_dir / '.file_organizer_log.json'}")
            print("Use --undo to reverse this operation.")


def _undo_operation(target_dir: Path) -> None:
    """Undo the most recent organization run."""
    print(f"\nUndo: Looking for last operation in '{target_dir}'...")

    last_run = get_last_run(target_dir)

    if last_run is None:
        print("Nothing to undo. No previous operations found.")
        return

    timestamp = last_run.get('timestamp', 'unknown time')
    operations = last_run.get('operations', [])

    print(f"Found operation from {timestamp} with {len(operations)} file(s).")

    if not operations:
        print("No file operations to undo.")
        pop_last_run(target_dir)
        return

    print(f"Reversing {len(operations)} move(s)...\n")

    reversed_ops = 0
    errors = 0
    source_paths: set[Path] = set()

    for op in operations:
        src = Path(op['destination'])  # The file was moved here
        dst = Path(op['source'])       # We want to move it back here

        if not src.exists():
            print(f"  Warning: Source file not found, skipping: {src.name}")
            errors += 1
            continue

        # Ensure the original parent directory exists
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            print(f"  Error: Could not create directory {dst.parent}: {e}")
            errors += 1
            continue

        # Handle conflicts at the original location
        if dst.exists():
            stem = dst.stem
            suffix = ''.join(dst.suffixes)
            counter = 1
            while True:
                if suffix:
                    alt_name = f"{stem}_restored_{counter}{suffix}"
                else:
                    alt_name = f"{stem}_restored_{counter}"
                alt_dst = dst.parent / alt_name
                if not alt_dst.exists():
                    dst = alt_dst
                    print(f"  Note: Original name exists, restoring as: {alt_name}")
                    break
                counter += 1

        try:
            shutil.move(str(src), str(dst))
            source_paths.add(src.parent)
            reversed_ops += 1
            print(f"  Restored: {dst.name}")
        except (PermissionError, OSError) as e:
            print(f"  Error moving back '{src.name}': {e}")
            errors += 1

    # Remove the run from the log
    pop_last_run(target_dir)

    # Try to clean up empty directories that were created
    _cleanup_empty_dirs(target_dir, source_paths)

    print(f"\nUndo complete. {reversed_ops} file(s) restored, {errors} error(s).")


def _cleanup_empty_dirs(root: Path, candidates: set[Path]) -> None:
    """Remove empty directories that were created during organization.

    Only removes directories under the root that are empty.
    """
    cleaned = 0
    for candidate in sorted(candidates, key=lambda p: len(str(p)), reverse=True):
        try:
            if candidate.exists() and candidate != root:
                # Check if directory is empty
                if not any(candidate.iterdir()):
                    candidate.rmdir()
                    cleaned += 1
                    # Try parent too
                    parent = candidate.parent
                    while parent != root and parent.exists():
                        try:
                            if not any(parent.iterdir()):
                                parent.rmdir()
                                cleaned += 1
                                parent = parent.parent
                            else:
                                break
                        except OSError:
                            break
        except OSError:
            pass

    if cleaned > 0:
        print(f"  Cleaned up {cleaned} empty director{'y' if cleaned == 1 else 'ies'}.")


if __name__ == '__main__':
    main()
