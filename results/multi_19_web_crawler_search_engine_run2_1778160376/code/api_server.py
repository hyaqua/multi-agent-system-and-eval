"""
REST API server for the search engine.
Provides /search, /stats, /crawl, /crawl/<job_id> endpoints.
"""

import json
import threading
import uuid
import time
import urllib.parse
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class CrawlJob:
    """Represents an asynchronous crawl job."""

    def __init__(self, job_id: str, seed_urls: list[str], depth: int, limit: int,
                 num_workers: int, timeout: float):
        self.job_id = job_id
        self.status = "pending"
        self.pages_crawled = 0
        self.total_terms = 0
        self.error = None
        self.start_time = time.time()
        self.seed_urls = seed_urls
        self.depth = depth
        self.limit = limit
        self.num_workers = num_workers
        self.timeout = timeout
        self.lock = threading.Lock()

    def to_dict(self) -> dict:
        with self.lock:
            elapsed = time.time() - self.start_time
            return {
                "job_id": self.job_id,
                "status": self.status,
                "pages_crawled": self.pages_crawled,
                "total_terms": self.total_terms,
                "elapsed_seconds": round(elapsed, 1),
                "error": self.error,
            }


class JobManager:
    """Manages crawl jobs in a thread-safe manner."""

    def __init__(self):
        self.jobs: dict[str, CrawlJob] = {}
        self.lock = threading.Lock()

    def create_job(self, seed_urls: list[str], depth: int, limit: int,
                   num_workers: int, timeout: float) -> CrawlJob:
        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(job_id, seed_urls, depth, limit, num_workers, timeout)
        with self.lock:
            self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> CrawlJob | None:
        with self.lock:
            return self.jobs.get(job_id)

    def run_job(self, job: CrawlJob, on_complete):
        """Run a crawl job in a background thread."""

        def _run():
            from crawler import Crawler

            job.status = "running"
            try:
                crawler = Crawler(
                    seed_urls=job.seed_urls,
                    depth=job.depth,
                    limit=job.limit,
                    num_workers=job.num_workers,
                    timeout=job.timeout,
                )

                def progress_callback(crawled, queued, failed, current_url):
                    with job.lock:
                        job.pages_crawled = crawled

                crawler.progress_callback = progress_callback
                indexer = crawler.run()

                with job.lock:
                    job.pages_crawled = indexer.doc_count
                    job.total_terms = indexer.total_terms
                    job.status = "completed"

                # Call on_complete with the new indexer
                on_complete(job, indexer, crawler.crawl_duration)

            except Exception as e:
                logger.exception("Crawl job %s failed", job.job_id)
                with job.lock:
                    job.status = "failed"
                    job.error = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()


class SearchAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the search API."""

    # Class-level references set by the server
    search_engine = None
    search_engine_lock = threading.Lock()
    job_manager = None
    seed_urls = []
    crawl_depth = 2
    crawl_limit = 100
    crawl_workers = 5
    crawl_timeout = 10.0
    crawl_duration = 0.0
    index_file_path = None

    def log_message(self, format, *args):
        """Override to suppress default logging or redirect to our logger."""
        logger.debug("API: %s", format % args)

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _parse_query(self) -> dict[str, list[str]]:
        """Parse query string from the URL."""
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.parse_qs(parsed.query)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/search":
                self._handle_search()
            elif path == "/stats":
                self._handle_stats()
            elif path == "/crawl":
                # Check if this is /crawl/<job_id>
                # Actually, /crawl matches the job creation;
                # /crawl/{job_id} has a longer path
                self._handle_crawl_start()
            elif path.startswith("/crawl/"):
                job_id = path[len("/crawl/"):]
                self._handle_crawl_status(job_id)
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            logger.exception("Error handling request %s", self.path)
            self._send_json({"error": str(e)}, 500)

    def _handle_search(self):
        params = self._parse_query()
        query = params.get("q", [""])[0]
        limit_str = params.get("limit", ["10"])[0]
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 10
        limit = max(1, min(limit, 100))

        with self.__class__.search_engine_lock:
            engine = self.__class__.search_engine

        if engine is None:
            self._send_json({"error": "No index loaded"}, 503)
            return

        results = engine.search(query, limit)
        self._send_json({"results": results, "query": query, "total": len(results)})

    def _handle_stats(self):
        with self.__class__.search_engine_lock:
            engine = self.__class__.search_engine

        if engine is None:
            self._send_json({"error": "No index loaded"}, 503)
            return

        index_path = self.__class__.index_file_path
        index_size = 0
        if index_path and os.path.exists(index_path):
            index_size = os.path.getsize(index_path)

        self._send_json({
            "total_pages_crawled": engine.total_pages,
            "total_unique_terms": engine.total_terms,
            "index_size_bytes": index_size,
            "crawl_duration_seconds": round(self.__class__.crawl_duration, 2),
        })

    def _handle_crawl_start(self):
        job = self.__class__.job_manager.create_job(
            seed_urls=self.__class__.seed_urls,
            depth=self.__class__.crawl_depth,
            limit=self.__class__.crawl_limit,
            num_workers=self.__class__.crawl_workers,
            timeout=self.__class__.crawl_timeout,
        )

        def on_complete(job, indexer, duration):
            with self.__class__.search_engine_lock:
                from search_engine import SearchEngine
                self.__class__.search_engine = SearchEngine(indexer)
                self.__class__.crawl_duration = duration
                # Save index to file
                if self.__class__.index_file_path:
                    try:
                        indexer.save(self.__class__.index_file_path)
                    except Exception as e:
                        logger.error("Failed to save index: %s", e)

        self.__class__.job_manager.run_job(job, on_complete)
        self._send_json({"job_id": job.job_id, "status": "started"}, 202)

    def _handle_crawl_status(self, job_id: str):
        job = self.__class__.job_manager.get_job(job_id)
        if job is None:
            self._send_json({"error": "Job not found"}, 404)
            return
        self._send_json(job.to_dict())


def run_server(
    port: int,
    search_engine,
    seed_urls: list[str],
    depth: int,
    limit: int,
    workers: int,
    timeout: float,
    crawl_duration: float,
    index_file_path: str | None,
) -> None:
    """Start the HTTP API server."""
    SearchAPIHandler.search_engine = search_engine
    SearchAPIHandler.job_manager = JobManager()
    SearchAPIHandler.seed_urls = seed_urls
    SearchAPIHandler.crawl_depth = depth
    SearchAPIHandler.crawl_limit = limit
    SearchAPIHandler.crawl_workers = workers
    SearchAPIHandler.crawl_timeout = timeout
    SearchAPIHandler.crawl_duration = crawl_duration
    SearchAPIHandler.index_file_path = index_file_path

    server = HTTPServer(("0.0.0.0", port), SearchAPIHandler)
    logger.info("API server listening on port %d", port)
    print(f"\nAPI server running at http://localhost:{port}")
    print(f"Search interface: http://localhost:{port}/search?q=your_query")
    print(f"Stats: http://localhost:{port}/stats")
    print(f"Start crawl: http://localhost:{port}/crawl")
    print(f"Press Ctrl+C to stop the server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
