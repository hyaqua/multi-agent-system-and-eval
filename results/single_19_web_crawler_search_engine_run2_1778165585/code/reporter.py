"""Live crawl progress display and summary report."""

import sys
import time
import threading
from typing import Optional


class CrawlReporter:
    """Displays live crawl progress and summary reports."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._pages_crawled = 0
        self._pages_queued = 0
        self._pages_failed = 0
        self._current_url = ""
        self._start_time = 0.0

    def start(self):
        """Start the progress display."""
        self._running = True
        self._start_time = time.time()

    def update(self, crawled: int, queued: int, failed: int, current_url: str):
        """Update progress values. Thread-safe."""
        with self._lock:
            self._pages_crawled = crawled
            self._pages_queued = queued
            self._pages_failed = failed
            short_url = current_url[:70] + "..." if len(current_url) > 70 else current_url
            self._current_url = short_url

        # Print progress line (overwrite previous)
        elapsed = time.time() - self._start_time
        line = (
            f"\r[Progress] Crawled: {crawled} | Queued: {queued} | "
            f"Failed: {failed} | Elapsed: {elapsed:.1f}s | "
            f"Current: {short_url}"
        )
        # Pad to clear previous content
        sys.stdout.write(line.ljust(120))
        sys.stdout.flush()

    def stop(self):
        """Stop progress display and print newline."""
        self._running = False
        sys.stdout.write("\n")
        sys.stdout.flush()

    def print_summary(
        self,
        total_pages: int,
        total_terms: int,
        domain_links: dict,
        elapsed: float,
    ):
        """Print a summary report after crawling completes."""
        print()
        print("=" * 60)
        print("  CRAWL COMPLETE - SUMMARY REPORT")
        print("=" * 60)
        print(f"  Total pages crawled:  {total_pages}")
        print(f"  Total unique terms:   {total_terms}")
        print(f"  Total time:           {elapsed:.2f} seconds")
        print()

        # Top 10 most linked domains
        sorted_domains = sorted(domain_links.items(), key=lambda x: x[1], reverse=True)
        if sorted_domains:
            print("  Top linked domains:")
            for i, (domain, count) in enumerate(sorted_domains[:10], 1):
                print(f"    {i:2d}. {domain:<40s} ({count} links)")
        else:
            print("  No domain links collected.")

        print("=" * 60)
