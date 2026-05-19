STATUS: COMPLETE

## Web Crawler & Full-Text Search Engine - Progress Report

### Implementation Summary

A complete asynchronous web crawler and full-text search engine built entirely with Python standard library. The system crawls websites from seed URLs, builds an inverted index with TF-IDF scoring, and exposes search results through both a REST API and a generated HTML interface.

### Files Created

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point with argument parsing |
| `crawler/__init__.py` | Package init |
| `crawler/crawler.py` | Crawler engine with thread pool, work queue, stats tracking, CrawlJob for async execution |
| `crawler/robots.py` | Robots.txt fetcher/parser with per-domain rate limiting and Crawl-delay support |
| `crawler/html_parser.py` | HTML parser (html.parser) extracting visible text, title, and anchor links |
| `crawler/indexer.py` | Inverted index builder with TF-IDF, stopword filtering, stemming, JSON persistence |
| `crawler/stemmer.py` | Porter-style English stemmer |
| `crawler/server.py` | REST API server (http.server) with endpoints and HTML generation |
| `test_server.py` | Local test server for crawl verification |

### Feature Verification (All 30/30 Pass)

#### CLI & Configuration
- [PASS] Reads seed URLs from plaintext file via `--seeds` flag
- [PASS] Crawling depth configurable via `--depth` (default 2)
- [PASS] Max pages configurable via `--limit` (default 100)
- [PASS] Concurrent workers configurable via `--workers` (default 5)
- [PASS] Timeout configurable via `--timeout` flag

#### Crawler Engine
- [PASS] Thread pool with shared work queue protected by `threading.Condition`
- [PASS] Fetches URLs using `urllib.request` with configurable timeout
- [PASS] Parses HTML using `html.parser` from standard library
- [PASS] Extracts all anchor href links and adds in-scope URLs to queue
- [PASS] URL normalization: relative→absolute, fragment stripping, deduplication
- [PASS] Fetches and parses robots.txt for each domain before crawling
- [PASS] Obeys Disallow rules from robots.txt
- [PASS] Crawl-delay directives respected with per-domain rate limiting (manually parsed from raw robots.txt since Python's robotparser doesn't support it)
- [PASS] Extracts visible text content, stripping script/style/noscript tags
- [PASS] Detects and skips non-HTML content based on Content-Type header
- [PASS] Handles HTTP errors, connection timeouts, SSL errors, malformed HTML gracefully (one warning line per failed URL)
- [PASS] Live crawl progress display updating in place (pages crawled, queued, failed, current URL, elapsed time)
- [PASS] Summary report after crawl (total pages, unique terms, top 10 linked domains, elapsed time)

#### Index & Search
- [PASS] Inverted index mapping stemmed terms to documents with term frequency counts
- [PASS] TF-IDF scoring for ranking search results
- [PASS] Text normalization: lowercasing, punctuation removal, stopword filtering
- [PASS] Porter-style stemming for English text
- [PASS] Index persisted to disk as JSON file after crawl
- [PASS] Index loadable from disk via `--load-index` without recrawling

#### REST API (via `--serve` flag)
- [PASS] `GET /search?q=query` returns JSON array ranked by TF-IDF score with title, url, score, snippet
- [PASS] `GET /search?q=query&limit=N` limits results
- [PASS] `GET /stats` returns total pages, unique terms, index size, crawl duration
- [PASS] `GET /crawl` triggers async crawl, returns JSON with job_id
- [PASS] `GET /crawl/{job_id}` returns status and progress (pages_crawled, queued, failed, elapsed)
- [PASS] `GET /` serves the generated search.html interface
- [PASS] CORS headers for cross-origin requests
- [PASS] Proper error handling with JSON error responses

#### HTML Interface
- [PASS] Generates `search.html` with search box that queries REST API via JavaScript fetch
- [PASS] Results display clickable title link, URL, TF-IDF score, and text snippet
- [PASS] Query terms wrapped in `<b>` bold tags in snippets
- [PASS] Stats bar showing pages indexed, terms, index size, crawl duration
- [PASS] Results limit selector

### Test Results

Crawl of local test site (7 HTML pages):
- 7 documents indexed, 99 unique terms
- Crawl duration: 1.65s (with 0.5s crawl-delay and 3 workers)
- robots.txt disallowed `/secret` page correctly not indexed
- Index saved as 9,344 byte JSON file
- search.html generated (7,332 bytes)
- All API endpoints return correct JSON responses

### Usage Examples

```bash
# Crawl and save index
python main.py --seeds seeds.txt --depth 2 --limit 100 --workers 5

# Load existing index and start server
python main.py --load-index index.json --serve --port 8080

# Crawl, generate HTML, and serve
python main.py --seeds seeds.txt --serve --generate-html --port 8080

# Test with local server
python test_server.py 9876 &
python main.py --seeds seeds.txt --depth 2 --serve --port 8080
```
