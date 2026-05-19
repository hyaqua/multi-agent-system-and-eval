"""REST API server implemented with http.server."""

import http.server
import json
import threading
import urllib.parse
import os
import sys
import time

from search_engine import SearchEngine
from crawler import Crawler
from crawl_stats import CrawlStats


# Global state
search_engine = SearchEngine()
global_stats = {
    'pages_crawled': 0,
    'unique_terms': 0,
    'index_size_bytes': 0,
    'crawl_duration_seconds': 0,
    'start_time': None,
}
crawl_jobs = {}
crawl_jobs_lock = threading.Lock()
job_counter = 0

# Configuration (set by main)
server_config = {
    'port': 8080,
    'seeds_file': None,
    'seed_urls': [],
    'max_depth': 2,
    'max_pages': 100,
    'num_workers': 5,
    'timeout': 10,
    'index_file': 'index.json',
}


def update_global_stats(index_filepath=None):
    """Update global stats from the search engine."""
    global global_stats
    stats = search_engine.get_stats(index_filepath)
    global_stats.update(stats)


def run_crawl_job(job_id, seed_urls, max_depth, max_pages, num_workers, timeout, index_file):
    """Run a crawl job in a separate thread."""
    global crawl_jobs, search_engine

    with crawl_jobs_lock:
        crawl_jobs[job_id]['status'] = 'running'

    stats = CrawlStats()
    crawler = Crawler(
        seed_urls=seed_urls,
        max_depth=max_depth,
        max_pages=max_pages,
        num_workers=num_workers,
        timeout=timeout,
        stats=stats
    )

    try:
        # Update job status periodically
        def update_job_status():
            while stats.status == 'running':
                with crawl_jobs_lock:
                    if job_id in crawl_jobs:
                        snap = stats.snapshot()
                        crawl_jobs[job_id].update({
                            'pages_crawled': snap['pages_crawled'],
                            'total_queued': snap['pages_queued'],
                            'pages_failed': snap['pages_failed'],
                            'current_url': snap['current_url'],
                            'elapsed': snap['elapsed_seconds']
                        })
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=update_job_status, daemon=True)
        monitor_thread.start()

        # Run crawl
        documents = crawler.crawl()

        # Build new index
        new_indexer = search_engine.indexer.__class__()
        new_indexer.add_documents_batch(documents)
        new_indexer.build_index()

        # Save index
        new_indexer.save_to_file(index_file)

        # Atomically replace search engine index
        search_engine.indexer = new_indexer

        # Update global stats
        update_global_stats(index_file)
        global_stats['crawl_duration_seconds'] = stats.snapshot()['elapsed_seconds']

        # Get linked domains
        linked = crawler.get_linked_domains()

        with crawl_jobs_lock:
            if job_id in crawl_jobs:
                crawl_jobs[job_id]['status'] = 'completed'
                crawl_jobs[job_id]['pages_crawled'] = len(documents)
                crawl_jobs[job_id]['total_queued'] = 0

    except Exception as e:
        print(f"ERROR in crawl job {job_id}: {e}", file=sys.stderr)
        with crawl_jobs_lock:
            if job_id in crawl_jobs:
                crawl_jobs[job_id]['status'] = 'failed'
                crawl_jobs[job_id]['error'] = str(e)


class SearchServerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the search API."""

    def log_message(self, format, *args):
        """Override to provide cleaner logging."""
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_html(self, html, status=200):
        """Send an HTML response."""
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = urllib.parse.parse_qs(parsed.query)

        # Route: GET / or /index.html -> serve search.html
        if path == '' or path == '/index.html':
            self._serve_search_page()
            return

        # Route: GET /search
        if path == '/search':
            query = params.get('q', [''])[0]
            limit_str = params.get('limit', ['10'])[0]
            try:
                limit = int(limit_str)
                limit = max(1, min(100, limit))
            except ValueError:
                limit = 10

            if not query:
                self._send_json([])
                return

            results = search_engine.search(query, limit)
            self._send_json(results)
            return

        # Route: GET /stats
        if path == '/stats':
            # Try to get index file size
            index_file = server_config.get('index_file', 'index.json')
            try:
                if os.path.exists(index_file):
                    global_stats['index_size_bytes'] = os.path.getsize(index_file)
            except OSError:
                pass

            # Get stats from search engine
            engine_stats = search_engine.get_stats(index_file)
            stats_response = {
                'pages_crawled': engine_stats.get('pages_crawled', 0),
                'unique_terms': engine_stats.get('unique_terms', 0),
                'index_size_bytes': global_stats.get('index_size_bytes', 0),
                'crawl_duration_seconds': global_stats.get('crawl_duration_seconds', 0),
            }
            self._send_json(stats_response)
            return

        # Route: GET /crawl
        if path == '/crawl':
            global job_counter, crawl_jobs

            seed_urls = server_config.get('seed_urls', [])
            if not seed_urls:
                self._send_json({'error': 'No seed URLs configured. Start with --seeds.'}, 400)
                return

            with crawl_jobs_lock:
                job_counter += 1
                job_id = job_counter
                crawl_jobs[job_id] = {
                    'status': 'starting',
                    'pages_crawled': 0,
                    'total_queued': 0,
                    'pages_failed': 0,
                    'current_url': '',
                    'elapsed': 0,
                }

            # Start crawl in a new thread
            t = threading.Thread(
                target=run_crawl_job,
                args=(job_id, seed_urls,
                      server_config['max_depth'],
                      server_config['max_pages'],
                      server_config['num_workers'],
                      server_config['timeout'],
                      server_config.get('index_file', 'index.json')),
                daemon=True
            )
            t.start()

            self._send_json({'job_id': job_id})
            return

        # Route: GET /crawl/{job_id}
        if path.startswith('/crawl/'):
            try:
                job_id = int(path.split('/')[-1])
            except ValueError:
                self._send_json({'error': 'Invalid job ID'}, 400)
                return

            with crawl_jobs_lock:
                if job_id not in crawl_jobs:
                    self._send_json({'error': 'Job not found'}, 404)
                    return
                job_data = dict(crawl_jobs[job_id])

            self._send_json(job_data)
            return

        # 404
        self._send_json({'error': 'Not found'}, 404)

    def _serve_search_page(self):
        """Serve the search.html page."""
        html_path = 'search.html'
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
            self._send_html(html)
        else:
            # Generate on the fly
            from html_generator import generate_search_html
            generate_search_html('search.html', server_config['port'])
            with open('search.html', 'r', encoding='utf-8') as f:
                html = f.read()
            self._send_html(html)


def run_server(port=8080):
    """Start the HTTP server."""
    server_config['port'] = port
    server_address = ('', port)

    httpd = http.server.HTTPServer(server_address, SearchServerHandler)
    print(f"\n{'='*60}")
    print(f"  Search API Server running on http://localhost:{port}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Endpoints:")
    print(f"    GET /search?q=query&limit=N  - Search the index")
    print(f"    GET /stats                    - Index statistics")
    print(f"    GET /crawl                    - Start a new crawl")
    print(f"    GET /crawl/{{job_id}}           - Get crawl job status")
    print(f"{'='*60}\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.shutdown()
