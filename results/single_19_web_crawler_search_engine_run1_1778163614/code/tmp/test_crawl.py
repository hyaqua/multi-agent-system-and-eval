import sys
sys.path.insert(0, '/workspace')
from indexer import Indexer
from crawler import Crawler
import http.server, socketserver, threading, time

PAGES = {
    '/': '<!DOCTYPE html><html><head><title>Test</title></head><body><p>Hello world web crawlers.</p><p><a href="/about">About</a></p></body></html>',
    '/about': '<!DOCTYPE html><html><head><title>About</title></head><body><p>Crawlers extract text.</p></body></html>',
    '/robots.txt': 'User-agent: *\nDisallow: /private\nCrawl-delay: 0.01\n',
}

class TH(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        c = PAGES.get(self.path.split('?')[0])
        if c:
            self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
            self.wfile.write(c.encode())
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass

s = socketserver.TCPServer(('127.0.0.1', 9874), TH)
threading.Thread(target=s.serve_forever, daemon=True).start()
time.sleep(0.2)

idx = Indexer()
crawler = Crawler(seeds=['http://127.0.0.1:9874/'], depth=2, limit=10, workers=2, timeout=3.0, indexer=idx)
print('Starting run...', flush=True)
idx = crawler.run()
print('Run complete!', flush=True)
print(f'Docs: {idx.doc_count}', flush=True)
idx.save('/tmp/test_index.json')
print('Save complete!', flush=True)
s.shutdown()
s.server_close()
print('Done!', flush=True)
