"""REST API server for the search engine."""

import json
import os
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from indexer import Indexer
from crawler import Crawler


class CrawlJob:
    """Tracks an asynchronous crawl job."""

    def __init__(self, job_id: str, crawler: Crawler) -> None:
        self.job_id = job_id
        self.crawler = crawler
        self.status = 'pending'  # pending, running, completed, failed
        self.pages_crawled = 0
        self.pages_failed = 0
        self.start_time = time.time()
        self._thread: Optional[threading.Thread] = None
        self._result_indexer: Optional[Indexer] = None
        self.error: Optional[str] = None

    def start(self) -> None:
        """Begin the crawl in a background thread."""
        self.status = 'running'

        def _run():
            try:
                idx = self.crawler.run()
                self._result_indexer = idx
                self.status = 'completed'
            except Exception as e:
                self.error = str(e)
                self.status = 'failed'

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def get_progress(self) -> dict:
        """Return current job status."""
        if self.crawler:
            self.pages_crawled = self.crawler.pages_crawled
            self.pages_failed = self.crawler.pages_failed

        elapsed = time.time() - self.start_time
        return {
            'job_id': self.job_id,
            'status': self.status,
            'pages_crawled': self.pages_crawled,
            'pages_failed': self.pages_failed,
            'elapsed_sec': round(elapsed, 2),
            'error': self.error,
        }


class JobManager:
    """Manages crawl jobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, CrawlJob] = {}

    def create_job(self, crawler: Crawler) -> CrawlJob:
        """Create and register a new crawl job."""
        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(job_id, crawler)
        with self._lock:
            self._jobs[job_id] = job
        job.start()
        return job

    def get_job(self, job_id: str) -> Optional[CrawlJob]:
        with self._lock:
            return self._jobs.get(job_id)


class SearchHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the search API."""

    # Class-level references set by the server
    indexer: Indexer = None  # type: ignore
    job_manager: JobManager = None  # type: ignore
    seed_file: str = ''
    crawl_depth: int = 2
    crawl_limit: int = 100
    crawl_workers: int = 5

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(body.encode('utf-8'))

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({'error': message}, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = parse_qs(parsed.query)

        # Route: /search
        if path == '/search':
            self._handle_search(params)
        # Route: /stats
        elif path == '/stats':
            self._handle_stats()
        # Route: /crawl
        elif path == '/crawl':
            self._handle_crawl()
        # Route: /crawl/{job_id}
        elif path.startswith('/crawl/'):
            job_id = path.split('/crawl/', 1)[1].strip()
            if job_id:
                self._handle_crawl_status(job_id)
            else:
                self._send_error_json('Missing job_id', 400)
        # Route: /
        elif path == '/' or path == '':
            self._send_json({
                'name': 'Search Engine API',
                'endpoints': {
                    '/search?q=query&limit=N': 'Search the index',
                    '/stats': 'Index statistics',
                    '/crawl': 'Start a new crawl job',
                    '/crawl/{job_id}': 'Get crawl job status',
                }
            })
        else:
            self._send_error_json('Not found', 404)

    def _handle_search(self, params: dict) -> None:
        query = params.get('q', [''])[0].strip()
        if not query:
            self._send_error_json('Missing query parameter "q"', 400)
            return

        try:
            limit = int(params.get('limit', ['10'])[0])
        except ValueError:
            limit = 10
        limit = max(1, min(limit, 100))

        if SearchHandler.indexer is None or SearchHandler.indexer.doc_count == 0:
            self._send_json([], 200)
            return

        results = SearchHandler.indexer.search(query, limit=limit)
        self._send_json(results)

    def _handle_stats(self) -> None:
        if SearchHandler.indexer is None:
            self._send_json({
                'total_pages_crawled': 0,
                'total_unique_terms': 0,
                'index_size_bytes': 0,
                'crawl_duration_sec': 0,
            })
            return

        stats = SearchHandler.indexer.get_stats()
        self._send_json(stats)

    def _handle_crawl(self) -> None:
        if not SearchHandler.seed_file:
            self._send_error_json('No seed file configured', 500)
            return

        # Read seeds
        try:
            with open(SearchHandler.seed_file, 'r', encoding='utf-8') as f:
                seeds = [line.strip() for line in f if line.strip()
                         and not line.strip().startswith('#')]
        except FileNotFoundError:
            self._send_error_json(f'Seed file not found: {SearchHandler.seed_file}', 500)
            return

        if not seeds:
            self._send_error_json('Seed file is empty', 400)
            return

        # Create new indexer (crawl will replace current)
        new_indexer = Indexer()
        crawler = Crawler(
            seeds=seeds,
            depth=SearchHandler.crawl_depth,
            limit=SearchHandler.crawl_limit,
            workers=SearchHandler.crawl_workers,
            indexer=new_indexer,
        )

        job = SearchHandler.job_manager.create_job(crawler)

        # Schedule index replacement when job completes
        def _on_complete():
            # Wait for job to finish
            if job._thread:
                job._thread.join()
            if job.status == 'completed' and job._result_indexer is not None:
                SearchHandler.indexer = job._result_indexer
                # Persist if we have a path (reuse last save path or create one)
                # Not persisting automatically from API crawl

        threading.Thread(target=_on_complete, daemon=True).start()

        self._send_json({
            'job_id': job.job_id,
            'message': 'Crawl job started',
            'status': job.status,
        })

    def _handle_crawl_status(self, job_id: str) -> None:
        job = SearchHandler.job_manager.get_job(job_id)
        if job is None:
            self._send_error_json(f'Job not found: {job_id}', 404)
            return

        self._send_json(job.get_progress())


def generate_search_html(port: int = 8080) -> str:
    """Generate the search.html file content."""
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Search Engine</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
}}
.header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    padding: 40px 20px;
    text-align: center;
    border-bottom: 2px solid #0f3460;
}}
.header h1 {{
    font-size: 2.5rem;
    margin-bottom: 20px;
    background: linear-gradient(90deg, #e94560, #0f3460);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.search-container {{
    display: flex;
    max-width: 600px;
    margin: 0 auto;
    gap: 10px;
}}
#search-box {{
    flex: 1;
    padding: 14px 20px;
    font-size: 1.1rem;
    border: 2px solid #0f3460;
    border-radius: 30px;
    background: #1a1a2e;
    color: #e0e0e0;
    outline: none;
    transition: border-color 0.3s;
}}
#search-box:focus {{
    border-color: #e94560;
}}
#search-btn {{
    padding: 14px 28px;
    font-size: 1.1rem;
    border: none;
    border-radius: 30px;
    background: #e94560;
    color: white;
    cursor: pointer;
    transition: background 0.3s;
}}
#search-btn:hover {{
    background: #c73650;
}}
.results-container {{
    max-width: 800px;
    margin: 30px auto;
    padding: 0 20px;
}}
.result-item {{
    background: #1a1a2e;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    border: 1px solid #0f3460;
    transition: border-color 0.3s, transform 0.2s;
}}
.result-item:hover {{
    border-color: #e94560;
    transform: translateY(-2px);
}}
.result-title {{
    font-size: 1.2rem;
    margin-bottom: 6px;
}}
.result-title a {{
    color: #58a6ff;
    text-decoration: none;
}}
.result-title a:hover {{
    text-decoration: underline;
}}
.result-url {{
    font-size: 0.85rem;
    color: #8b949e;
    margin-bottom: 8px;
    word-break: break-all;
}}
.result-score {{
    font-size: 0.8rem;
    color: #e94560;
    margin-bottom: 8px;
    font-weight: 600;
}}
.result-snippet {{
    font-size: 0.95rem;
    line-height: 1.5;
    color: #c9d1d9;
}}
.result-snippet b {{
    color: #f0c674;
    background: rgba(240, 198, 116, 0.15);
    padding: 1px 3px;
    border-radius: 2px;
}}
.no-results {{
    text-align: center;
    padding: 40px;
    color: #8b949e;
    font-size: 1.1rem;
}}
.loading {{
    text-align: center;
    padding: 20px;
    color: #8b949e;
}}
.error {{
    text-align: center;
    padding: 20px;
    color: #e94560;
}}
.stats {{
    text-align: center;
    padding: 10px;
    color: #8b949e;
    font-size: 0.85rem;
}}
</style>
</head>
<body>
<div class="header">
    <h1>🔍 Search Engine</h1>
    <div class="search-container">
        <input type="text" id="search-box" placeholder="Enter your search query..."
               autofocus onkeydown="if(event.key==='Enter')doSearch()">
        <button id="search-btn" onclick="doSearch()">Search</button>
    </div>
