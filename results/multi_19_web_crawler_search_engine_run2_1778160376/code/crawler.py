"""
Web crawler: URL frontier, thread pool, robots.txt handling, HTML processing.
"""

import html.parser
import logging
import threading
import time
import queue
import urllib.request
import urllib.parse
import urllib.error
import urllib.robotparser
import ssl

from utils import normalize_url, get_domain
from indexer import Indexer
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class RobotsCache:
    """Thread-safe cache of robots.txt parsers per domain."""

    def __init__(self, timeout: float = 10.0):
        self.cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.lock = threading.Lock()
        self.timeout = timeout

    def get_parser(self, domain: str, scheme: str) -> urllib.robotparser.RobotFileParser:
        """Fetch and parse robots.txt for a domain, caching the result."""
        with self.lock:
            if domain in self.cache:
                return self.cache[domain]

        robots_url = f"{scheme}://{domain}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            # Create SSL context that doesn't verify (for simplicity)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(robots_url, timeout=self.timeout, context=ctx) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            rp.parse(content.splitlines())
        except Exception as e:
            logger.debug("Could not fetch robots.txt for %s: %s", domain, e)
            # If we can't fetch robots.txt, allow everything
            rp.allow_all = True

        with self.lock:
            self.cache[domain] = rp
        return rp

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Check if the URL is allowed by robots.txt."""
        domain = get_domain(url)
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme
        rp = self.get_parser(domain, scheme)
        return rp.can_fetch(user_agent, url)

    def crawl_delay(self, domain: str, scheme: str) -> float:
        """Get the Crawl-delay for a domain (seconds)."""
        rp = self.get_parser(domain, scheme)
        try:
            delay = rp.crawl_delay("*")
            if delay is not None:
                return float(delay)
        except Exception:
            pass
        return 0.0


class RateLimiter:
    """Per-domain rate limiting based on Crawl-delay."""

    def __init__(self, robots_cache: RobotsCache):
        self.last_fetch: dict[str, float] = {}
        self.lock = threading.Lock()
        self.robots_cache = robots_cache

    def wait_if_needed(self, url: str) -> None:
        """Block until the rate limit for this domain has passed."""
        domain = get_domain(url)
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme
        delay = self.robots_cache.crawl_delay(domain, scheme)

        if delay <= 0:
            return

        # Calculate required wait time under the lock
        with self.lock:
            now = time.time()
            last = self.last_fetch.get(domain, 0.0)
            elapsed = now - last
            sleep_time = delay - elapsed if elapsed < delay else 0.0

        # Sleep outside the lock to avoid blocking other threads
        if sleep_time > 0:
            logger.debug("Rate limiting %s: sleeping %.2fs", domain, sleep_time)
            time.sleep(sleep_time)

        # Update last fetch timestamp after sleeping
        with self.lock:
            self.last_fetch[domain] = time.time()


class HTMLProcessor(html.parser.HTMLParser):
    """Extract visible text and links from HTML."""

    def __init__(self):
        super().__init__()
        self.text_chunks: list[str] = []
        self.links: list[str] = []
        self.title: str = ""
        self._skip = False
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript"):
            self._skip = True
        elif tag_lower == "title":
            self._in_title = True

        # Extract href from <a>
        if tag_lower == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "noscript"):
            self._skip = False
        elif tag_lower == "title":
            self._in_title = False
            self.title = " ".join(self._title_text).strip()

    def handle_data(self, data: str):
        if self._skip:
            return
        if self._in_title:
            self._title_text.append(data)
        self.text_chunks.append(data)

    def get_text(self) -> str:
        text = " ".join(self.text_chunks)
        # Collapse whitespace
        import re
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class Fetcher:
    """Fetch URLs using urllib with timeout and content-type checking."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def fetch(self, url: str) -> tuple[str | None, str | None]:
        """
        Fetch a URL and return (content, content_type) or (None, None) on error.
        Follows redirects automatically via urllib.
        """
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SimpleCrawler/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as resp:
                content_type = resp.headers.get("Content-Type", "")
                final_url = resp.geturl()

                # Check Content-Type for HTML
                ct_lower = content_type.lower()
                if "text/html" not in ct_lower and "application/xhtml" not in ct_lower:
                    logger.debug("Skipping non-HTML content: %s (%s)", final_url, content_type)
                    return None, content_type

                # Read content
                content = resp.read()
                # Try to decode
                charset = "utf-8"
                # Try to extract charset from content-type
                if "charset=" in ct_lower:
                    parts = ct_lower.split("charset=")
                    if len(parts) > 1:
                        charset = parts[1].split(";")[0].strip()
                try:
                    text = content.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text = content.decode("utf-8", errors="replace")

                return text, content_type
        except urllib.error.HTTPError as e:
            logger.error("HTTP error %d for %s: %s", e.code, url, e.reason)
            return None, None
        except urllib.error.URLError as e:
            logger.error("URL error for %s: %s", url, e.reason)
            return None, None
        except ssl.SSLError as e:
            logger.error("SSL error for %s: %s", url, e)
            return None, None
        except Exception as e:
            logger.error("Error fetching %s: %s", url, e)
            return None, None


