"""Undo manager: reads the JSON log and reverses the last operation batch."""

import os
import os.path
import shutil

from file_organizer.logger import read_log, write_log, default_log_path


def undo_last(target_dir: str) -> bool:
    """Undo the most recent organising session recorded in the log.

    Returns True if any operations were reversed, False otherwise.
    """
    log_path = default_log_path(target_dir)
    sessions = read_log(log_path)

    if not sessions:
        print("Nothing to undo — the log is empty.")
        return False

    # The newest session is first
    session = sessions[0]
    ops = session.get("operations", [])

    if not ops:
        print("Nothing to undo — the most recent session has no operations.")
        # Remove empty session anyway
        sessions.pop(0)
        write_log(log_path, sessions)
        return False

    print(f"Undoing {len(ops)} operation(s) from {session.get('timestamp', 'unknown')}…")

    reversed_count = 0
    failures = 0

    # Operations are stored in order they were performed (source → dest).
    # To undo we move dest → source.
    for op in ops:
        src = op.get("source")      # original location
        dst = op.get("destination") # where the file was moved to

        if not src or not dst:
            print("⚠  Skipping malformed log entry (missing source/destination).")
            failures += 1
            continue

        if not os.path.isfile(dst):
            print(f"⚠  Cannot undo: '{dst}' no longer exists — skipping.")
            failures += 1
            continue

        # Ensure the original parent directory still exists
        src_dir = os.path.dirname(src)
        if not os.path.isdir(src_dir):
            try:
                os.makedirs(src_dir, exist_ok=True)
            except OSError as exc:
                print(f"⚠  Cannot recreate directory '{src_dir}': {exc}")
                failures += 1
                continue

        # If a file already sits at src, move with a temporary name first
        # to avoid overwriting — but in practice this shouldn't happen
        # unless someone manually placed a file there.
        if os.path.exists(src):
            print(f"⚠  '{src}' already exists; skipping undo for '{dst}' to avoid overwriting.")
            failures += 1
            continue

        try:
            shutil.move(dst, src)
            reversed_count += 1
        except OSError as exc:
            print(f"⚠  Failed to move '{dst}' back to '{src}': {exc}")
            failures += 1

    # Remove the session we just processed
    sessions.pop(0)
    write_log(log_path, sessions)

    print(f"Undo complete: {reversed_count} file(s) restored, {failures} skipped/failed.")
    return reversed_count > 0
