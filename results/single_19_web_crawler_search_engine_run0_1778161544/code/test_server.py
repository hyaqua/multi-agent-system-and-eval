#!/usr/bin/env python3
"""
Simple HTTP test server that serves a mini website for crawler testing.
Run this in the background, then crawl http://localhost:9876
"""

import http.server
import sys
import urllib.parse

PAGES = {
    '/': '''<!DOCTYPE html>
<html><head><title>Test Home</title></head>
<body>
<h1>Welcome to the Test Site</h1>
<p>This is a test page about python programming and web crawling.</p>
<p>Search engines use inverted indexes and TF-IDF scoring to rank results.</p>
<nav>
<a href="/page1">Page 1: Python Basics</a><br>
<a href="/page2">Page 2: Web Crawling</a><br>
<a href="/page3">Page 3: Search Algorithms</a><br>
<a href="/about">About</a><br>
<a href="/deep/page4">Deep Page 4</a><br>
<a href="https://docs.python.org/3/">Python Docs (external)</a><br>
<a href="https://en.wikipedia.org/wiki/Web_crawler">Wikipedia: Web Crawler</a>
</nav>
</body></html>''',

    '/page1': '''<!DOCTYPE html>
<html><head><title>Python Basics</title></head>
<body>
<h1>Python Programming</h1>
<p>Python is a high-level programming language. It is used for web development,
data science, machine learning, and automation.</p>
<p>The standard library includes many useful modules like urllib and html.parser.</p>
<a href="/">Home</a> | <a href="/page2">Web Crawling</a>
</body></html>''',

    '/page2': '''<!DOCTYPE html>
<html><head><title>Web Crawling 101</title></head>
<body>
<h1>Understanding Web Crawlers</h1>
<p>A web crawler systematically browses the World Wide Web. It starts from seed URLs
and follows links to discover new pages.</p>
<p>Important aspects include respecting robots.txt, managing crawl delays, and
handling errors gracefully.</p>
<p>Crawlers use concurrent workers with thread pools for efficiency.</p>
<a href="/">Home</a> | <a href="/page1">Python</a> | <a href="/page3">Search</a>
</body></html>''',

    '/page3': '''<!DOCTYPE html>
<html><head><title>Search Algorithms</title></head>
<body>
<h1>Full-Text Search</h1>
<p>TF-IDF (Term Frequency-Inverse Document Frequency) is a numerical statistic
that reflects how important a word is to a document in a collection.</p>
<p>An inverted index maps terms to the documents that contain them.</p>
<p>Python is great for building search engines from scratch.</p>
<a href="/">Home</a> | <a href="/page2">Crawling</a> | <a href="/about">About</a>
</body></html>''',

    '/about': '''<!DOCTYPE html>
<html><head><title>About This Site</title></head>
<body>
<h1>About</h1>
<p>This is a simple test website for crawling experiments.</p>
<a href="/">Home</a> | <a href="/page3">Search Algorithms</a>
</body></html>''',

    '/deep/page4': '''<!DOCTYPE html>
<html><head><title>Deep Page</title></head>
<body>
<h1>Deeply Nested Page</h1>
<p>This page demonstrates depth-two crawling. It links to an even deeper page.</p>
<p>Python web crawlers need to track depth to avoid infinite crawling.</p>
<a href="/">Home</a> | <a href="/deep/page5">Even Deeper</a>
</body></html>''',

    '/deep/page5': '''<!DOCTYPE html>
<html><head><title>Deep Page 5</title></head>
<body>
<h1>Depth 2 Page</h1>
<p>This page is at depth 2 from the home page. Web crawlers with depth=1 would not reach this page.</p>
<a href="/">Home</a>
</body></html>''',

    '/robots.txt': '''User-agent: *
Disallow: /secret
Crawl-delay: 0.5

User-agent: BadBot
Disallow: /
''',

    '/secret': '''<!DOCTYPE html>
<html><head><title>Secret Page</title></head>
<body><h1>Secret</h1><p>You should not see this.</p></body></html>''',
}


class TestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path in PAGES:
            content = PAGES[path]
            self.send_response(200)
            if path.endswith('.txt'):
                self.send_header('Content-Type', 'text/plain')
            else:
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(content.encode()))
            self.end_headers()
            self.wfile.write(content.encode())
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        pass  # Quiet mode


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9876
    server = http.server.HTTPServer(('127.0.0.1', port), TestHandler)
    print(f"Test server running on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()
