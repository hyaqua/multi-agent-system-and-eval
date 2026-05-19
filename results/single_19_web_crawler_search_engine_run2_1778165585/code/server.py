"""REST API server for the search engine using http.server."""

import json
import time
import threading
import urllib.parse
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable

from indexer import InvertedIndex


class SearchAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the search engine REST API."""

    # Class-level references (set by server setup)
    index: InvertedIndex = None
    crawl_manager = None  # CrawlManager instance
    seeds: list = []
    depth: int = 2
    limit: int = 100
    workers: int = 5
    timeout: float = 10.0
    start_time: float = 0.0
    crawl_duration: float = 0.0
    index_size_bytes: int = 0

    def log_message(self, format, *args):
        """Suppress default logging; use our own."""
        pass

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status=200):
        """Send an HTML response."""
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse_query(self) -> dict:
        """Parse query string from the URL."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        return params

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/search":
                self._handle_search()
            elif path == "/stats":
                self._handle_stats()
            elif path == "/crawl" or path == "/crawl/":
                self._handle_crawl_start()
            elif path.startswith("/crawl/") and len(path) > len("/crawl/"):
                self._handle_crawl_status(path)
            elif path == "/":
                self._serve_search_page()
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_search(self):
        """Handle /search?q=query&limit=N"""
        params = self._parse_query()
        query = params.get("q", [""])[0].strip()
        limit_str = params.get("limit", ["20"])[0]

        if not query:
            self._send_json({"error": "Missing query parameter 'q'"}, 400)
            return

        try:
            limit = int(limit_str)
            limit = max(1, min(limit, 200))
        except ValueError:
            limit = 20

        if self.index is None or self.index.doc_count == 0:
            self._send_json({"results": [], "total": 0, "query": query})
            return

        results = self.index.search(query, limit=limit)

        self._send_json({
            "results": results,
            "total": len(results),
            "query": query,
        })

    def _handle_stats(self):
        """Handle /stats endpoint."""
        index_size = 0
        if self.index is not None:
            # Estimate index size
            try:
                import sys
                index_size = sys.getsizeof(self.index.index) + sys.getsizeof(self.index.documents)
            except Exception:
                index_size = self.index_size_bytes

        stats = {
            "pages_crawled": self.index.doc_count if self.index else 0,
            "unique_terms": len(self.index.index) if self.index else 0,
            "index_size_bytes": index_size,
            "crawl_duration_seconds": round(self.crawl_duration, 2),
        }
        self._send_json(stats)

    def _handle_crawl_start(self):
        """Handle /crawl - start a new crawl job."""
        if self.crawl_manager is None:
            self._send_json({"error": "Crawl manager not available"}, 500)
            return

        job_id = self.crawl_manager.create_job(
            self.seeds, self.depth, self.limit
        )

        # Run crawl in background thread
        job = self.crawl_manager.get_job(job_id)
        if job:
            job.status = "running"
            job.start_time = __import__("datetime").datetime.now()

            def run_crawl():
                try:
                    # Re-initialize crawler with same settings
                    from crawler import CrawlManager
                    from reporter import CrawlReporter
                    reporter = CrawlReporter()
                    cm = CrawlManager(
                        seeds=self.seeds,
                        depth=self.depth,
                        limit=self.limit,
                        workers=self.workers,
                        timeout=self.timeout,
                        index=self.index,
                        reporter=reporter,
                    )
                    new_index = cm.crawl()
                    # Update shared index
                    self.index.documents.update(new_index.documents)
                    self.index.index.update(new_index.index)
                    self.index.doc_count = len(self.index.documents)
                    self.index.term_count = len(self.index.index)
                    self.index.doc_lengths.update(new_index.doc_lengths)
                    self.crawl_duration = (time.time() - self.crawl_manager._start_time) if self.crawl_manager._start_time else 0
                    job.status = "completed"
                    job.pages_crawled = cm.pages_crawled
                except Exception as e:
                    job.status = "failed"
                    job.error = str(e)
                finally:
                    job.end_time = __import__("datetime").datetime.now()

            t = threading.Thread(target=run_crawl, daemon=True)
            t.start()

        self._send_json({"job_id": job_id, "status": "running"})

    def _handle_crawl_status(self, path: str):
        """Handle /crawl/{job_id}"""
        job_id = path.split("/")[-1]

        if self.crawl_manager is None:
            self._send_json({"error": "Crawl manager not available"}, 500)
            return

        job = self.crawl_manager.get_job(job_id)
        if job is None:
            self._send_json({"error": f"Job not found: {job_id}"}, 404)
            return

        self._send_json({
            "job_id": job.job_id,
            "status": job.status,
            "pages_crawled": job.pages_crawled,
            "pages_failed": job.pages_failed,
            "pages_queued": job.pages_queued,
            "current_url": job.current_url,
            "error": job.error,
        })

    def _serve_search_page(self):
        """Serve the static search.html page."""
        # Check multiple locations
        for html_path in [
            os.path.join(os.getcwd(), "search.html"),
            "/tmp/search.html",
        ]:
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    html = f.read()
                self._send_html(html)
                return
        # Serve embedded fallback
        html = generate_search_html()
        self._send_html(html)


