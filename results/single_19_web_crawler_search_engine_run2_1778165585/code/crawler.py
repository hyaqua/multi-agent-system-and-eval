"""Web crawler with thread pool, shared work queue, and rate limiting."""

import threading
import queue
import time
import logging
from typing import Set, Optional, List
from datetime import datetime

from url_utils import normalize_url, get_domain
from robots import RobotsChecker
from fetcher import fetch_url, FetchResult
from html_parser import parse_html
from indexer import Document, InvertedIndex
from reporter import CrawlReporter

logger = logging.getLogger(__name__)


class CrawlJob:
    """Tracks a crawl job's status."""

    def __init__(self, job_id: str, seeds: List[str], depth: int, limit: int):
        self.job_id = job_id
        self.seeds = seeds
        self.depth = depth
        self.limit = limit
        self.pages_crawled = 0
        self.pages_queued = 0
        self.pages_failed = 0
        self.current_url = ""
        self.status = "pending"  # pending, running, completed, failed
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error: str = ""


class CrawlManager:
    """Manages web crawling with thread pool and shared work queue."""

    def __init__(
        self,
        seeds: List[str],
        depth: int = 2,
        limit: int = 100,
        workers: int = 5,
        timeout: float = 10.0,
        user_agent: str = "SimpleCrawler/1.0",
        index: Optional[InvertedIndex] = None,
        reporter: Optional[CrawlReporter] = None,
    ):
        self.seeds = [s.strip() for s in seeds if s.strip()]
        self.depth = depth
        self.limit = limit
        self.workers = workers
        self.timeout = timeout
        self.user_agent = user_agent
        self.index = index or InvertedIndex()
        self.reporter = reporter or CrawlReporter()

        # Seed domains for scoping
        self.seed_domains: Set[str] = set()
        for seed in self.seeds:
            domain = get_domain(seed)
            if domain:
                self.seed_domains.add(domain)

        # URL normalization cache
        self._seen_urls: Set[str] = set()

        # Work queue: each item is (url, depth)
        self._work_queue: queue.Queue = queue.Queue()
        self._queue_lock = threading.Lock()
        self._queued_count = 0

        # Thread-safe counters
        self._crawled_lock = threading.Lock()
        self._pages_crawled = 0
        self._pages_failed = 0
        self._current_url = ""
        self._current_url_lock = threading.Lock()

        # Robots checker (shared)
        self.robots_checker = RobotsChecker(
            user_agent=user_agent, timeout=timeout
        )

        # Shutdown flag
        self._stop_event = threading.Event()

        # Job tracking
        self._jobs: dict = {}
        self._job_counter = 0
        self._job_lock = threading.Lock()

        # Domain link counting for summary
        self._domain_links: dict = {}
        self._domain_links_lock = threading.Lock()

        # Start time
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    @property
    def pages_crawled(self) -> int:
        with self._crawled_lock:
            return self._pages_crawled

    @property
    def pages_failed(self) -> int:
        with self._crawled_lock:
            return self._pages_failed

    @property
    def pages_queued(self) -> int:
        return self._work_queue.qsize()

    @property
    def current_url(self) -> str:
        with self._current_url_lock:
            return self._current_url

    @current_url.setter
    def current_url(self, url: str):
        with self._current_url_lock:
            self._current_url = url

    def create_job(self, seeds: List[str], depth: int, limit: int) -> str:
        """Create a new crawl job and return its job_id."""
        with self._job_lock:
            self._job_counter += 1
            job_id = f"crawl_{self._job_counter}"
            job = CrawlJob(job_id, seeds, depth, limit)
            self._jobs[job_id] = job
            return job_id

    def get_job(self, job_id: str) -> Optional[CrawlJob]:
        with self._job_lock:
            return self._jobs.get(job_id)

    def _is_in_scope(self, url: str) -> bool:
        """Check if URL is in scope of seed domains."""
        domain = get_domain(url)
        return domain in self.seed_domains

    def _enqueue_url(self, url: str, depth: int):
        """Add a URL to the work queue if not already seen and within limit."""
        normalized = normalize_url(url)
        if not normalized:
            return

        if normalized in self._seen_urls:
            return

        # Check limit
        with self._crawled_lock:
            total_processed = self._pages_crawled + self._pages_failed
            if total_processed + self._work_queue.qsize() >= self.limit:
                return

        self._seen_urls.add(normalized)
        self._work_queue.put((normalized, depth))

    def _crawl_worker(self, worker_id: int):
        """Worker thread that fetches and processes URLs from the queue."""
        while not self._stop_event.is_set():
            try:
                url, depth = self._work_queue.get(timeout=1)
            except queue.Empty:
                # Check if queue is truly empty and we should stop
                if self._work_queue.qsize() == 0:
                    # All workers might be waiting; check if we're done
                    with self._crawled_lock:
                        if self._pages_crawled + self._pages_failed >= self.limit:
                            break
                    # If no more work items and no workers busy, stop
                    if self._work_queue.qsize() == 0:
                        # Give it another moment to see if more items come
                        continue
                continue

            # Check limit again
            with self._crawled_lock:
                if self._pages_crawled >= self.limit:
                    self._work_queue.task_done()
                    continue

            # Update current URL
            self.current_url = url

            # Check robots.txt
            domain = get_domain(url)
            if domain:
                self.robots_checker.fetch_robots(domain)
                if not self.robots_checker.is_allowed(url):
                    logger.debug(f"Blocked by robots.txt: {url}")
                    self._work_queue.task_done()
                    continue

                # Enforce crawl delay
                self.robots_checker.wait_if_needed(domain)

            # Fetch the URL
            result = fetch_url(url, timeout=self.timeout, user_agent=self.user_agent)

            if result.success and result.content:
                # Parse HTML
                title, text, links = parse_html(result.content)

                # Count domain links for summary
                domain_counts: dict = {}
                for link in links:
                    norm_link = normalize_url(link, result.final_url or url)
                    if norm_link:
                        link_domain = get_domain(norm_link)
                        if link_domain:
                            domain_counts[link_domain] = domain_counts.get(link_domain, 0) + 1
                with self._domain_links_lock:
                    for d, count in domain_counts.items():
                        self._domain_links[d] = self._domain_links.get(d, 0) + count

                # Create document and index
                doc = Document(
                    url=result.final_url or url,
                    title=title,
                    text=text,
                    links=links,
                )
                self.index.add_document(doc)

                # Enqueue discovered links if within depth
                if depth < self.depth:
                    for link in links:
                        norm_link = normalize_url(link, result.final_url or url)
                        if norm_link and self._is_in_scope(norm_link):
                            self._enqueue_url(norm_link, depth + 1)

                with self._crawled_lock:
                    self._pages_crawled += 1

            else:
                with self._crawled_lock:
                    self._pages_failed += 1

            self._work_queue.task_done()

            # Live progress update
            self.reporter.update(
                self.pages_crawled,
                self.pages_queued,
                self.pages_failed,
                self.current_url,
            )

    def crawl(self) -> InvertedIndex:
        """Run the crawl with the thread pool. Returns the built index."""
        self._start_time = time.time()
        self.reporter.start()

        # Initialize queue with seed URLs
        for seed in self.seeds:
            normalized = normalize_url(seed)
            if normalized:
                self._seen_urls.add(normalized)
                self._work_queue.put((normalized, 0))

        # Start worker threads
        threads = []
        for i in range(self.workers):
            t = threading.Thread(target=self._crawl_worker, args=(i,), daemon=True)
            t.start()
            threads.append(t)

        # Wait for all work to complete or limit reached
        while True:
            with self._crawled_lock:
                if self._pages_crawled >= self.limit:
                    break

            # Check if queue is empty and all items processed
            if self._work_queue.qsize() == 0:
                # Give a moment for in-flight tasks
                time.sleep(0.5)
                if self._work_queue.qsize() == 0:
                    # Check if all workers are waiting (queue empty)
                    with self._crawled_lock:
                        if self._pages_crawled > 0:
                            # Small grace period
                            time.sleep(1.0)
                            if self._work_queue.qsize() == 0:
                                break

        # Signal stop and wait for threads
        self._stop_event.set()
        for t in threads:
            t.join(timeout=5)

        self._end_time = time.time()
        self.reporter.stop()
        self.reporter.print_summary(
            self.pages_crawled,
            len(self.index.index),
            self.get_domain_links(),
            self._end_time - self._start_time,
        )

        return self.index

    def get_domain_links(self) -> dict:
        with self._domain_links_lock:
            return dict(self._domain_links)
