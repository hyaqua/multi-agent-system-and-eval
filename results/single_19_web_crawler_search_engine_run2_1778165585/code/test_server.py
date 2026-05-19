"""Test server that provides sample pages for the crawler to index locally."""

import http.server
import socketserver
import threading
import os
import json

# HTML pages for testing
PAGES = {
    "/": """<!DOCTYPE html>
<html><head><title>Test Home</title></head>
<body>
<h1>Welcome to the Test Site</h1>
<p>This is a test page about web crawling and search engines. Web crawlers are automated programs that browse the internet.</p>
<p>Search engines use crawlers to build their indexes. Python is a great language for building search engines.</p>
<ul>
<li><a href="/page1">Python Programming</a></li>
<li><a href="/page2">Web Crawling Techniques</a></li>
<li><a href="/page3">Search Engine Basics</a></li>
</ul>
</body></html>""",

    "/page1": """<!DOCTYPE html>
<html><head><title>Python Programming</title></head>
<body>
<h1>Python Programming Guide</h1>
<p>Python is a versatile programming language used for web development, data science, artificial intelligence, and automation.</p>
<p>The Python standard library includes many useful modules like urllib, html.parser, and http.server for building web applications.</p>
<p>Python's async capabilities enable efficient web crawling and concurrent processing of multiple URLs.</p>
<p>Popular Python web frameworks include Django, Flask, and FastAPI for building REST APIs.</p>
<a href="/">Back to Home</a> | <a href="/page2">Web Crawling</a>
</body></html>""",

    "/page2": """<!DOCTYPE html>
<html><head><title>Web Crawling Techniques</title></head>
<body>
<h1>Web Crawling Techniques</h1>
<p>A web crawler systematically browses the World Wide Web to discover and index web pages. Crawlers start from seed URLs and follow links.</p>
<p>Important crawling considerations include respecting robots.txt files, implementing rate limiting, and handling various content types.</p>
<p>Distributed crawling systems use thread pools and work queues to achieve high throughput while respecting per-domain limits.</p>
<p>TF-IDF is a common ranking algorithm used by search engines to score document relevance for queries.</p>
<a href="/">Back to Home</a> | <a href="/page3">Search Engines</a>
</body></html>""",

    "/page3": """<!DOCTYPE html>
<html><head><title>Search Engine Basics</title></head>
<body>
<h1>Search Engine Fundamentals</h1>
<p>Search engines process user queries and return relevant results from their indexed corpus of web pages.</p>
<p>An inverted index maps terms to documents, enabling fast full-text search across millions of pages.</p>
<p>TF-IDF (Term Frequency-Inverse Document Frequency) measures how important a term is to a document within a collection.</p>
<p>Modern search engines use hundreds of ranking signals including page quality, freshness, and user engagement metrics.</p>
<a href="/">Back to Home</a> | <a href="/page1">Python</a>
</body></html>""",

    "/robots.txt": """User-agent: *
Disallow: /private
Crawl-delay: 0.5
""",

    "/private": """<!DOCTYPE html>
<html><head><title>Private Page</title></head>
<body><h1>Secret</h1><p>This should not be crawled.</p></body></html>""",

    "/not-html": """{"message": "This is JSON, not HTML"}""",
}


class TestHandler(http.server.BaseHTTPRequestHandler):
    """Handler that serves test pages with proper content types."""

    def do_GET(self):
        path = self.path.split("?")[0]  # Strip query params

        if path == "/not-html":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(PAGES["/not-html"].encode())
        elif path in PAGES:
            content = PAGES[path]
            self.send_response(200)
            if path == "/robots.txt":
                self.send_header("Content-Type", "text/plain")
            else:
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode())
        elif path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/page1")
            self.end_headers()
        elif path == "/error":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
        elif path == "/timeout":
            import time
            time.sleep(30)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        pass  # Suppress logs


def start_test_server(port: int = 9876) -> socketserver.TCPServer:
    """Start a test HTTP server and return the server object."""
    server = socketserver.TCPServer(("127.0.0.1", port), TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    server = start_test_server(9876)
    print(f"Test server running at http://127.0.0.1:9876")
    print("Press Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()
