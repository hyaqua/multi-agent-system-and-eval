"""Core organization logic: plan and execute file moves."""

import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from file_organizer.categories import (
    get_category_by_extension,
    get_category_by_size,
)


def compute_plan(
    files: list[dict],
    strategy: str,
    target_dir: Path,
) -> list[dict]:
    """Compute the destination path for each file without moving anything.

    Args:
        files: List of file metadata dicts from scanner.
        strategy: One of 'type', 'date', 'size'.
        target_dir: The root directory where subdirectories will be created.

    Returns:
        List of dicts with source, destination, category keys.
    """
    target_dir = target_dir.resolve()
    operations: list[dict] = []

    # Group files by their target subdirectory to detect conflicts
    planned_destinations: dict[Path, list[tuple[int, Path]]] = defaultdict(list)
    # Map: destination_dir -> [(index_in_files, proposed_dest_path)]

    for idx, file_info in enumerate(files):
        subdir = _get_subdirectory(file_info, strategy)
        dest_dir = target_dir / subdir
        dest_path = dest_dir / file_info['name']

        planned_destinations[dest_dir].append((idx, dest_path))

    # Resolve conflicts within each destination directory
    for dest_dir, entries in planned_destinations.items():
        seen_names: dict[str, int] = {}  # name stem -> count
        for idx, dest_path in entries:
            final_dest = _resolve_conflict(dest_path, seen_names, dest_dir)
            operations.append({
                'source': files[idx]['path'],
                'destination': final_dest,
                'category': _get_category_label(file_info=files[idx], strategy=strategy),
            })

    return operations


def execute_plan(operations: list[dict], dry_run: bool = False, target_dir: Path = None) -> list[dict]:
    """Execute the move operations.

    Args:
        operations: List of operation dicts with source, destination, category.
        dry_run: If True, only print what would happen; don't move.
        target_dir: The root target directory (for display purposes).

    Returns:
        List of successfully completed operations (with 'success' key).
    """
    completed: list[dict] = []
    total = len(operations)
    errors: list[str] = []

    for i, op in enumerate(operations):
        _show_progress(i + 1, total, "Moving" if not dry_run else "Planning")

        source = op['source']
        destination = op['destination']

        if dry_run:
            # Show a clean relative path from target_dir
            if target_dir:
                try:
                    rel_dest = destination.relative_to(target_dir)
                except ValueError:
                    rel_dest = destination
            else:
                rel_dest = destination
            print(f"  [DRY-RUN] {source.name} -> {rel_dest}")
            # In dry-run, still log but note it wasn't actually moved
            op['success'] = True
            op['dry_run'] = True
            completed.append(op)
            continue

        # Create destination directory
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            errors.append(f"Error: Permission denied creating directory: {destination.parent}")
            op['success'] = False
            op['error'] = f"Permission denied: {destination.parent}"
            completed.append(op)
            continue
        except OSError as e:
            errors.append(f"Error: Could not create directory {destination.parent}: {e}")
            op['success'] = False
            op['error'] = str(e)
            completed.append(op)
            continue

        # Move the file
        try:
            shutil.move(str(source), str(destination))
            op['success'] = True
            op['dry_run'] = False
            completed.append(op)
        except PermissionError:
            errors.append(f"Warning: Permission denied moving '{source.name}' — skipping.")
            op['success'] = False
            op['error'] = 'Permission denied'
            completed.append(op)
        except OSError as e:
            errors.append(f"Error: Could not move '{source.name}': {e}")
            op['success'] = False
            op['error'] = str(e)
            completed.append(op)

    # Clear progress line
    if total > 30:
        sys.stderr.write('\r' + ' ' * 60 + '\r')
        sys.stderr.flush()

    for err in errors:
        print(err, file=sys.stderr)

    return completed


def display_summary(operations: list[dict], strategy: str) -> None:
    """Display a summary of how many files go to each subdirectory."""
    from collections import Counter
    counts: Counter = Counter()
    for op in operations:
        label = _get_summary_label(op, strategy)
        counts[label] += 1

    print(f"\n{'=' * 55}")
    print(f"  Organization Summary (strategy: {strategy})")
    print(f"{'=' * 55}")
    print(f"  Total files to move: {len(operations)}")
    print(f"{'-' * 55}")

    for label, count in sorted(counts.items()):
        print(f"  {label:<40} {count:>5} files")

    # Count errors
    errors = sum(1 for op in operations if not op.get('success', True))
    if errors:
        print(f"{'-' * 55}")
        print(f"  {'Errors/Skipped:':<40} {errors:>5} files")
    print(f"{'=' * 55}\n")


def _get_subdirectory(file_info: dict, strategy: str) -> str:
    """Determine the subdirectory for a file based on the strategy."""
    if strategy == 'date':
        mtime = file_info['mtime']
        return f"{mtime.year:04d}/{mtime.month:02d}"
    elif strategy == 'size':
        cat = get_category_by_size(file_info['size'])
        return cat
    else:  # default: by type
        cat = get_category_by_extension(file_info['extension'])
        return cat


def _get_category_label(*, file_info: dict = None, strategy: str = 'type') -> str:
    """Get a human-readable category label."""
    if strategy == 'date':
        mtime = file_info['mtime']
        return f"{mtime.year:04d}/{mtime.month:02d}"
    elif strategy == 'size':
        return get_category_by_size(file_info['size'])
    else:
        return get_category_by_extension(file_info['extension'])


def _get_summary_label(op: dict, strategy: str) -> str:
    """Get the label for summary display."""
    if strategy == 'date':
        # Extract year/month from destination path
        parts = op['destination'].parts
        # Find year/month pattern in path
        for i, p in enumerate(parts):
            if len(p) == 4 and p.isdigit():
                if i + 1 < len(parts) and len(parts[i + 1]) == 2 and parts[i + 1].isdigit():
                    return f"{p}/{parts[i + 1]}"
    return op.get('category', 'Other')


def _resolve_conflict(dest_path: Path, seen_names: dict[str, int], dest_dir: Path) -> Path:
    """Resolve filename conflicts by appending a number suffix.

    Checks both the in-memory planned names and existing files on disk.
    """
    name = dest_path.name
    stem = dest_path.stem
    suffix = ''.join(dest_path.suffixes)  # handles compound extensions like .tar.gz

    # Build the set of all existing names
    existing_names: set[str] = set()
    if dest_dir.exists():
        try:
            for entry in dest_dir.iterdir():
                existing_names.add(entry.name)
        except PermissionError:
            pass  # If we can't read, we'll handle at move time

    # Also consider names we've already planned
    existing_names.update(seen_names.keys())

    if name not in existing_names and name not in seen_names:
        seen_names[name] = 0
        return dest_path

    # Need to find a unique name
    counter = 1
    while True:
        if suffix:
            new_name = f"{stem}_{counter}{suffix}"
        else:
            new_name = f"{stem}_{counter}"
        if new_name not in existing_names and new_name not in seen_names:
            seen_names[new_name] = counter
            return dest_dir / new_name
        # Also check if this candidate has been claimed
        counter += 1
        if counter > 10000:
            # Safety limit
            raise RuntimeError(f"Could not resolve name conflict for {name} after 10000 attempts")


from file_organizer.scanner import _show_progress
