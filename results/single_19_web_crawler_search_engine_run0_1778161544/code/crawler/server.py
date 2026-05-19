"""
REST API server for the search engine.
Serves JSON endpoints and generates a static HTML interface.
"""

import json
import time
import threading
import uuid
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from crawler.indexer import Indexer
from crawler.crawler import CrawlJob

import logging
logger = logging.getLogger(__name__)


class SearchAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the search API."""
    
    # Class-level shared state
    indexer = None
    crawl_start_time = None
    crawl_duration = 0.0
    jobs = {}  # job_id -> CrawlJob
    jobs_lock = threading.Lock()
    seed_file = None
    crawl_depth = 2
    crawl_limit = 100
    crawl_workers = 5
    crawl_timeout = 10
    index_file_size = 0
    html_path = '/tmp/search.html'
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(f"API: {format % args}")
    
    def _send_json(self, data, status=200):
        """Send JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
    
    def _send_html(self, html, status=200):
        """Send HTML response."""
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def _send_error_json(self, message, status=400):
        """Send error as JSON."""
        self._send_json({'error': message}, status=status)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)
        
        try:
            if path == '' or path == '/':
                self._serve_html()
            elif path == '/search':
                self._handle_search(params)
            elif path == '/stats':
                self._handle_stats()
            elif path == '/crawl':
                self._handle_crawl()
            elif path.startswith('/crawl/'):
                job_id = path.split('/crawl/', 1)[1]
                self._handle_crawl_status(job_id)
            else:
                self._send_error_json('Not found', status=404)
        except Exception as e:
            logger.error(f"Error handling request {self.path}: {e}")
            self._send_error_json(str(e), status=500)
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _handle_search(self, params):
        """Handle /search?q=query&limit=N."""
        query = params.get('q', [None])[0]
        if not query:
            self._send_error_json('Missing query parameter "q"', status=400)
            return
        
        limit_str = params.get('limit', [None])[0]
        limit = None
        if limit_str:
            try:
                limit = int(limit_str)
            except ValueError:
                self._send_error_json('Invalid limit parameter', status=400)
                return
        
        if self.indexer is None:
            self._send_json([])
            return
        
        results = self.indexer.search(query, limit=limit)
        self._send_json(results)
    
    def _handle_stats(self):
        """Handle /stats."""
        if self.indexer is None:
            self._send_json({
                'total_pages': 0,
                'unique_terms': 0,
                'index_size_bytes': 0,
                'crawl_duration': self.crawl_duration
            })
            return
        
        stats = self.indexer.get_stats()
        # Get actual index file size if available
        index_size = self.index_file_size
        self._send_json({
            'total_pages': stats['total_pages'],
            'unique_terms': stats['unique_terms'],
            'index_size_bytes': index_size,
            'crawl_duration': round(self.crawl_duration, 2)
        })
    
    def _handle_crawl(self):
        """Handle /crawl - trigger a new crawl."""
        if not self.seed_file:
            self._send_error_json('No seed file configured', status=500)
            return
        
        # Read seed URLs
        try:
            with open(self.seed_file, 'r') as f:
                seed_urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self._send_error_json(f'Failed to read seed file: {e}', status=500)
            return
        
        if not seed_urls:
            self._send_error_json('Seed file is empty', status=400)
            return
        
        job_id = str(uuid.uuid4())[:8]
        job = CrawlJob(
            job_id=job_id,
            seed_urls=seed_urls,
            depth=self.crawl_depth,
            max_pages=self.crawl_limit,
            num_workers=self.crawl_workers,
            timeout=self.crawl_timeout
        )
        
        with self.jobs_lock:
            self.jobs[job_id] = job
        
        # Start crawl in background thread
        def run_job():
            job.run()
            # Update shared indexer if crawl succeeded
            if job.status == 'completed' and job.indexer:
                # Atomically replace indexer
                SearchAPIHandler.indexer = job.indexer
                SearchAPIHandler.crawl_duration = time.time() - job.start_time
        
        job.thread = threading.Thread(target=run_job, daemon=True)
        job.thread.start()
        
        self._send_json({
            'job_id': job_id,
            'status': 'started',
            'message': 'Crawl job started'
        })
    
    def _handle_crawl_status(self, job_id):
        """Handle /crawl/{job_id}."""
        with self.jobs_lock:
            job = self.jobs.get(job_id)
        
        if job is None:
            self._send_error_json(f'Job {job_id} not found', status=404)
            return
        
        self._send_json(job.get_progress())
    
    def _serve_html(self):
        """Serve the generated search.html page."""
        html_path = SearchAPIHandler.html_path
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
            self._send_html(html)
        except FileNotFoundError:
            # Serve a simple fallback page
            self._send_html("<html><body><h1>Search Engine</h1><p>No search.html found. Use --generate-html to create one.</p></body></html>")
        except Exception as e:
            self._send_error_json(f'Could not serve HTML: {e}', status=500)


