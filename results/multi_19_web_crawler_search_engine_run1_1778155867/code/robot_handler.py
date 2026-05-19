"""Robots.txt handler with per-domain caching and rate limiting."""

import urllib.robotparser
import urllib.request
import urllib.parse
import time
import threading


class RobotHandler:
    """
    Fetches and caches robots.txt for each domain.
    Enforces Crawl-delay with per-domain last-access tracking.
    """

    def __init__(self, user_agent: str = '*', default_delay: float = 1.0,
                 timeout: int = 10):
        self.user_agent = user_agent
        self.default_delay = default_delay
        self.timeout = timeout
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_access: dict[str, float] = {}
        self._crawl_delays: dict[str, float] = {}
        self._lock = threading.Lock()

    def get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL."""
        parsed = urllib.parse.urlparse(url)
        return f'{parsed.scheme}://{parsed.netloc}/robots.txt'

    def _ensure_parser(self, domain: str) -> urllib.robotparser.RobotFileParser | None:
        """Fetch and parse robots.txt for a domain if not already cached."""
        with self._lock:
            if domain in self._parsers:
                return self._parsers[domain]

        # Fetch robots.txt ourselves with a timeout so unresponsive
        # endpoints don't hang the crawl.  On any error, we leave the
        # domain out of the cache so that can_fetch returns True
        # (allow-all) for every URL on that domain.
        robots_url = f'http://{domain}/robots.txt'
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            with urllib.request.urlopen(robots_url, timeout=self.timeout) as resp:
                raw = resp.read()
            # urllib.robotparser expects lines
            lines = raw.decode('utf-8', errors='replace').splitlines()
            parser.parse(lines)
        except Exception as e:
            print(f'Warning: Could not fetch robots.txt for {domain}: {e}. '
                  f'Allowing all crawls.')
            # Do NOT cache a parser — is_allowed will default to True
            return None

        with self._lock:
            self._parsers[domain] = parser
            # Extract crawl delay
            try:
                delay = parser.crawl_delay(self.user_agent)
                if delay is None:
                    delay = self.default_delay
                self._crawl_delays[domain] = float(delay)
            except Exception:
                self._crawl_delays[domain] = self.default_delay

        return parser

    def can_fetch(self, url: str) -> bool:
        """Check if the URL is allowed by robots.txt."""
        domain = urllib.parse.urlparse(url).netloc.lower()
        parser = self._ensure_parser(domain)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def wait_if_needed(self, url: str):
        """
        Enforce Crawl-delay for the domain of the given URL.
        Sleeps if the domain was accessed too recently.
        """
        domain = urllib.parse.urlparse(url).netloc.lower()
        self._ensure_parser(domain)

        with self._lock:
            delay = self._crawl_delays.get(domain, self.default_delay)
            last = self._last_access.get(domain, 0)
            now = time.time()
            elapsed = now - last

        if elapsed < delay:
            time.sleep(delay - elapsed)

        with self._lock:
            self._last_access[domain] = time.time()
