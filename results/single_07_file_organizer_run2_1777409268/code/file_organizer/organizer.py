"""Core organiser: moves files into category subdirectories with conflict resolution."""

import os
import os.path
import shutil
import sys
from typing import Callable

from file_organizer.scanner import FileInfo
from file_organizer.logger import append_operations, default_log_path


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _unique_dest(dest_dir: str, name: str) -> str:
    """Return a non-conflicting destination path inside *dest_dir*.

    If ``name`` already exists, append '_1', '_2', … before the extension.
    """
    base, ext = os.path.splitext(name)
    candidate = os.path.join(dest_dir, name)
    if not os.path.exists(candidate):
        return candidate

    counter = 1
    while True:
        candidate = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _progress_indicator(total: int, description: str = "Processing") -> Callable:
    """Return a callable that draws a progress bar to stderr."""

    def _show(current: int) -> None:
        pct = (current / total * 100) if total > 0 else 100
        bar_len = 40
        filled = int(bar_len * current / total) if total > 0 else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stderr.write(f"\r{description}: |{bar}| {current}/{total} ({pct:.0f}%)")
        sys.stderr.flush()

    return _show


# Each planned move: (FileInfo, destination_path)
PlanEntry = tuple[FileInfo, str]


def _build_plan(
    files: list[FileInfo],
    target_dir: str,
    categorizer: Callable[[FileInfo], str],
    on_progress: Callable[[int], None] | None = None,
) -> tuple[dict[str, list[PlanEntry]], int]:
    """Group files by category and resolve destination conflicts.

    Returns (plan, conflicts_resolved).
    """
    plan: dict[str, list[PlanEntry]] = {}
    conflicts = 0

    for idx, info in enumerate(files, start=1):
        if on_progress:
            on_progress(idx)

        category = categorizer(info)
        dest_dir = os.path.join(target_dir, category)
        dest = _unique_dest(dest_dir, info.name)
        if dest != os.path.join(dest_dir, info.name):
            conflicts += 1

        plan.setdefault(category, []).append((info, dest))

    return plan, conflicts


def _print_summary(
    plan: dict[str, list[PlanEntry]],
    total: int,
    conflicts: int,
    dry_run: bool,
) -> None:
    """Print summary table and, for dry‑run, a detailed file listing."""
    print()
    print("=" * 70)
    if dry_run:
        print("DRY-RUN — no files will be moved.")
    print(f"Files scanned : {total}")
    print(f"Name conflicts resolved : {conflicts}")
    print("-" * 70)
    for cat in sorted(plan.keys()):
        print(f"  {cat:35s} → {len(plan[cat]):5d} file(s)")
    print("=" * 70)

    if dry_run:
        print("\nDetailed plan (showing type, size, modification date):")
        for cat in sorted(plan.keys()):
            print(f"\n[{cat}]")
            for info, dest in plan[cat]:
                rel_dest = os.path.relpath(dest, os.path.dirname(dest) if cat == "" else os.path.dirname(os.path.dirname(dest)))
                # Compute a cleaner relative path for display
                display_dest = os.path.join(cat, os.path.basename(dest))
                print(
                    f"  {info.name:30s}  "
                    f"{info.ext or '(none)':8s}  "
                    f"{_format_size(info.size):>10s}  "
                    f"{info.mtime.strftime('%Y-%m-%d %H:%M'):>16s}  "
                    f"→ {display_dest}"
                )


def organize(
    files: list[FileInfo],
    target_dir: str,
    categorizer: Callable[[FileInfo], str],
    *,
    dry_run: bool = False,
) -> None:
    """Move *files* into subdirectories of *target_dir* based on *categorizer*."""
    total = len(files)
    if total == 0:
        print("No files to organize.")
        return

    show = _progress_indicator(total, "Organizing" if not dry_run else "Scanning")
    plan, conflicts = _build_plan(files, target_dir, categorizer, on_progress=show)

    # Clear progress line
    sys.stderr.write("\r" + " " * 80 + "\r")
    sys.stderr.flush()

    _print_summary(plan, total, conflicts, dry_run)

    if dry_run:
        return

    # ----- Execute moves -----
    log_ops: list[dict] = []
    moved = 0
    errors = 0

    show_exec = _progress_indicator(total, "Moving   ")

    op_idx = 0
    for cat in sorted(plan.keys()):
        moves = plan[cat]
        dest_dir = os.path.join(target_dir, cat)

        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as exc:
            print(f"\n⚠  Cannot create directory '{dest_dir}': {exc}")
            for _info, _dst in moves:
                print(f"⚠  Skipping '{_info.name}' — target directory unavailable.")
            errors += len(moves)
            continue

        for info, dst in moves:
            op_idx += 1
            show_exec(op_idx)

            try:
                shutil.move(info.path, dst)
                log_ops.append({"source": info.path, "destination": dst})
                moved += 1
            except PermissionError:
                print(f"\n⚠  Permission denied: cannot move '{info.name}'")
                errors += 1
            except OSError as exc:
                print(f"\n⚠  Error moving '{info.name}': {exc}")
                errors += 1

    # Clear progress line
    sys.stderr.write("\r" + " " * 80 + "\r")
    sys.stderr.flush()

    # ----- Write log -----
    if log_ops:
        log_path = default_log_path(target_dir)
        append_operations(log_path, log_ops)

    print(f"\nDone: {moved} file(s) moved, {errors} error(s).")
    if log_ops:
        print(f"Log written to {default_log_path(target_dir)}")
