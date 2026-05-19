"""
Asynchronous web crawler with thread pool, shared work queue,
robots.txt compliance, and configurable limits.
"""

import threading
import urllib.request
import urllib.error
import urllib.parse
import socket
import ssl
import time
import sys
import logging
from collections import defaultdict
from urllib.parse import urlparse, urljoin

from crawler.robots import RobotsChecker
from crawler.html_parser import parse_html
from crawler.indexer import Indexer

logger = logging.getLogger(__name__)

# Sentinel for signaling workers to stop
_STOP = object()


def normalize_url(url, base_url=None):
    """Normalize URL: resolve relative, strip fragment, lowercase scheme+host."""
    if base_url:
        url = urljoin(base_url, url)
    
    parsed = urlparse(url)
    
    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if scheme == 'http' and netloc.endswith(':80'):
        netloc = netloc[:-3]
    elif scheme == 'https' and netloc.endswith(':443'):
        netloc = netloc[:-4]
    
    # Rebuild URL without fragment
    normalized = urllib.parse.urlunparse((
        scheme,
        netloc,
        parsed.path or '/',
        parsed.params,
        parsed.query,
        ''  # No fragment
    ))
    
    return normalized


def is_same_domain(url, seed_domains):
    """Check if URL belongs to any of the seed domains."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    for seed in seed_domains:
        if domain == seed or domain.endswith('.' + seed):
            return True
    return False


def get_domain(url):
    """Extract domain from URL."""
    return urlparse(url).netloc.lower()


class CrawlStats:
    """Thread-safe crawl statistics."""
    def __init__(self):
        self.lock = threading.Lock()
        self.pages_crawled = 0
        self.pages_queued = 0
        self.pages_failed = 0
        self.current_url = ""
        self.start_time = time.time()
        self.running = True
    
    def elapsed(self):
        return time.time() - self.start_time
    
    def snapshot(self):
        with self.lock:
            return {
                'pages_crawled': self.pages_crawled,
                'pages_queued': self.pages_queued,
                'pages_failed': self.pages_failed,
                'current_url': self.current_url,
                'elapsed': self.elapsed(),
            }


class Crawler:
    """Web crawler with thread pool and work queue."""
    
    def __init__(self, seed_urls, depth=2, max_pages=100, num_workers=5, timeout=10, silent=False):
        self.seed_urls = seed_urls
        self.max_depth = depth
        self.max_pages = max_pages
        self.num_workers = num_workers
        self.timeout = timeout
        self.silent = silent
        
        # Work queue protected by condition variable
        self._cv = threading.Condition()
        self._queue = []
        self._active_workers = 0
        self._finished = False
        
        # Seen URLs (deduplication)
        self._seen = set()
        self._seen_lock = threading.Lock()
        
        # Seed domains for scope checking
        self.seed_domains = set()
        for url in seed_urls:
            self.seed_domains.add(get_domain(url))
        
        # Robots checker
        self.robots = RobotsChecker(timeout=timeout)
        
        # Indexer
        self.indexer = Indexer()
        
        # Stats
        self.stats = CrawlStats()
    
    def _add_to_queue(self, url, depth):
        """Add URL to queue if not seen and within scope. Thread-safe."""
        normalized = normalize_url(url)
        
        with self._seen_lock:
            if normalized in self._seen:
                return
            self._seen.add(normalized)
        
        with self._cv:
            self._queue.append((normalized, depth))
            self.stats.pages_queued += 1
            self._cv.notify()
    
    def _fetch_url(self, url):
        """Fetch a URL and return (content, content_type, final_url)."""
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'CrawlerBot/1.0',
                'Accept': 'text/html,application/xhtml+xml,*/*',
            }
        )
        
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            final_url = response.geturl()
            content = response.read()
        
        return content, content_type, final_url
    
    def _is_html(self, content_type):
        """Check if content type indicates HTML."""
        if not content_type:
            return True
        ct = content_type.lower().split(';')[0].strip()
        return ct in ('text/html', 'application/xhtml+xml')
    
    def _process_url(self, url, depth):
        """Fetch and process a single URL. Return number of new links added."""
        domain = get_domain(url)
        
        # Check robots.txt
        self.robots.ensure_robots_loaded(url)
        if not self.robots.is_allowed(url):
            logger.info(f"Blocked by robots.txt: {url}")
            return 0
        
        # Respect crawl delay
        self.robots.wait_if_needed(domain)
        
        # Update current URL display
        with self.stats.lock:
            self.stats.current_url = url
        
        # Fetch the page
        try:
            content, content_type, final_url = self._fetch_url(url)
        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error {e.code} for {url}")
            with self.stats.lock:
                self.stats.pages_failed += 1
            self.robots.mark_fetched(domain)
            return 0
        except urllib.error.URLError as e:
            logger.warning(f"URL error for {url}: {e.reason}")
            with self.stats.lock:
                self.stats.pages_failed += 1
            self.robots.mark_fetched(domain)
            return 0
        except (socket.timeout, TimeoutError) as e:
            logger.warning(f"Timeout for {url}")
            with self.stats.lock:
                self.stats.pages_failed += 1
            self.robots.mark_fetched(domain)
            return 0
        except ssl.SSLError as e:
            logger.warning(f"SSL error for {url}: {e}")
            with self.stats.lock:
                self.stats.pages_failed += 1
            self.robots.mark_fetched(domain)
            return 0
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            with self.stats.lock:
                self.stats.pages_failed += 1
            self.robots.mark_fetched(domain)
            return 0
        
        self.robots.mark_fetched(domain)
        
        # Check Content-Type
        if not self._is_html(content_type):
            logger.info(f"Skipping non-HTML content ({content_type}): {url}")
            return 0
        
        # Parse HTML
        try:
            html_str = content.decode('utf-8', errors='replace')
        except Exception:
            html_str = content.decode('latin-1', errors='replace')
        
        text, title, links = parse_html(html_str, final_url or url)
        
        # Add to index
        self.indexer.add_document(final_url or url, title, text)
        
        # Track outbound link domains
        self.indexer.track_links(links)
        
        # Update stats
        with self.stats.lock:
            self.stats.pages_crawled += 1
        
        # Discover new links if within depth
        new_links = 0
        if depth < self.max_depth:
            for link in links:
                # Check page limit before adding more
                with self.stats.lock:
                    if self.stats.pages_crawled >= self.max_pages:
                        break
                
                normalized_link = normalize_url(link)
                if is_same_domain(normalized_link, self.seed_domains):
                    with self._seen_lock:
                        if normalized_link not in self._seen:
                            self._seen.add(normalized_link)
                            with self._cv:
                                self._queue.append((normalized_link, depth + 1))
                                self.stats.pages_queued += 1
                                self._cv.notify()
                            new_links += 1
        
        return new_links
    
    def _worker(self, worker_id):
        """Worker thread loop."""
        while True:
            with self._cv:
                while not self._queue and not self._finished:
                    self._active_workers -= 1
                    # Check if all workers are idle and queue is empty
                    if self._active_workers == 0 and not self._queue:
                        self._finished = True
                        self._cv.notify_all()
                        break
                    self._cv.wait(timeout=0.5)
                    self._active_workers += 1
                
                if self._finished or not self._queue:
                    self._active_workers -= 1
                    self._cv.notify_all()
                    return
                
                url, depth = self._queue.pop(0)
                self._active_workers += 1
            
            # Check page limit
            with self.stats.lock:
                if self.stats.pages_crawled >= self.max_pages:
                    with self._cv:
                        self._queue.clear()
                        self._finished = True
                        self._cv.notify_all()
                    return
            
            self._process_url(url, depth)
            
            with self._cv:
                self._active_workers -= 1
    
    def _progress_reporter(self):
        """Thread that prints live crawl progress."""
        while not self._finished:
            with self.stats.lock:
                crawled = self.stats.pages_crawled
                queued = self.stats.pages_queued
                failed = self.stats.pages_failed
                current = self.stats.current_url
                elapsed = self.stats.elapsed()
            
            if not self.silent:
                pending = max(0, queued - crawled - failed)
                display_url = current if len(current) <= 65 else current[:62] + '...'
                
                sys.stdout.write(
                    f"\r[Progress] Crawled: {crawled} | Queued: {pending} | "
                    f"Failed: {failed} | {display_url} | {elapsed:.1f}s    "
                )
                sys.stdout.flush()
            time.sleep(0.15)
        
        # Clear the progress line
        if not self.silent:
            sys.stdout.write("\r" + " " * 120 + "\r")
            sys.stdout.flush()
    
    def crawl(self):
        """Start crawling and return when done."""
        # Seed the queue
        for url in self.seed_urls:
            normalized = normalize_url(url)
            with self._seen_lock:
                if normalized not in self._seen:
                    self._seen.add(normalized)
            with self._cv:
                self._queue.append((normalized, 0))
                self.stats.pages_queued += 1
        
        # Start progress reporter
        reporter = threading.Thread(target=self._progress_reporter, daemon=True)
        reporter.start()
        
        # Start worker threads
        workers = []
        with self._cv:
            self._active_workers = self.num_workers
        
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker, args=(i,), daemon=True)
            t.start()
            workers.append(t)
        
        # Wait for workers to complete
        for t in workers:
            t.join()
        
        # Wait for reporter
        reporter.join(timeout=1)
        
        # Print summary
        self._print_summary()
        
        return self.indexer
    
    def _print_summary(self):
        """Print crawl summary report."""
        if self.silent:
            return
        elapsed = self.stats.elapsed()
        print(f"\n{'='*60}")
        print(f"CRAWL COMPLETE")
        print(f"{'='*60}")
        print(f"Total pages crawled: {self.stats.pages_crawled}")
        print(f"Total unique terms:  {len(self.indexer.index)}")
        print(f"Total failed:        {self.stats.pages_failed}")
        print(f"Time elapsed:        {elapsed:.2f} seconds")
        if elapsed > 0:
            print(f"Pages/sec:           {self.stats.pages_crawled / elapsed:.2f}")
        print(f"\nTop 10 most linked domains:")
        top_domains = self.indexer.get_top_linked_domains(10)
        if top_domains:
            for domain, count in top_domains:
                print(f"  {domain}: {count} links")
        else:
            print("  (no external links found)")
        print(f"{'='*60}")


class CrawlJob:
    """Represents an asynchronous crawl job."""
    
    def __init__(self, job_id, seed_urls, depth, max_pages, num_workers, timeout):
        self.job_id = job_id
        self.seed_urls = seed_urls
        self.depth = depth
        self.max_pages = max_pages
        self.num_workers = num_workers
        self.timeout = timeout
        self.status = "pending"
        self.crawler = None
        self.indexer = None
        self.error = None
        self.start_time = None
        self.end_time = None
        self.thread = None
    
    def get_progress(self):
        """Get current progress."""
        if self.status == "pending":
            return {"status": "pending", "pages_crawled": 0}
        elif self.status == "running" and self.crawler:
            snap = self.crawler.stats.snapshot()
            snap["status"] = "running"
            return snap
        elif self.status == "completed":
            return {
                "status": "completed",
                "pages_crawled": self.crawler.stats.pages_crawled if self.crawler else 0,
                "elapsed": (self.end_time - self.start_time) if self.start_time and self.end_time else 0
            }
        elif self.status == "failed":
            return {"status": "failed", "error": str(self.error)}
        return {"status": "unknown"}
    
    def run(self):
        """Run the crawl in this thread."""
        self.status = "running"
        self.start_time = time.time()
        try:
            self.crawler = Crawler(
                self.seed_urls,
                depth=self.depth,
                max_pages=self.max_pages,
                num_workers=self.num_workers,
                timeout=self.timeout,
                silent=True  # Don't print progress for background jobs
            )
            self.indexer = self.crawler.crawl()
            self.status = "completed"
        except Exception as e:
            logger.error(f"Crawl job {self.job_id} failed: {e}")
            self.status = "failed"
            self.error = e
        self.end_time = time.time()