</div>
<div class="results-container" id="results">
    <div class="no-results">Enter a query above to search the crawled index.</div>
</div>

<script>
const API_BASE = 'http://localhost:{port}';

async function doSearch() {{
    const query = document.getElementById('search-box').value.trim();
    if (!query) return;

    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';

    try {{
        const resp = await fetch(`${{API_BASE}}/search?q=${{encodeURIComponent(query)}}&limit=20`);
        if (!resp.ok) throw new Error('Search request failed');
        const data = await resp.json();

        if (!data || data.length === 0) {{
            resultsDiv.innerHTML = '<div class="no-results">No results found for "' +
                escapeHtml(query) + '".</div>';
            return;
        }}

        let html = '';
        for (const item of data) {{
            html += `
            <div class="result-item">
                <div class="result-title">
                    <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener">
                        ${{escapeHtml(item.title)}}
                    </a>
                </div>
                <div class="result-url">${{escapeHtml(item.url)}}</div>
                <div class="result-score">Score: ${{item.score.toFixed(4)}}</div>
                <div class="result-snippet">${{item.snippet}}</div>
            </div>`;
        }}
        resultsDiv.innerHTML = html;
    }} catch (err) {{
        resultsDiv.innerHTML = '<div class="error">Error: ' + escapeHtml(err.message) + '</div>';
    }}
}}

function escapeHtml(str) {{
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}}
</script>
</body>
</html>'''
    return html


def start_server(
    indexer: Indexer,
    seed_file: str,
    port: int = 8080,
    depth: int = 2,
    limit: int = 100,
    workers: int = 5,
) -> HTTPServer:
    """Configure and start the HTTP server (non-blocking). Returns the server instance."""
    SearchHandler.indexer = indexer
    SearchHandler.job_manager = JobManager()
    SearchHandler.seed_file = seed_file
    SearchHandler.crawl_depth = depth
    SearchHandler.crawl_limit = limit
    SearchHandler.crawl_workers = workers

    server = HTTPServer(('0.0.0.0', port), SearchHandler)
    return server