def generate_search_html() -> str:
    """Generate the search.html interface."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Search Engine</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
    .container { max-width: 800px; margin: 0 auto; padding: 20px; }
    header { text-align: center; padding: 40px 0 20px; }
    header h1 { font-size: 2.5em; color: #1a0dab; margin-bottom: 10px; }
    .search-box { display: flex; gap: 10px; margin-bottom: 30px; }
    .search-box input[type="text"] { flex: 1; padding: 12px 20px; font-size: 16px; border: 2px solid #ddd; border-radius: 24px; outline: none; transition: border-color 0.3s; }
    .search-box input[type="text"]:focus { border-color: #1a0dab; }
    .search-box button { padding: 12px 24px; font-size: 16px; background: #1a0dab; color: white; border: none; border-radius: 24px; cursor: pointer; transition: background 0.3s; }
    .search-box button:hover { background: #150a8c; }
    .results-header { margin-bottom: 15px; color: #666; font-size: 14px; }
    .result-item { background: white; padding: 15px 20px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .result-title { font-size: 18px; margin-bottom: 5px; }
    .result-title a { color: #1a0dab; text-decoration: none; }
    .result-title a:hover { text-decoration: underline; }
    .result-url { color: #006621; font-size: 13px; margin-bottom: 6px; word-break: break-all; }
    .result-score { color: #999; font-size: 12px; margin-bottom: 6px; }
    .result-snippet { font-size: 14px; color: #555; line-height: 1.5; }
    .result-snippet b { color: #000; font-weight: 700; }
    .stats-bar { display: flex; gap: 20px; margin-bottom: 20px; font-size: 13px; color: #666; }
    .stats-bar span { background: #e8e8e8; padding: 5px 10px; border-radius: 12px; }
    .error { color: #d32f2f; text-align: center; padding: 20px; }
    .loading { text-align: center; padding: 40px; color: #999; }
    .no-results { text-align: center; padding: 40px; color: #999; }
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>Web Search</h1>
    </header>
    <div class="search-box">
        <input type="text" id="queryInput" placeholder="Enter search query..." autofocus>
        <button onclick="search()">Search</button>
    </div>
    <div class="stats-bar" id="statsBar"></div>
    <div id="resultsHeader" class="results-header"></div>
    <div id="results"></div>
</div>

<script>
const API_BASE = '';

function loadStats() {
    fetch(API_BASE + '/stats')
        .then(r => r.json())
        .then(data => {
            document.getElementById('statsBar').innerHTML = `
                <span>Pages: ${data.pages_crawled}</span>
                <span>Terms: ${data.unique_terms}</span>
                <span>Duration: ${data.crawl_duration_seconds}s</span>
            `;
        })
        .catch(() => {});
}

function search() {
    const query = document.getElementById('queryInput').value.trim();
    if (!query) return;

    document.getElementById('results').innerHTML = '<div class="loading">Searching...</div>';
    document.getElementById('resultsHeader').textContent = '';

    fetch(API_BASE + '/search?q=' + encodeURIComponent(query) + '&limit=30')
        .then(r => r.json())
        .then(data => {
            const resultsDiv = document.getElementById('results');
            document.getElementById('resultsHeader').textContent =
                `Found ${data.total} result(s) for "${data.query}"`;

            if (!data.results || data.results.length === 0) {
                resultsDiv.innerHTML = '<div class="no-results">No results found.</div>';
                return;
            }

            let html = '';
            data.results.forEach(r => {
                html += `
                <div class="result-item">
                    <div class="result-title"><a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a></div>
                    <div class="result-url">${escapeHtml(r.url)}</div>
                    <div class="result-score">Score: ${r.score}</div>
                    <div class="result-snippet">${r.snippet}</div>
                </div>`;
            });
            resultsDiv.innerHTML = html;
        })
        .catch(err => {
            document.getElementById('results').innerHTML =
                '<div class="error">Error: ' + err.message + '</div>';
        });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Search on Enter key
document.getElementById('queryInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') search();
});

// Load stats on page load
loadStats();
</script>
</body>
</html>"""


class SearchAPIServer:
    """Manages the HTTP search API server."""

    def __init__(
        self,
        index: InvertedIndex,
        crawl_manager=None,
        seeds: list = None,
        depth: int = 2,
        limit: int = 100,
        workers: int = 5,
        timeout: float = 10.0,
        crawl_duration: float = 0.0,
    ):
        self.index = index
        self.crawl_manager = crawl_manager
        self.seeds = seeds or []
        self.depth = depth
        self.limit = limit
        self.workers = workers
        self.timeout = timeout
        self.crawl_duration = crawl_duration

    def start(self, port: int = 8080):
        """Start the HTTP server on the given port."""
        # Configure the handler class
        SearchAPIHandler.index = self.index
        SearchAPIHandler.crawl_manager = self.crawl_manager
        SearchAPIHandler.seeds = self.seeds
        SearchAPIHandler.depth = self.depth
        SearchAPIHandler.limit = self.limit
        SearchAPIHandler.workers = self.workers
        SearchAPIHandler.timeout = self.timeout
        SearchAPIHandler.crawl_duration = self.crawl_duration

        server = HTTPServer(("0.0.0.0", port), SearchAPIHandler)
        print(f"\nSearch API server running at http://localhost:{port}")
        print(f"  Search:  http://localhost:{port}/search?q=your+query")
        print(f"  Stats:   http://localhost:{port}/stats")
        print(f"  Web UI:  http://localhost:{port}/")
        print(f"\nPress Ctrl+C to stop the server.")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            server.shutdown()
