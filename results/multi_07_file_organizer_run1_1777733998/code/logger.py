"""Manages the JSONL log file: appending move records, reading all entries
for undo, and clearing the log after a successful undo.
"""

import json
import os
import sys
from datetime import datetime, timezone


class Logger:
    """Writes and reads the JSON Lines (JSONL) operation log."""

    def __init__(self, log_path: str):
        """*log_path* is the absolute or relative path to the log file."""
        self._log_path = log_path

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    def append(self, source: str, destination: str) -> None:
        """Record a move operation.

        Parameters
        ----------
        source : str
            Absolute source path.
        destination : str
            Absolute destination path.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": os.path.abspath(source),
            "destination": os.path.abspath(destination),
        }
        try:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(
                f"Warning: could not write log entry: {exc}",
                file=sys.stderr,
            )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def read_all(self) -> list[dict]:
        """Return every log entry as a list of dicts (preserving order).

        Returns an empty list if the log file does not exist or is
        unreadable.
        """
        if not os.path.isfile(self._log_path):
            return []
        entries = []
        try:
            with open(self._log_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(
                            f"Warning: skipping malformed log line: {line!r}",
                            file=sys.stderr,
                        )
        except OSError as exc:
            print(f"Warning: cannot read log file: {exc}", file=sys.stderr)
        return entries

    # ------------------------------------------------------------------
    # Resetting / Clearing
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Truncate (empty) the log file so only the current run is recorded.

        Called by the Organizer at the start of every non-dry-run
        organise operation.
        """
        self.clear()

    def clear(self) -> None:
        """Truncate (empty) the log file."""
        try:
            open(self._log_path, "w", encoding="utf-8").close()
        except OSError as exc:
            print(f"Warning: could not clear log file: {exc}", file=sys.stderr)