def generate_search_html(output_path='search.html'):
    """Generate a static HTML file with search interface."""
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Search Engine</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}
.header {
    text-align: center;
    padding: 30px 0 20px;
}
.header h1 { font-size: 2.5em; color: #1a73e8; margin-bottom: 5px; }
.header p { color: #666; }
.search-box {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}
.search-box input[type="text"] {
    flex: 1;
    padding: 14px 20px;
    font-size: 1.1em;
    border: 2px solid #ddd;
    border-radius: 24px;
    outline: none;
    transition: border-color 0.2s;
}
.search-box input[type="text"]:focus {
    border-color: #1a73e8;
}
.search-box button {
    padding: 14px 30px;
    font-size: 1.1em;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 24px;
    cursor: pointer;
    transition: background 0.2s;
}
.search-box button:hover { background: #1557b0; }
.options {
    display: flex;
    gap: 15px;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
}
.options label { font-size: 0.9em; color: #555; }
.options input[type="number"] {
    width: 70px;
    padding: 6px;
    border: 1px solid #ccc;
    border-radius: 4px;
}
.stats-bar {
    background: white;
    padding: 12px 20px;
    border-radius: 12px;
    margin-bottom: 20px;
    display: flex;
    gap: 30px;
    flex-wrap: wrap;
    font-size: 0.9em;
    color: #666;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.stats-bar span { white-space: nowrap; }
.results-info {
    color: #666;
    font-size: 0.9em;
    margin-bottom: 15px;
}
.result-item {
    background: white;
    padding: 16px 20px;
    border-radius: 8px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    transition: box-shadow 0.2s;
}
.result-item:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.result-title {
    font-size: 1.15em;
    margin-bottom: 3px;
}
.result-title a {
    color: #1a0dab;
    text-decoration: none;
}
.result-title a:hover { text-decoration: underline; }
.result-url {
    color: #006621;
    font-size: 0.85em;
    margin-bottom: 5px;
    word-break: break-all;
}
.result-score {
    color: #999;
    font-size: 0.8em;
    margin-bottom: 5px;
}
.result-snippet {
    font-size: 0.9em;
    color: #545454;
    line-height: 1.5;
}
.result-snippet b { color: #000; }
.loading {
    text-align: center;
    padding: 40px;
    color: #999;
}
.no-results {
    text-align: center;
    padding: 40px;
    color: #999;
}
.error {
    background: #fce8e6;
    color: #c5221f;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 15px;
}
</style>
</head>
<body>
<div class="header">
    <h1>🔍 Search Engine</h1>
    <p>Full-text search over crawled web pages</p>
</div>
<div class="search-box">
    <input type="text" id="query" placeholder="Enter your search query..." autofocus>
    <button onclick="doSearch()">Search</button>
</div>
<div class="options">
    <label>Results: <input type="number" id="limit" value="10" min="1" max="100"></label>
</div>
<div class="stats-bar" id="stats">
    <span>📄 Pages: <strong id="stat-pages">-</strong></span>
    <span>📝 Terms: <strong id="stat-terms">-</strong></span>
    <span>💾 Size: <strong id="stat-size">-</strong></span>
    <span>⏱ Duration: <strong id="stat-duration">-</strong></span>
</div>
<div id="results-info" class="results-info"></div>
<div id="results"></div>

<script>
const API_BASE = '';

async function loadStats() {
    try {
        const resp = await fetch(API_BASE + '/stats');
        const data = await resp.json();
        document.getElementById('stat-pages').textContent = data.total_pages || 0;
        document.getElementById('stat-terms').textContent = data.unique_terms || 0;
        const size = data.index_size_bytes || 0;
        document.getElementById('stat-size').textContent = 
            size > 1024*1024 ? (size/(1024*1024)).toFixed(1) + ' MB' :
            size > 1024 ? (size/1024).toFixed(1) + ' KB' : size + ' B';
        document.getElementById('stat-duration').textContent = 
            (data.crawl_duration || 0).toFixed(1) + 's';
    } catch(e) {
        console.error('Failed to load stats:', e);
    }
}

function highlightTerms(text, query) {
    if (!query || !text) return escapeHtml(text);
    const terms = query.split(/\\s+/).filter(t => t.length > 0);
    let result = escapeHtml(text);
    terms.forEach(term => {
        const escaped = escapeRegex(term);
        const regex = new RegExp('(' + escaped + ')', 'gi');
        result = result.replace(regex, '<b>$1</b>');
    });
    return result;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
}

async function doSearch() {
    const query = document.getElementById('query').value.trim();
    const limit = document.getElementById('limit').value || 10;
    const resultsDiv = document.getElementById('results');
    const infoDiv = document.getElementById('results-info');
    
    if (!query) {
        resultsDiv.innerHTML = '<div class="no-results">Please enter a search query.</div>';
        infoDiv.innerHTML = '';
        return;
    }
    
    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
    infoDiv.innerHTML = '';
    
    try {
        const url = API_BASE + '/search?q=' + encodeURIComponent(query) + '&limit=' + limit;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        
        if (data.error) {
            resultsDiv.innerHTML = '<div class="error">' + escapeHtml(data.error) + '</div>';
            return;
        }
        
        if (data.length === 0) {
            resultsDiv.innerHTML = '<div class="no-results">No results found for "' + escapeHtml(query) + '".</div>';
            infoDiv.innerHTML = '';
            return;
        }
        
        infoDiv.innerHTML = 'Found <strong>' + data.length + '</strong> result(s)';
        
        let html = '';
        data.forEach(item => {
            html += '<div class="result-item">';
            html += '<div class="result-title"><a href="' + escapeHtml(item.url) + '" target="_blank">' + escapeHtml(item.title) + '</a></div>';
            html += '<div class="result-url">' + escapeHtml(item.url) + '</div>';
            html += '<div class="result-score">Score: ' + item.score + '</div>';
            html += '<div class="result-snippet">' + highlightTerms(item.snippet, query) + '</div>';
            html += '</div>';
        });
        resultsDiv.innerHTML = html;
    } catch(e) {
        resultsDiv.innerHTML = '<div class="error">Search failed: ' + escapeHtml(e.message) + '</div>';
        console.error('Search error:', e);
    }
}

// Search on Enter key
document.getElementById('query').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') doSearch();
});

// Load stats on page load
loadStats();
</script>
</body>
</html>'''
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Search interface written to {output_path}")
    except PermissionError:
        # Try /tmp as fallback
        import tempfile
        fallback = '/tmp/search.html'
        with open(fallback, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Search interface written to {fallback} (fallback due to permissions)")
        output_path = fallback
    
    return output_path


def run_server(indexer, port=8080, seed_file=None, crawl_depth=2, crawl_limit=100,
               crawl_workers=5, crawl_timeout=10, crawl_duration=0.0, index_file_size=0,
               html_path='/tmp/search.html'):
    """Start the REST API server."""
    SearchAPIHandler.indexer = indexer
    SearchAPIHandler.seed_file = seed_file
    SearchAPIHandler.crawl_depth = crawl_depth
    SearchAPIHandler.crawl_limit = crawl_limit
    SearchAPIHandler.crawl_workers = crawl_workers
    SearchAPIHandler.crawl_timeout = crawl_timeout
    SearchAPIHandler.crawl_duration = crawl_duration
    SearchAPIHandler.index_file_size = index_file_size
    SearchAPIHandler.html_path = html_path
    
    server = HTTPServer(('0.0.0.0', port), SearchAPIHandler)
    print(f"REST API server started on http://0.0.0.0:{port}")
    print(f"Endpoints:")
    print(f"  GET /search?q=query&limit=N")
    print(f"  GET /stats")
    print(f"  GET /crawl")
    print(f"  GET /crawl/{{job_id}}")
    print(f"Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()
