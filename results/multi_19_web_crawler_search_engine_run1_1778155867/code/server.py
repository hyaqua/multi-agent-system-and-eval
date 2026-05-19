"""HTTP server providing REST API endpoints for the search engine."""

import json
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from indexer import Indexer
from searcher import Searcher
from crawl_manager import CrawlManager


class SearchRequestHandler(BaseHTTPRequestHandler):
    """Custom request handler for the search engine REST API."""

    # Class-level references set by the server setup
    indexer: Indexer = None  # type: ignore
    searcher: Searcher = None  # type: ignore
    crawl_manager: CrawlManager = None  # type: ignore
    seeds: list[str] = []
    index_path: str = ''
    crawl_start_time: float = 0.0
    crawl_duration: float = 0.0
    index_file_size: int = 0

    def log_message(self, format, *args):
        """Suppress standard logging or redirect."""
        pass

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, filepath: str, content_type: str):
        """Serve a static file."""
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'File not found')

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = urllib.parse.parse_qs(parsed.query)

        if path == '/search':
            self._handle_search(params)
        elif path == '/stats':
            self._handle_stats()
        elif path == '/crawl':
            self._handle_crawl()
        elif path.startswith('/crawl/'):
            job_id = path[len('/crawl/'):]
            self._handle_crawl_job(job_id)
        elif path == '/' or path == '/search.html':
            self._send_static('search.html', 'text/html; charset=utf-8')
        else:
            self._send_json({'error': 'Not found'}, status=404)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _handle_search(self, params: dict):
        """Handle /search?q=...&limit=N."""
        query = params.get('q', [''])[0]
        limit_str = params.get('limit', ['10'])[0]

        try:
            limit = int(limit_str)
            limit = max(1, min(limit, 100))
        except (ValueError, TypeError):
            limit = 10

        if not query or not self.searcher:
            self._send_json({'results': [], 'query': query})
            return

        results = self.searcher.search(query, limit=limit)
        self._send_json({
            'results': results,
            'query': query,
            'total_results': len(results),
        })

    def _handle_stats(self):
        """Handle /stats."""
        stats = self.indexer.get_stats() if self.indexer else {
            'total_docs': 0,
            'unique_terms': 0,
        }

        index_size = 0
        if self.index_path and os.path.exists(self.index_path):
            index_size = os.path.getsize(self.index_path)

        self._send_json({
            'total_pages_crawled': stats.get('total_docs', 0),
            'total_unique_terms': stats.get('unique_terms', 0),
            'index_size_bytes': index_size,
            'crawl_duration_seconds': round(self.crawl_duration, 2),
        })

    def _handle_crawl(self):
        """Handle /crawl - start a new crawl asynchronously."""
        if not self.seeds:
            self._send_json({'error': 'No seeds configured'}, status=400)
            return

        job = self.crawl_manager.start_crawl_async(self.seeds)
        self._send_json({
            'job_id': job.job_id,
            'status': job.status,
        })

    def _handle_crawl_job(self, job_id: str):
        """Handle /crawl/{job_id} - get job status."""
        job = self.crawl_manager.get_job(job_id)
        if job is None:
            self._send_json({'error': 'Job not found'}, status=404)
            return

        self._send_json({
            'job_id': job.job_id,
            'status': job.status,
            'pages_crawled': job.pages_crawled,
            'pages_failed': job.pages_failed,
        })


def create_server(
    port: int,
    indexer: Indexer,
    searcher: Searcher,
    crawl_manager: CrawlManager,
    seeds: list[str],
    index_path: str = '',
    crawl_duration: float = 0.0,
) -> HTTPServer:
    """Create and configure the HTTP server."""
    # Set class-level references
    SearchRequestHandler.indexer = indexer
    SearchRequestHandler.searcher = searcher
    SearchRequestHandler.crawl_manager = crawl_manager
    SearchRequestHandler.seeds = seeds
    SearchRequestHandler.index_path = index_path
    SearchRequestHandler.crawl_duration = crawl_duration

    server = HTTPServer(('0.0.0.0', port), SearchRequestHandler)
    return server


def run_server(
    port: int,
    indexer: Indexer,
    searcher: Searcher,
    crawl_manager: CrawlManager,
    seeds: list[str],
    index_path: str = '',
    crawl_duration: float = 0.0,
):
    """Start the HTTP server (blocking)."""
    server = create_server(
        port, indexer, searcher, crawl_manager, seeds, index_path, crawl_duration
    )
    print(f'\nServer running at http://localhost:{port}/search.html')
    print('API endpoints:')
    print('  GET /search?q=query&limit=10')
    print('  GET /stats')
    print('  GET /crawl')
    print('  GET /crawl/{job_id}')
    print('\nPress Ctrl+C to stop.\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        server.shutdown()