class Crawler:
    """Main crawler: manages frontier, workers, and coordination with indexer."""

    def __init__(
        self,
        seed_urls: list[str],
        depth: int = 2,
        limit: int = 100,
        num_workers: int = 5,
        timeout: float = 10.0,
        progress_callback=None,
    ):
        self.seed_urls = seed_urls
        self.max_depth = depth
        self.limit = limit
        self.num_workers = num_workers
        self.timeout = timeout
        self.progress_callback = progress_callback

        # Frontier: queue of (url, depth)
        self.frontier: queue.Queue = queue.Queue()
        self.visited: set[str] = set()
        self.visited_lock = threading.Lock()

        self.indexer = Indexer()
        self.robots_cache = RobotsCache(timeout=timeout)
        self.rate_limiter = RateLimiter(self.robots_cache)
        self.fetcher = Fetcher(timeout=timeout)

        # Stats
        self.stats_lock = threading.Lock()
        self.crawled = 0
        self.failed = 0
        self.doc_id_counter = 0

        # Domain link count for summary
        self.domain_links: dict[str, int] = {}
        self.domain_links_lock = threading.Lock()

        # Shutdown flag
        self.stop_flag = threading.Event()

    def _should_stop(self) -> bool:
        with self.stats_lock:
            return self.crawled >= self.limit or self.stop_flag.is_set()

    def _add_to_frontier(self, url: str, depth: int):
        """Normalize and add URL to frontier if not visited and within depth."""
        url = normalize_url(url)
        if url is None:
            return
        if depth > self.max_depth:
            return

        with self.visited_lock:
            if url in self.visited:
                return
            self.visited.add(url)

        self.frontier.put((url, depth))

    def _extract_links(self, base_url: str, html_text: str) -> list[str]:
        """Parse HTML and extract all href links."""
        parser = HTMLProcessor()
        try:
            parser.feed(html_text)
        except html.parser.HTMLParseError as e:
            logger.error("HTML parse error for %s: %s", base_url, e)
            return [], "", ""

        # Resolve relative links
        resolved = []
        for link in parser.links:
            resolved_url = normalize_url(link, base_url)
            if resolved_url:
                resolved.append(resolved_url)

        return resolved, parser.get_text(), parser.title

    def _worker(self):
        """Worker thread: fetch pages, extract links, update index."""
        while not self._should_stop():
            try:
                url, depth = self.frontier.get(timeout=1)
            except queue.Empty:
                if self._should_stop():
                    break
                continue

            if self._should_stop():
                self.frontier.task_done()
                break

            # Respect robots.txt
            if not self.robots_cache.can_fetch(url):
                logger.info("Blocked by robots.txt: %s", url)
                self.frontier.task_done()
                continue

            # Rate limiting
            self.rate_limiter.wait_if_needed(url)

            # Update progress
            if self.progress_callback:
                with self.stats_lock:
                    qsize = self.frontier.qsize()
                self.progress_callback(
                    crawled=self.crawled,
                    queued=qsize,
                    failed=self.failed,
                    current_url=url,
                )

            # Fetch
            content, content_type = self.fetcher.fetch(url)
            if content is None:
                with self.stats_lock:
                    self.failed += 1
                self.frontier.task_done()
                continue

            # Parse and extract
            links, text, title = self._extract_links(url, content)

            # Index this page
            with self.stats_lock:
                self.doc_id_counter += 1
                doc_id = self.doc_id_counter
                self.crawled += 1

            self.indexer.add_document(doc_id, url, title, text)

            # Count domain links
            domain_counts: dict[str, int] = {}
            for link in links:
                d = get_domain(link)
                domain_counts[d] = domain_counts.get(d, 0) + 1

            with self.domain_links_lock:
                for d, count in domain_counts.items():
                    self.domain_links[d] = self.domain_links.get(d, 0) + count

            # Add new links to frontier
            for link in links:
                if self._should_stop():
                    break
                self._add_to_frontier(link, depth + 1)

            self.frontier.task_done()

    def run(self) -> Indexer:
        """Start the crawl and return the populated indexer."""
        start_time = time.time()

        # Seed the frontier
        for seed_url in self.seed_urls:
            self._add_to_frontier(seed_url, 0)

        # Start worker threads
        threads = []
        for _ in range(self.num_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            threads.append(t)

        # Wait for workers to finish (frontier empty or limit reached)
        # Monitor progress and handle graceful shutdown
        while any(t.is_alive() for t in threads):
            # Check if we've reached the limit and queue is being drained
            if self._should_stop():
                # Give workers time to finish current items
                # Drain remaining queue
                while not self.frontier.empty():
                    try:
                        self.frontier.get_nowait()
                        self.frontier.task_done()
                    except queue.Empty:
                        break
                self.stop_flag.set()
                break

            if self.progress_callback:
                with self.stats_lock:
                    crawled = self.crawled
                    failed = self.failed
                qsize = self.frontier.qsize()
                self.progress_callback(
                    crawled=crawled,
                    queued=qsize,
                    failed=failed,
                    current_url="",
                )
            time.sleep(0.1)

        # Wait for all threads to finish
        for t in threads:
            t.join(timeout=5)

        # Finalize index
        self.indexer.finalize()

        elapsed = time.time() - start_time
        self.crawl_duration = elapsed
        logger.info(
            "Crawl complete: %d pages, %d terms, %.2fs",
            self.indexer.doc_count,
            self.indexer.total_terms,
            elapsed,
        )

        return self.indexer

    def get_top_domains(self, n: int = 10) -> list[tuple[str, int]]:
        """Get top N most linked domains."""
        with self.domain_links_lock:
            sorted_domains = sorted(
                self.domain_links.items(), key=lambda x: x[1], reverse=True
            )
        return sorted_domains[:n]
