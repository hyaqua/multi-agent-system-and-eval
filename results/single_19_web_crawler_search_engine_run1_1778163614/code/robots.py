"""Robots.txt fetching, parsing, and per-domain rate limiting."""

import threading
import time
import urllib.request
import urllib.error
import urllib.robotparser
from typing import Optional


class RobotsCache:
    """Thread-safe cache for robots.txt entries per domain."""

    def __init__(self, user_agent: str = 'SearchCrawler/1.0',
                 default_delay: float = 1.0):
        self._lock = threading.Lock()
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._crawl_delays: dict[str, float] = {}
        self._last_access: dict[str, float] = {}
        self._user_agent = user_agent
        self._default_delay = default_delay
        self._fetched_domains: set[str] = set()
        self._disallowed: dict[str, set[str]] = {}  # domain -> set of disallowed paths

    def _fetch_robots_txt(self, domain: str, timeout: float = 10.0) -> Optional[str]:
        """Fetch robots.txt for a domain."""
        robots_url = f'http://{domain}/robots.txt'
        # Also try https if http fails
        urls_to_try = [robots_url]
        if robots_url.startswith('http://'):
            urls_to_try.append(f'https://{domain}/robots.txt')

        for url in urls_to_try:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': self._user_agent})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        return resp.read().decode('utf-8', errors='replace')
            except Exception:
                continue

        return None

    def ensure_fetched(self, domain: str, timeout: float = 10.0) -> None:
        """Fetch and parse robots.txt for a domain if not already done."""
        with self._lock:
            if domain in self._fetched_domains:
                return
            self._fetched_domains.add(domain)

        content = self._fetch_robots_txt(domain, timeout)

        with self._lock:
            rp = urllib.robotparser.RobotFileParser()
            rp.allow_all = True  # default if we can't parse

            if content:
                try:
                    rp.parse(content.splitlines())
                except Exception:
                    rp.allow_all = True

            self._parsers[domain] = rp

            # Extract Crawl-delay
            delay = self._default_delay
            if content:
                for line in content.splitlines():
                    line_lower = line.strip().lower()
                    if line_lower.startswith('crawl-delay:'):
                        try:
                            val = float(line_lower.split(':', 1)[1].strip())
                            if val >= 0:
                                delay = val
                        except ValueError:
                            pass
                    elif line_lower.startswith('disallow:'):
                        path = line_lower.split(':', 1)[1].strip()
                        if path:
                            if domain not in self._disallowed:
                                self._disallowed[domain] = set()
                            self._disallowed[domain].add(path)

            self._crawl_delays[domain] = delay
            self._last_access[domain] = 0.0

    def is_allowed(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt."""
        from utils import get_domain
        domain = get_domain(url)
        self.ensure_fetched(domain)

        with self._lock:
            rp = self._parsers.get(domain)
            if rp is None:
                return True
            try:
                return rp.can_fetch(self._user_agent, url)
            except Exception:
                return True

    def get_crawl_delay(self, domain: str) -> float:
        """Get crawl delay for a domain in seconds."""
        with self._lock:
            return self._crawl_delays.get(domain, self._default_delay)

    def wait_if_needed(self, domain: str) -> None:
        """Block until the domain's rate limit allows another request."""
        delay = self.get_crawl_delay(domain)
        if delay <= 0:
            return

        with self._lock:
            last = self._last_access.get(domain, 0.0)
            now = time.time()
            wait = delay - (now - last)
            if wait > 0:
                # Release lock while sleeping
                pass
            else:
                self._last_access[domain] = now
                return

        if wait > 0:
            time.sleep(wait)
            with self._lock:
                self._last_access[domain] = time.time()
        else:
            with self._lock:
                self._last_access[domain] = now
