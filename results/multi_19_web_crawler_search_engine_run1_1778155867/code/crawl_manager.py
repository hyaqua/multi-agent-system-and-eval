"""Crawl controller: thread pool, work queue, progress reporting, job management."""

import threading
import queue
import time
import uuid
from collections import defaultdict

from url_utils import URLUtils
from fetcher import Fetcher
from robot_handler import RobotHandler
from html_parser import extract_text_and_links
from indexer import Indexer


class CrawlJob:
    """Represents a crawl job with status tracking."""

    def __init__(self, job_id: str, seeds: list[str], depth: int, limit: int):
        self.job_id = job_id
        self.seeds = seeds
        self.depth = depth
        self.limit = limit
        self.status = 'pending'  # pending, running, finished, failed
        self.pages_crawled = 0
        self.pages_queued = 0
        self.pages_failed = 0
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.current_url = ''


class CrawlManager:
    """
    Manages crawl jobs with a thread pool and shared work queue.
    Handles domain-level rate limiting and robots.txt checks.
    """

    def __init__(
        self,
        indexer: Indexer,
        url_utils: URLUtils,
        num_workers: int = 5,
        timeout: int = 10,
        depth: int = 2,
        limit: int = 100,
    ):
        self.indexer = indexer
        self.url_utils = url_utils
        self.num_workers = num_workers
        self.timeout = timeout
        self.default_depth = depth
        self.default_limit = limit

        self.work_queue: queue.Queue[tuple[str, int]] = queue.Queue()
        self.failed_urls: list[tuple[str, str]] = []  # (url, error)

        self.pages_crawled = 0
        self.pages_failed = 0
        self._lock = threading.Lock()
        self._active = False
        self._error_lock = threading.Lock()

        # Domain link counting: domain -> set of source pages
        self.domain_links: dict[str, set[str]] = defaultdict(set)

        # Current URL for progress display
        self.current_url = ''

        # Jobs tracking
        self.jobs: dict[str, CrawlJob] = {}
        self._job_lock = threading.Lock()

    def start_crawl(self, seeds: list[str], depth: int | None = None,
                    limit: int | None = None) -> CrawlJob:
        """
        Start a crawl synchronously. Returns a CrawlJob.
        This method blocks until crawling completes.
        """
        if depth is None:
            depth = self.default_depth
        if limit is None:
            limit = self.default_limit

        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(job_id, seeds, depth, limit)
        job.status = 'running'
        job.start_time = time.time()

        with self._job_lock:
            self.jobs[job_id] = job

        # Reset counters
        with self._lock:
            self.pages_crawled = 0
            self.pages_failed = 0
            self.current_url = ''

        # Seed the queue
        for seed_url in seeds:
            normalized = self.url_utils.normalize(seed_url)
            if normalized and self.url_utils.mark_visited(normalized):
                self.work_queue.put((normalized, 0))

        with self._lock:
            job.pages_queued = self.work_queue.qsize()

        # Create components for workers
        robot_handler = RobotHandler()
        fetcher = Fetcher(timeout=self.timeout)
        fetcher.set_error_callback(self._record_error)

        # Start worker threads
        self._active = True
        threads = []
        for _ in range(self.num_workers):
            t = threading.Thread(
                target=self._worker,
                args=(fetcher, robot_handler, depth, limit, job),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # Start progress reporter
        progress_thread = threading.Thread(
            target=self._progress_reporter,
            args=(job,),
            daemon=True,
        )
        progress_thread.start()

        # Wait for all workers
        for t in threads:
            t.join()

        self._active = False
        progress_thread.join(timeout=2)

        # Compute TF-IDF
        self.indexer.compute_tfidf()

        job.status = 'finished'
        job.end_time = time.time()
        with self._lock:
            job.pages_crawled = self.pages_crawled
            job.pages_failed = self.pages_failed

        with self._job_lock:
            self.jobs[job_id] = job

        return job

    def start_crawl_async(self, seeds: list[str], depth: int | None = None,
                          limit: int | None = None) -> CrawlJob:
        """Start a crawl in a background thread. Returns a CrawlJob immediately."""
        if depth is None:
            depth = self.default_depth
        if limit is None:
            limit = self.default_limit

        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(job_id, seeds, depth, limit)
        job.status = 'running'
        job.start_time = time.time()

        with self._job_lock:
            self.jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_async_crawl,
            args=(job, seeds, depth, limit),
            daemon=True,
        )
        thread.start()

        return job

    def _run_async_crawl(self, job: CrawlJob, seeds: list[str], depth: int, limit: int):
        """Run a crawl for an async job."""
        self.start_crawl(seeds, depth, limit)

    def get_job(self, job_id: str) -> CrawlJob | None:
        """Get a job by ID."""
        with self._job_lock:
            return self.jobs.get(job_id)

    def _worker(self, fetcher: Fetcher, robot_handler: RobotHandler,
                depth_limit: int, page_limit: int, job: CrawlJob):
        """Worker thread that processes URLs from the queue."""
        while self._active:
            try:
                url, current_depth = self.work_queue.get(timeout=1)
            except queue.Empty:
                # Check if queue is really done
                if self.work_queue.empty():
                    break
                continue

            with self._lock:
                if self.pages_crawled >= page_limit:
                    self.work_queue.task_done()
                    break

            # Update current URL for progress display
            with self._lock:
                self.current_url = url

            # Check robots.txt
            if not robot_handler.can_fetch(url):
                self.work_queue.task_done()
                continue

            # Rate limiting
            robot_handler.wait_if_needed(url)

            # Fetch
            html, _ = fetcher.fetch(url)

            if html is None:
                with self._lock:
                    self.pages_failed += 1
                self.work_queue.task_done()
                continue

            # Increment pages_crawled immediately on successful fetch
            # (before parsing/indexing, so pages with no indexable
            # tokens still count towards progress and --limit).
            with self._lock:
                self.pages_crawled += 1
                job.pages_crawled = self.pages_crawled

            # Parse
            text, links, title = extract_text_and_links(html)

            # Add to index (may return None if no tokens extracted,
            # but the page is already counted as crawled above)
            doc_id = self.indexer.add_document(url, title, text)

            if doc_id is not None:
                # Debug: show extracted text length / token count
                if __debug__:
                    print(f'[DEBUG] {url}: text_len={len(text)}, '
                          f'tokens={self.indexer.documents[doc_id].get("token_count", 0)}')

            # Extract links for further crawling (always, even if indexing yielded no tokens)
            if current_depth + 1 < depth_limit:
                for link in links:
                    normalized = self.url_utils.normalize(link, url)
                    if normalized and self.url_utils.mark_visited(normalized):
                        self.work_queue.put((normalized, current_depth + 1))

            # Track domain links for summary
            source_domain = self.url_utils.extract_domain(url)
            linked_domains = self.url_utils.extract_domains_from_links(links, url)
            with self._lock:
                for domain in linked_domains:
                    if domain != source_domain:  # Don't count self-links
                        self.domain_links[domain].add(url)

            with self._lock:
                job.pages_failed = self.pages_failed

            self.work_queue.task_done()

    def _record_error(self, url: str, message: str):
        """Record a fetch error."""
        with self._error_lock:
            self.failed_urls.append((url, message))
        # Print immediate log line
        print(f'[ERR] Failed to fetch {url}: {message}')

    def _progress_reporter(self, job: CrawlJob):
        """Display live progress on the terminal."""
        while self._active:
            with self._lock:
                crawled = self.pages_crawled
                queued = self.work_queue.qsize()
                failed = self.pages_failed
                current = self.current_url

            # Truncate current URL for display
            display_url = current
            if len(display_url) > 80:
                display_url = display_url[:77] + '...'

            print(
                f'\rCrawled: {crawled} | Queued: {queued} | '
                f'Failed: {failed} | Current: {display_url}'
                f'{" " * 20}',
                end='',
                flush=True,
            )

            time.sleep(1)

        # Final line
        with self._lock:
            crawled = self.pages_crawled
            failed = self.pages_failed
        print(f'\rCrawled: {crawled} | Queued: 0 | Failed: {failed} | Done'
              f'{" " * 40}')

    def get_top_domains(self, n: int = 10) -> list[tuple[str, int]]:
        """Get top N domains by inbound link count."""
        with self._lock:
            domain_counts = [
                (domain, len(sources))
                for domain, sources in self.domain_links.items()
            ]
        domain_counts.sort(key=lambda x: x[1], reverse=True)
        return domain_counts[:n]

    def get_failed_urls(self) -> list[tuple[str, str]]:
        """Get list of (url, error) for failed fetches."""
        with self._error_lock:
            return list(self.failed_urls)
