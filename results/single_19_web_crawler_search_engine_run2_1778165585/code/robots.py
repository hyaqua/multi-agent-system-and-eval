"""Robots.txt fetching, parsing, and per-domain rate limiting."""

import urllib.parse
import urllib.request
import time
import threading
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Fetches and parses robots.txt for domains, enforces rate limits."""

    def __init__(self, user_agent: str = "SimpleCrawler/1.0", timeout: float = 10.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._cache: dict = {}  # domain -> {'disallow': [...], 'crawl_delay': float}
        self._lock = threading.Lock()
        self._last_fetch_time: dict = {}  # domain -> last fetch timestamp
        self._domain_locks: dict = {}  # domain -> threading.Lock for rate limiting
        self._domain_lock_lock = threading.Lock()

    def _get_domain_lock(self, domain: str) -> threading.Lock:
        with self._domain_lock_lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = threading.Lock()
            return self._domain_locks[domain]

    def fetch_robots(self, domain: str) -> dict:
        """Fetch and parse robots.txt for a domain. Returns parsed rules dict."""
        with self._lock:
            if domain in self._cache:
                return self._cache[domain]

        robots_url = f"http://{domain}/robots.txt"
        if domain.startswith("https://"):
            robots_url = f"{domain}/robots.txt"
        elif not domain.startswith("http"):
            # Try https first, fall back to http
            robots_url_https = f"https://{domain}/robots.txt"
            robots_url_http = f"http://{domain}/robots.txt"

        rules = {"disallow": [], "crawl_delay": 0.0, "fetched": False}

        urls_to_try = []
        if domain.startswith("http"):
            urls_to_try = [f"{domain.rstrip('/')}/robots.txt"]
        else:
            urls_to_try = [
                f"https://{domain}/robots.txt",
                f"http://{domain}/robots.txt",
            ]

        for url in urls_to_try:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": self.user_agent},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        content = resp.read().decode("utf-8", errors="replace")
                        rules = self._parse_robots_content(content)
                        rules["fetched"] = True
                        break
            except Exception:
                continue

        with self._lock:
            self._cache[domain] = rules

        return rules

    def _parse_robots_content(self, content: str) -> dict:
        """Parse robots.txt content."""
        disallow = []
        crawl_delay = 0.0
        current_user_agent = None
        applies_to_us = False

        for line in content.splitlines():
            line = line.strip()
            # Remove comments
            if "#" in line:
                line = line.split("#", 1)[0].strip()
            if not line:
                continue

            # Parse directive
            if ":" not in line:
                continue

            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                current_user_agent = value.lower()
                applies_to_us = (
                    current_user_agent == "*"
                    or current_user_agent == self.user_agent.lower()
                )
            elif key == "disallow" and applies_to_us:
                if value:
                    disallow.append(value)
            elif key == "crawl-delay" and applies_to_us:
                try:
                    crawl_delay = max(crawl_delay, float(value))
                except ValueError:
                    pass

        return {"disallow": disallow, "crawl_delay": crawl_delay, "fetched": True}

    def is_allowed(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt rules."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path or "/"
            if parsed.query:
                path = path + "?" + parsed.query
        except Exception:
            return True  # If we can't parse, allow

        rules = self.fetch_robots(domain)
        if not rules["fetched"]:
            return True  # No robots.txt means allow

        for disallow_path in rules["disallow"]:
            if self._path_matches(path, disallow_path):
                return False

        return True

    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if a path matches a robots.txt disallow pattern."""
        # Simple prefix matching as per robots.txt spec
        if pattern == "/":
            return True
        return path.startswith(pattern)

    def wait_if_needed(self, domain: str):
        """Enforce crawl-delay for a domain. Blocks the calling thread."""
        rules = self.fetch_robots(domain)
        delay = rules.get("crawl_delay", 0.0)
        if delay <= 0:
            return

        lock = self._get_domain_lock(domain)
        with lock:
            now = time.time()
            last = self._last_fetch_time.get(domain, 0)
            elapsed = now - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_fetch_time[domain] = time.time()

    def get_delay(self, domain: str) -> float:
        """Get the crawl delay for a domain."""
        rules = self.fetch_robots(domain)
        return rules.get("crawl_delay", 0.0)
