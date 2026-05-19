"""
Robots.txt parser and rate limiter with per-domain tracking.
"""

import urllib.robotparser
import urllib.request
import urllib.error
import time
import re
import threading
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Fetches and caches robots.txt per domain, enforces rate limits."""
    
    def __init__(self, timeout=10):
        self._parsers = {}       # domain -> urllib.robotparser.RobotFileParser
        self._last_fetch = {}    # domain -> float (timestamp)
        self._crawl_delays = {}  # domain -> float (seconds)
        self._lock = threading.Lock()
        self._timeout = timeout
        self._user_agent = "CrawlerBot/1.0"
    
    def get_robots_url(self, url):
        """Get the robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _parse_crawl_delay_from_text(self, text):
        """Manually parse Crawl-delay from robots.txt content."""
        # Look for Crawl-delay: N under User-agent: * or our specific agent
        lines = text.splitlines()
        current_agent = None
        for line in lines:
            line = line.strip()
            if line.lower().startswith('user-agent:'):
                current_agent = line.split(':', 1)[1].strip()
            elif line.lower().startswith('crawl-delay:'):
                if current_agent in ('*', self._user_agent, None):
                    try:
                        value = float(line.split(':', 1)[1].strip())
                        if value > 0:
                            return value
                    except ValueError:
                        pass
        return 0.0
    
    def fetch_robots(self, domain, robots_url):
        """Fetch and parse robots.txt for a domain."""
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        raw_content = ""
        
        try:
            req = urllib.request.Request(
                robots_url,
                headers={"User-Agent": self._user_agent}
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                raw_content = response.read().decode('utf-8', errors='replace')
            parser.parse(raw_content.splitlines())
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt for {domain}: {e}")
            # If we can't fetch, allow everything
            parser.allow_all = True
        
        # Manually parse crawl delay from raw content
        crawl_delay = self._parse_crawl_delay_from_text(raw_content)
        
        with self._lock:
            self._parsers[domain] = parser
            self._crawl_delays[domain] = crawl_delay
            self._last_fetch[domain] = 0.0
        
        return parser, crawl_delay
    
    def is_allowed(self, url):
        """Check if a URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = self.get_robots_url(url)
        
        with self._lock:
            if domain not in self._parsers:
                pass  # Will fetch below
            else:
                parser = self._parsers[domain]
                return parser.can_fetch(self._user_agent, url)
        
        # Fetch robots.txt
        parser, _ = self.fetch_robots(domain, robots_url)
        return parser.can_fetch(self._user_agent, url)
    
    def wait_if_needed(self, domain):
        """Block if needed to respect crawl delay."""
        with self._lock:
            delay = self._crawl_delays.get(domain, 0.0)
            last = self._last_fetch.get(domain, 0.0)
        
        if delay > 0:
            elapsed = time.time() - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
    
    def mark_fetched(self, domain):
        """Update last fetch timestamp for a domain."""
        with self._lock:
            self._last_fetch[domain] = time.time()
    
    def ensure_robots_loaded(self, url):
        """Make sure robots.txt is loaded for the URL's domain, fetching if needed."""
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = self.get_robots_url(url)
        
        with self._lock:
            if domain in self._parsers:
                return
        
        self.fetch_robots(domain, robots_url)
