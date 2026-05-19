"""Asynchronous web crawler using thread pool and shared work queue."""

import queue
import sys
import threading
import time
import urllib.request
import urllib.error
import ssl
import socket
from typing import Optional

from utils import (
    normalize_url, get_domain, TextExtractor, LinkExtractor, TitleExtractor
)
from robots import RobotsCache
from indexer import Indexer


class ProgressTracker:
    """Thread-safe progress display with in-place terminal updates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.pages_crawled = 0
        self.pages_failed = 0
        self.pages_queued = 0
        self.current_url = ''
        self._start_time = time.time()
        self._running = True

    def update(self, crawled: int = 0, queued: int = 0, failed: int = 0,
               current_url: str = '') -> None:
        """Update tracked values and redraw progress line."""
        with self._lock:
            self.pages_crawled += crawled
            self.pages_queued = queued
            self.pages_failed += failed
            if current_url:
                # Truncate long URLs for display
                self.current_url = (current_url[:80] + '...') if len(current_url) > 80 else current_url

            # Build progress line
            elapsed = time.time() - self._start_time
            line = (f'\rCrawling: {self.pages_crawled} pages | '
                    f'{self.pages_queued} queued | '
                    f'{self.pages_failed} failed | '
                    f'{elapsed:.0f}s | '
                    f'{self.current_url}')

            # Clear to end of line
            line = line.ljust(120)[:120]
            sys.stderr.write(line)
            sys.stderr.flush()

    def finish(self) -> None:
        """End progress display with a newline."""
        self._running = False
        sys.stderr.write('\n')
        sys.stderr.flush()


class Crawler:
    """Multi-threaded web crawler with robots.txt compliance and rate limiting."""

    def __init__(
        self,
        seeds: list[str],
        depth: int = 2,
        limit: int = 100,
        workers: int = 5,
        timeout: float = 10.0,
        user_agent: str = 'SearchCrawler/1.0',
        indexer: Optional[Indexer] = None,
    ) -> None:
        self.seeds = seeds
        self.max_depth = depth
        self.max_pages = limit
        self.num_workers = workers
        self.timeout = timeout
        self.user_agent = user_agent
        self.indexer = indexer or Indexer()

        # Work queue: (url, depth) tuples
        self._work_queue: queue.Queue = queue.Queue()
        # Track seen URLs to avoid duplicates
        self._seen_urls: set[str] = set()
        self._seen_lock = threading.Lock()
        # Track domain -> link count (for summary)
        self._domain_links: dict[str, int] = {}
        self._domain_links_lock = threading.Lock()
        # Progress tracker
        self.progress = ProgressTracker()
        # Robots cache
        self.robots_cache = RobotsCache(user_agent=user_agent)
        # Control
        self._stop_event = threading.Event()
        self._pages_crawled_count = 0
        self._pages_failed_count = 0
        self._count_lock = threading.Lock()
        self._start_time = 0.0
        self._end_time = 0.0

        # SSL context - don't verify certs for robustness
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _is_in_scope(self, url: str) -> bool:
        """Check if URL is http/https and not already seen."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        return True

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract and normalize all links from HTML."""
        try:
            extractor = LinkExtractor()
            extractor.feed(html)
            extractor.close()
        except Exception:
            return []

        links = []
        for href in extractor.links:
            normalized = normalize_url(base_url, href)
            if normalized:
                links.append(normalized)
        return links

    def _extract_text(self, html: str) -> str:
        """Extract visible text from HTML."""
        try:
            extractor = TextExtractor()
            extractor.feed(html)
            extractor.close()
            return extractor.get_text()
        except Exception:
            return ''

    def _extract_title(self, html: str) -> str:
        """Extract <title> from HTML."""
        try:
            extractor = TitleExtractor()
            extractor.feed(html)
            extractor.close()
            return extractor.title or ''
        except Exception:
            return ''

    def _add_to_queue(self, url: str, depth: int) -> bool:
        """Add a URL to the work queue if not already seen. Returns True if added."""
        with self._seen_lock:
            if url in self._seen_urls:
                return False
            # Check page limit
            if self._pages_crawled_count + self._work_queue.qsize() >= self.max_pages:
                return False
            self._seen_urls.add(url)

        self._work_queue.put((url, depth))
        return True

    def _fetch(self, url: str) -> Optional[tuple[str, str]]:
        """Fetch a URL and return (html_content, content_type) or None on failure."""
        req = urllib.request.Request(
            url,
            headers={'User-Agent': self.user_agent,
                     'Accept': 'text/html,application/xhtml+xml,*/*'}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout,
                                        context=self._ssl_context) as resp:
                content_type = resp.headers.get('Content-Type', '')
                # Skip non-HTML content
                if 'text/html' not in content_type.lower() and \
                   'application/xhtml' not in content_type.lower():
                    return None

                # Read with size limit to avoid huge pages
                raw = resp.read(5 * 1024 * 1024)  # 5 MB limit
                # Try to decode
                charset = 'utf-8'
                # Try to extract charset from Content-Type
                for part in content_type.split(';'):
                    part = part.strip()
                    if part.lower().startswith('charset='):
                        charset = part.split('=', 1)[1].strip().strip('"\'')
                        break

                try:
                    html = raw.decode(charset, errors='replace')
                except (LookupError, UnicodeDecodeError):
                    html = raw.decode('utf-8', errors='replace')

                return (html, content_type)

        except urllib.error.HTTPError as e:
            print(f'[HTTP {e.code}] {url}', file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            reason = str(e.reason)
            print(f'[URL Error: {reason}] {url}', file=sys.stderr)
            return None
        except (ssl.SSLError, ssl.CertificateError) as e:
            print(f'[SSL Error] {url}: {e}', file=sys.stderr)
            return None
        except socket.timeout:
            print(f'[Timeout] {url}', file=sys.stderr)
            return None
        except ConnectionError as e:
            print(f'[Connection Error] {url}: {e}', file=sys.stderr)
            return None
        except Exception as e:
            print(f'[Error] {url}: {e}', file=sys.stderr)
            return None

    def _worker(self) -> None:
        """Worker thread: fetch, parse, index pages from the queue."""
        while not self._stop_event.is_set():
            try:
                url, depth = self._work_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                # Check if we've hit the limit
                with self._count_lock:
                    if self._pages_crawled_count >= self.max_pages:
                        continue

                domain = get_domain(url)

                # Check robots.txt
                if not self.robots_cache.is_allowed(url):
                    continue

                # Rate limiting
                self.robots_cache.wait_if_needed(domain)

                # Fetch
                result = self._fetch(url)
                if result is None:
                    with self._count_lock:
                        self._pages_failed_count += 1
                    self.progress.update(failed=1,
                                         queued=self._work_queue.qsize(),
                                         current_url=url)
                    continue

                html, _content_type = result

                # Parse
                title = self._extract_title(html)
                text = self._extract_text(html)

                # Index the page
                self.indexer.add_document(url, title, text)

                with self._count_lock:
                    self._pages_crawled_count += 1

                # Extract links if within depth
                if depth < self.max_depth:
                    links = self._extract_links(html, url)

                    # Track domain links for summary
                    domain_link_counts: dict[str, int] = {}
                    for link in links:
                        link_domain = get_domain(link)
                        domain_link_counts[link_domain] = \
                            domain_link_counts.get(link_domain, 0) + 1

                    with self._domain_links_lock:
                        for d, count in domain_link_counts.items():
                            self._domain_links[d] = self._domain_links.get(d, 0) + count

                    # Add to queue
                    for link in links:
                        if self._pages_crawled_count >= self.max_pages:
                            break
                        self._add_to_queue(link, depth + 1)

                self.progress.update(crawled=1,
                                     queued=self._work_queue.qsize(),
                                     current_url=url)

            except Exception as e:
                print(f'[Worker Error] {url}: {e}', file=sys.stderr)
                with self._count_lock:
                    self._pages_failed_count += 1
                self.progress.update(failed=1,
                                     queued=self._work_queue.qsize(),
                                     current_url=url)
            finally:
                self._work_queue.task_done()

    def run(self) -> Indexer:
        """Execute the crawl. Returns the populated Indexer."""
        self._start_time = time.time()

        # Seed the queue
        for seed_url in self.seeds:
            normalized = normalize_url(seed_url, seed_url)
            if normalized:
                self._add_to_queue(normalized, 0)

        initial_queued = self._work_queue.qsize()
        if initial_queued == 0:
            self._end_time = time.time()
            self.progress.finish()
            return self.indexer

        self.progress.update(queued=initial_queued, current_url='Starting...')

        # Start worker threads
        num_threads = min(self.num_workers, max(1, initial_queued))
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            threads.append(t)

        # Wait for all work to complete
        while not self._stop_event.is_set():
            with self._count_lock:
                crawled = self._pages_crawled_count
            if crawled >= self.max_pages:
                break
            # Check if queue is empty
            if self._work_queue.qsize() == 0:
                time.sleep(0.3)
                if self._work_queue.qsize() == 0:
                    break
            time.sleep(0.1)

        # Signal workers to stop
        self._stop_event.set()

        # Wait for threads to finish with generous timeout
        deadline = time.time() + 15.0
        for t in threads:
            remaining = deadline - time.time()
            if remaining > 0:
                t.join(timeout=remaining)

        self._end_time = time.time()
        self.progress.finish()

        # Compute TF-IDF
        self.indexer.compute_tfidf()
        duration = self._end_time - self._start_time
        self.indexer.set_crawl_duration(duration)

        return self.indexer

    def get_summary(self) -> str:
        """Generate a textual summary report."""
        elapsed = self._end_time - self._start_time if self._end_time > 0 else 0
        lines = []
        lines.append('=' * 60)
        lines.append('CRAWL SUMMARY')
        lines.append('=' * 60)
        lines.append(f'  Total pages crawled:  {self._pages_crawled_count}')
        lines.append(f'  Total pages failed:   {self._pages_failed_count}')
        lines.append(f'  Total unique terms:   {len(self.indexer.inverted_index)}')
        lines.append(f'  Elapsed time:         {elapsed:.2f} seconds')
        lines.append('')

        # Top 10 most linked domains
        with self._domain_links_lock:
            sorted_domains = sorted(self._domain_links.items(),
                                    key=lambda x: x[1], reverse=True)[:10]

        if sorted_domains:
            lines.append('  Top 10 most linked domains:')
            for i, (dom, count) in enumerate(sorted_domains, 1):
                lines.append(f'    {i:2d}. {dom:40s} {count:5d} links')
        else:
            lines.append('  No outbound links discovered.')

        lines.append('=' * 60)
        return '\n'.join(lines)

    @property
    def pages_crawled(self) -> int:
        return self._pages_crawled_count

    @property
    def pages_failed(self) -> int:
        return self._pages_failed_count
