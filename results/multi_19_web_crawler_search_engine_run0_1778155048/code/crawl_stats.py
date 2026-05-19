"""Shared crawl statistics object."""

import threading
import time


class CrawlStats:
    """Thread-safe statistics for crawl progress."""

    def __init__(self):
        self._lock = threading.Lock()
        self.pages_crawled = 0
        self.pages_queued = 0
        self.pages_failed = 0
        self.current_url = ''
        self.start_time = None
        self.end_time = None
        self.status = 'idle'  # 'idle', 'running', 'completed'

    def start(self):
        with self._lock:
            self.start_time = time.time()
            self.status = 'running'

    def finish(self):
        with self._lock:
            self.end_time = time.time()
            self.status = 'completed'

    def increment_crawled(self):
        with self._lock:
            self.pages_crawled += 1

    def increment_queued(self, count=1):
        with self._lock:
            self.pages_queued += count

    def increment_failed(self):
        with self._lock:
            self.pages_failed += 1

    def decrement_queued(self):
        with self._lock:
            self.pages_queued = max(0, self.pages_queued - 1)

    def set_current_url(self, url):
        with self._lock:
            if len(url) > 80:
                self.current_url = url[:80]
            else:
                self.current_url = url

    def snapshot(self):
        """Return a dictionary of current stats."""
        with self._lock:
            elapsed = 0
            if self.start_time:
                end = self.end_time or time.time()
                elapsed = end - self.start_time
            return {
                'pages_crawled': self.pages_crawled,
                'pages_queued': self.pages_queued,
                'pages_failed': self.pages_failed,
                'current_url': self.current_url,
                'status': self.status,
                'elapsed_seconds': round(elapsed, 2)
            }

    def get_progress_line(self):
        """Return a one-line progress string."""
        snap = self.snapshot()
        url_display = snap['current_url'][:60].ljust(60) if snap['current_url'] else ' ' * 60
        return (f"\rCrawled: {snap['pages_crawled']} | "
                f"Queued: {snap['pages_queued']} | "
                f"Failed: {snap['pages_failed']} | "
                f"Current: {url_display}")
