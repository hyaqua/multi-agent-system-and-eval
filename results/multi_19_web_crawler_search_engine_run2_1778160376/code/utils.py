"""
Utility functions: URL normalization, live progress display, logging.
"""

import sys
import time
import logging
import urllib.parse


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """
    Normalize a URL:
      - Resolve relative URLs against base.
      - Strip fragment.
      - Remove trailing slash from path (unless root).
      - Lowercase scheme and host.
    Returns None if URL is invalid.
    """
    try:
        # Resolve relative
        if base_url:
            url = urllib.parse.urljoin(base_url, url)

        parsed = urllib.parse.urlparse(url)

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return None

        # Strip fragment
        url, _ = urllib.parse.urldefrag(url)

        # Re-parse after defrag
        parsed = urllib.parse.urlparse(url)

        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Normalize path: remove trailing slash unless root
        path = parsed.path
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Reconstruct
        normalized = urllib.parse.urlunparse(
            (scheme, netloc, path or "/", parsed.params, parsed.query, "")
        )
        return normalized
    except Exception:
        return None


def get_domain(url: str) -> str:
    """Extract domain (netloc) from a URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower() or parsed.path.split("/")[0]


def configure_logging(verbose: bool = False) -> None:
    """Configure logging format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


class ProgressMonitor:
    """Displays a live progress line on the terminal."""

    def __init__(self):
        self.pages_crawled = 0
        self.queued = 0
        self.failed = 0
        self.current_url = ""
        self.start_time = time.time()

    def update(
        self,
        crawled: int | None = None,
        queued: int | None = None,
        failed: int | None = None,
        current_url: str | None = None,
    ):
        if crawled is not None:
            self.pages_crawled = crawled
        if queued is not None:
            self.queued = queued
        if failed is not None:
            self.failed = failed
        if current_url is not None:
            self.current_url = current_url

        elapsed = time.time() - self.start_time
        # Truncate current URL for display
        display_url = self.current_url
        if len(display_url) > 60:
            display_url = display_url[:57] + "..."

        line = (
            f"\rCrawled: {self.pages_crawled} | "
            f"Queued: {self.queued} | "
            f"Failed: {self.failed} | "
            f"Elapsed: {elapsed:.0f}s | "
            f"Current: {display_url}"
        )
        # Pad to clear previous content
        sys.stdout.write(line.ljust(120))
        sys.stdout.flush()

    def finish(self):
        """End the progress line with a newline."""
        sys.stdout.write("\n")
        sys.stdout.flush()
