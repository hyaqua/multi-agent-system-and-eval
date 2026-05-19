"""URL normalization, domain extraction, robots.txt parsing and caching."""

import urllib.parse
import urllib.robotparser
import urllib.request
import threading
import time
import sys


def normalize_url(url, base_url=None):
    """Normalize a URL: resolve relative, strip fragments, lower scheme/host, remove default ports."""
    if base_url:
        url = urllib.parse.urljoin(base_url, url)

    # Strip fragment
    url = urllib.parse.urldefrag(url)[0]

    parsed = urllib.parse.urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower() if parsed.scheme else 'http'
    host = parsed.hostname.lower() if parsed.hostname else ''
    port = parsed.port

    # Remove default ports
    if (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443):
        port = None

    host_part = host
    if port:
        host_part = f"{host}:{port}"

    if host_part:
        netloc = host_part
    else:
        netloc = parsed.netloc

    # Reconstruct URL without fragment
    normalized = urllib.parse.urlunparse((scheme, netloc, parsed.path or '/',
                                           parsed.params, parsed.query, ''))

    return normalized


def get_domain(url):
    """Extract the domain (host) from a URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname.lower() if parsed.hostname else ''


class RobotsCache:
    """Thread-safe cache for robots.txt parsers per domain."""

    def __init__(self, timeout=10):
        self._cache = {}
        self._lock = threading.Lock()
        self._timeout = timeout
        self._last_access = {}
        self._access_lock = threading.Lock()

    def get_parser(self, url, user_agent='WebCrawler/1.0'):
        """Get or create a RobotFileParser for the domain of the given URL."""
        domain = get_domain(url)

        with self._lock:
            if domain in self._cache:
                return self._cache[domain]

            # Create new parser
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"http://{domain}/robots.txt")
            if urllib.parse.urlparse(url).scheme == 'https':
                parser.set_url(f"https://{domain}/robots.txt")

            try:
                parser.read()
                parser.useragent = user_agent
            except Exception as e:
                # If robots.txt can't be fetched, allow all
                print(f"WARNING: Could not fetch robots.txt for {domain}: {e}", file=sys.stderr)
                parser.allow_all = True
                parser.disallow_all = False
                # Monkey-patch to allow all
                parser.can_fetch = lambda *args, **kwargs: True

            self._cache[domain] = parser
            return parser

    def is_allowed(self, url, user_agent='WebCrawler/1.0'):
        """Check if URL is allowed by robots.txt."""
        parser = self.get_parser(url, user_agent)
        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True

    def get_crawl_delay(self, url, user_agent='WebCrawler/1.0'):
        """Get the crawl delay for the domain of the URL."""
        if hasattr(self, '_cache'):
            domain = get_domain(url)
            with self._lock:
                if domain in self._cache:
                    parser = self._cache[domain]
                    try:
                        delay = parser.crawl_delay(user_agent)
                        return delay if delay else 0
                    except Exception:
                        return 0
        return 0

    def wait_if_needed(self, url, user_agent='WebCrawler/1.0'):
        """Sleep if needed to respect crawl delay for the domain."""
        domain = get_domain(url)
        delay = self.get_crawl_delay(url, user_agent)

        if delay > 0:
            with self._access_lock:
                now = time.time()
                last = self._last_access.get(domain, 0)
                wait = delay - (now - last)
                if wait > 0:
                    time.sleep(wait)
                self._last_access[domain] = time.time()
        else:
            with self._access_lock:
                self._last_access[domain] = time.time()
