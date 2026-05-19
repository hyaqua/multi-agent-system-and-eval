"""Crawler managing frontier queue, workers, robots.txt, rate limiting, depth tracking."""

import threading
import queue
import time
import sys
import urllib.request
import urllib.error
import ssl

from url_utils import normalize_url, get_domain, RobotsCache
from parser import HTMLContentParser
from crawl_stats import CrawlStats


class Crawler:
    """Web crawler with thread pool and frontier management."""

    def __init__(self, seed_urls, max_depth=2, max_pages=100, num_workers=5,
                 timeout=10, stats=None):
        self.seed_urls = seed_urls
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.num_workers = num_workers
        self.timeout = timeout
        self.stats = stats or CrawlStats()

        # Frontier queue: items are (url, depth)
        self.frontier = queue.Queue()

        # Track seen URLs
        self.seen_urls = set()
        self.seen_lock = threading.Lock()

        # Robots cache
        self.robots_cache = RobotsCache(timeout=timeout)

        # Documents collected
        self.documents = []
        self.documents_lock = threading.Lock()

        # Parser (created per thread, but we can reuse)
        self._parser = HTMLContentParser()

        # Stop event
        self.stop_event = threading.Event()

        # Link domain counter for summary
        self.linked_domains = {}
        self.linked_domains_lock = threading.Lock()

    def _fetch(self, url):
        """Fetch a URL and return the response data."""
        req = urllib.request.Request(url, headers={
            'User-Agent': 'WebCrawler/1.0',
            'Accept': 'text/html,application/xhtml+xml'
        })
        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                if content_type:
                    print(f"\nSKIP non-HTML: {url} [{content_type}]", file=sys.stderr)
                return None

            # Read with error handling for encoding
            raw = response.read()
            # Try to decode
            encoding = 'utf-8'
            # Look for charset in content-type
            if 'charset=' in content_type:
                parts = content_type.split('charset=')
                if len(parts) > 1:
                    encoding = parts[1].strip().split(';')[0].strip()

            try:
                html = raw.decode(encoding, errors='replace')
            except (LookupError, UnicodeDecodeError):
                html = raw.decode('utf-8', errors='replace')

            return html
        except urllib.error.HTTPError as e:
            print(f"\nERROR: {url} - HTTP {e.code}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"\nERROR: {url} - {e.reason}", file=sys.stderr)
            return None
        except ssl.SSLError as e:
            print(f"\nERROR: {url} - SSL error: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"\nERROR: {url} - {e}", file=sys.stderr)
            return None

    def _parse_page(self, html, url):
        """Parse HTML and return extracted data."""
        parser = HTMLContentParser()
        try:
            result = parser.parse_html(html)
        except Exception as e:
            print(f"\nERROR parsing {url}: {e}", file=sys.stderr)
            result = {'title': '', 'text': '', 'links': []}
        return result

    def _process_url(self, url, depth):
        """Process a single URL: fetch, parse, extract links."""
        # Check if we've hit the limit
        with self.documents_lock:
            if len(self.documents) >= self.max_pages:
                return

        # Check robots.txt
        if not self.robots_cache.is_allowed(url):
            print(f"\nBLOCKED by robots.txt: {url}", file=sys.stderr)
            return

        # Respect crawl delay
        self.robots_cache.wait_if_needed(url)

        # Update stats
        self.stats.set_current_url(url)

        # Fetch
        html = self._fetch(url)
        if html is None:
            self.stats.increment_failed()
            self.stats.decrement_queued()
            return

        # Parse
        result = self._parse_page(html, url)

        # Store document
        doc = {
            'url': url,
            'title': result.get('title', ''),
            'text': result.get('text', ''),
            'outlinks': result.get('links', [])
        }

        with self.documents_lock:
            self.documents.append(doc)
            self.stats.increment_crawled()
            self.stats.decrement_queued()

        # Enqueue new links if under depth limit
        if depth < self.max_depth:
            base_url = url
            for link in result.get('links', []):
                if self.stop_event.is_set():
                    break

                try:
                    absolute_url = normalize_url(link, base_url)
                except Exception:
                    continue

                if not absolute_url.startswith(('http://', 'https://')):
                    continue

                with self.seen_lock:
                    if absolute_url in self.seen_urls:
                        continue

                    with self.documents_lock:
                        if len(self.documents) + self.frontier.qsize() >= self.max_pages:
                            break

                    self.seen_urls.add(absolute_url)

                # Count linked domain
                domain = get_domain(absolute_url)
                if domain:
                    with self.linked_domains_lock:
                        self.linked_domains[domain] = self.linked_domains.get(domain, 0) + 1

                self.frontier.put((absolute_url, depth + 1))
                self.stats.increment_queued()

    def _worker(self):
        """Worker thread function."""
        while not self.stop_event.is_set():
            try:
                url, depth = self.frontier.get(timeout=0.5)
            except queue.Empty:
                # Check if we've reached the limit
                with self.documents_lock:
                    if len(self.documents) >= self.max_pages:
                        break
                # If queue is empty and all workers are idle, we're done
                if self.frontier.empty():
                    # Small additional wait to ensure no new items are added
                    time.sleep(0.2)
                    if self.frontier.empty():
                        break
                continue

            try:
                self._process_url(url, depth)
            except Exception as e:
                print(f"\nERROR processing {url}: {e}", file=sys.stderr)
                self.stats.increment_failed()
                self.stats.decrement_queued()
            finally:
                self.frontier.task_done()

    def crawl(self):
        """Run the crawl."""
        self.stats.start()

        # Enqueue seeds
        for url in self.seed_urls:
            normalized = normalize_url(url)
            if normalized.startswith(('http://', 'https://')):
                with self.seen_lock:
                    if normalized not in self.seen_urls:
                        self.seen_urls.add(normalized)
                        self.frontier.put((normalized, 0))
                        self.stats.increment_queued()

        if self.frontier.empty():
            print("No valid seed URLs to crawl.")
            self.stats.finish()
            return

        # Start worker threads
        threads = []
        for _ in range(self.num_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            threads.append(t)

        # Progress reporting
        try:
            while any(t.is_alive() for t in threads):
                # Print progress
                progress = self.stats.get_progress_line()
                sys.stdout.write(progress)
                sys.stdout.flush()
                time.sleep(0.3)

                # Check if we've reached the limit
                with self.documents_lock:
                    if len(self.documents) >= self.max_pages:
                        self.stop_event.set()
                        # Drain remaining queue items to unblock workers
                        while not self.frontier.empty():
                            try:
                                self.frontier.get_nowait()
                                self.frontier.task_done()
                            except queue.Empty:
                                break
                        break
        except KeyboardInterrupt:
            print("\n\nCrawl interrupted by user.")
            self.stop_event.set()

        # Wait for threads to finish
        for t in threads:
            t.join(timeout=2)

        self.stats.finish()
        sys.stdout.write("\r" + " " * 100 + "\r")  # Clear progress line
        sys.stdout.flush()

        return self.documents

    def get_linked_domains(self):
        """Return the domain link counts."""
        with self.linked_domains_lock:
            return dict(self.linked_domains)
