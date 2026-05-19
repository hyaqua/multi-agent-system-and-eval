"""Small utility helpers: human-readable size formatting and a progress ticker."""

import sys


def format_size(num_bytes: int) -> str:
    """Return a human-friendly size string (e.g. '1.23 MB')."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class ProgressTicker:
    """Prints a dot to stderr every *step* files processed.

    If the total number of files is known ahead of time, pass it as
    *total*; the ticker will stay silent for batches smaller than 20
    files.

    Usage::

        ticker = ProgressTicker(step=10, total=len(files))
        for f in files:
            ticker.tick()
        ticker.finish()
    """

    def __init__(self, step: int = 10, total: int | None = None, out=sys.stderr):
        self._step = step
        self._total = total
        self._count = 0
        self._dots = 0
        self._out = out
        self._silent = total is not None and total < 20

    def tick(self):
        self._count += 1
        if self._silent:
            return
        if self._count % self._step == 0:
            self._out.write(".")
            self._out.flush()
            self._dots += 1

    def finish(self):
        if self._silent:
            return
        if self._dots:
            self._out.write("\n")
            self._out.flush()
