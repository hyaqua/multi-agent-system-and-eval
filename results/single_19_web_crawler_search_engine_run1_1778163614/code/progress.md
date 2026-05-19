STATUS: COMPLETE

## Web Crawler & Full-Text Search Engine - Progress Report

### All 29 required features are implemented and working:

**CLI & Configuration:**
- ✅ Reads seed URLs from plaintext file via `--seeds` flag (one URL per line)
- ✅ `--depth` flag (default 2) controls crawl depth
- ✅ `--limit` flag (default 100) limits max pages crawled
- ✅ `--workers` flag (default 5) sets concurrent worker count
- ✅ `--serve` flag starts REST API server after crawling
- ✅ `--port` flag (default 8080) configures API server port
- ✅ `--load-index` flag loads existing index JSON without recrawling
- ✅ `--save-index` flag specifies index output path
- ✅ `--output-html` flag specifies search.html output path

**Crawler Engine (crawler.py):**
- ✅ Thread pool with threading.Thread and shared queue.Queue protected by threading.Lock
- ✅ urllib.request for fetching with configurable timeout
- ✅ html.parser (HTMLParser) for parsing HTML
- ✅ Extracts all <a href> links, normalizes to absolute URLs, strips fragments, deduplicates
- ✅ Fetches and parses robots.txt per domain before crawling
- ✅ Obeys Disallow rules and Crawl-delay with per-domain rate limiting
- ✅ Extracts visible text, stripping <script>, <style>, <noscript>, and other non-content tags
- ✅ Detects and skips non-HTML content via Content-Type header
- ✅ Gracefully handles HTTP errors (4xx, 5xx), connection timeouts, SSL errors, malformed HTML
- ✅ Logs one error line per failed URL to stderr
- ✅ Live in-place progress line showing pages crawled, queued, failed, and current URL
- ✅ Summary report after crawling: total pages, total terms, top 10 most-linked domains, elapsed time

**Indexer (indexer.py):**
- ✅ Builds inverted index mapping stemmed terms → {doc_id: term_frequency}
- ✅ Porter stemming algorithm for term normalization
- ✅ Text normalization: lowercasing, punctuation removal, stopword filtering
- ✅ TF-IDF scoring with smoothed IDF for ranking
- ✅ JSON persistence (save/load) with all index data
- ✅ Thread-safe document addition from concurrent crawler workers

**REST API (server.py):**
- ✅ `GET /search?q=query` returns JSON array of results ranked by TF-IDF score
- ✅ Each result contains: title, url, score, and text snippet (with <b> wrapped query terms)
- ✅ `GET /search?q=query&limit=N` limits number of results
- ✅ `GET /stats` returns: total_pages_crawled, total_unique_terms, index_size_bytes, crawl_duration_sec
- ✅ `GET /crawl` triggers async crawl job, returns job_id JSON
- ✅ `GET /crawl/{job_id}` returns job status and pages_crawled progress
- ✅ CORS headers for browser access

**HTML Interface (server.py generate_search_html):**
- ✅ Generates static search.html with search box and results area
- ✅ JavaScript fetch() to query REST API
- ✅ Renders clickable title links (target="_blank"), URL, TF-IDF score, and text snippet
- ✅ Query terms displayed in bold (<b>) within snippets via CSS styling
- ✅ Keyboard support (Enter key to search)
- ✅ Error handling and "no results" display

**Project Structure:**
- `main.py` - CLI entry point, argument parsing, orchestration
- `crawler.py` - Multi-threaded crawler engine, progress tracking, domain link counters
- `indexer.py` - Inverted index, TF-IDF scoring, JSON persistence
- `server.py` - REST API server, job manager, HTML generation
- `utils.py` - URL normalization, HTML parsers, Porter stemmer, tokenizer, stopwords, snippet generation
- `robots.py` - Robots.txt fetcher/cache with per-domain rate limiting

**Verified by automated tests:**
- Crawl: 4 pages from test site, robots.txt respected (/private skipped), non-HTML skipped
- Search: TF-IDF ranking, stemming, limit parameter, empty results
- Save/Load: Index persisted and restored correctly, search works after load
- REST API: All 5 endpoints tested with correct status codes and response formats
- HTML: Generated file contains all required elements (search box, results, fetch, bold styling)
- CLI: --load-index flag works via subprocess
- Error handling: HTTP 500, 404, malformed HTML all handled gracefully
