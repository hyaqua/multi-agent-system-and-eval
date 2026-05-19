STATUS: COMPLETE

# Web Crawler & Full-Text Search Engine - Progress Report

## Implemented Features

### Core Crawling
1. **Seed URL file reading** (`--seeds` flag) - Reads plaintext file with one URL per line, validates and normalizes URLs
2. **Configurable crawl depth** (`--depth` flag, default 2) - Controls how many link levels to follow
3. **Page limit** (`--limit` flag, default 100) - Maximum pages to crawl
4. **Concurrent workers** (`--workers` flag, default 5) - Thread pool with shared work queue (`queue.Queue`) protected by `threading.Lock` for shared state
5. **URL fetching** - Uses `urllib.request` with configurable timeout; handles HTTP errors, connection timeouts, SSL errors gracefully
6. **HTML parsing** - Uses `html.parser.HTMLParser` from stdlib; extracts visible text (strips scripts/styles) and anchor href links
7. **URL normalization** - Resolves relative URLs, strips fragments, lowercases scheme/host, removes default ports, deduplicates

### Robots.txt Compliance
8. **Robots.txt fetching** - Fetches and parses robots.txt for each domain before crawling
9. **Disallow rules** - Skips URLs matching disallow paths
10. **Crawl-delay** - Per-domain rate limiting using per-domain locks and `time.sleep()`

### Indexing & Search
11. **Inverted index** - Maps stemmed terms to documents with term frequency counts
12. **TF-IDF scoring** - Computes TF (log normalization) × IDF for ranked search results
13. **Text normalization** - Lowercasing, punctuation removal, stopword filtering (~150 English stopwords)
14. **Stemming** - Simplified Porter-like stemmer handling -ing, -ed, -s, -es, -er, -est, -ly suffixes
15. **Text snippets** - Generated with query terms wrapped in `<b>` tags for highlighting

### Persistence
16. **JSON persistence** - Index saved to JSON file after crawling completes (`--save-index`)
17. **Index loading** (`--load-index`) - Load index from disk without recrawling

### REST API Server
18. **Configurable port** (`--serve PORT`) - Starts HTTP server using `http.server`
19. **GET /search?q=query** - Returns JSON array with title, url, score, snippet, ranked by TF-IDF
20. **GET /search?q=query&limit=N** - Limits number of results
21. **GET /stats** - Returns pages_crawled, unique_terms, index_size_bytes, crawl_duration_seconds
22. **GET /crawl** - Triggers async crawl job, returns job_id
23. **GET /crawl/{job_id}** - Returns job status with pages_crawled, status, error

### HTML Interface
24. **search.html generation** - Static HTML file with search box
25. **JavaScript fetch API** - Queries REST API and renders results dynamically
26. **Result display** - Clickable title link, URL, TF-IDF score, snippet with bold query terms

### Error Handling
27. **HTTP errors** - 404, 500, connection errors logged (one line per failed URL)
28. **Non-HTML detection** - Skips content based on Content-Type header
29. **Malformed HTML** - Graceful handling via html.parser error resilience

### Terminal Output
30. **Live progress** - Carriage-return updating line: pages crawled, queued, failed, current URL
31. **Summary report** - Total pages, total terms, top 10 linked domains, elapsed time

## Files Created

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point, arg parsing, orchestration |
| `crawler.py` | CrawlManager with thread pool, work queue, locks |
| `fetcher.py` | URL fetching via urllib with error handling |
| `html_parser.py` | HTML parsing for text and link extraction |
| `url_utils.py` | URL normalization, resolution, dedup |
| `robots.py` | Robots.txt fetching, parsing, rate limiting |
| `indexer.py` | Inverted index, TF-IDF, stemming, stopwords, JSON I/O |
| `server.py` | REST API server + search.html generation |
| `reporter.py` | Live progress display + summary report |
| `test_server.py` | Local test server with sample pages |
| `test_integration.py` | Integration test suite |
| `seeds.txt` | Sample seed URLs |

## Testing Results

- All imports work correctly (pure stdlib)
- URL normalization handles all edge cases (fragments, relative URLs, case, ports, dedup)
- Crawler successfully crawls 4 local test pages, respects robots.txt (skips /private), skips non-HTML content
- Inverted index built with 129 unique terms from 4 documents
- TF-IDF search returns relevant ranked results with proper snippets
- Index JSON persistence: save and load round-trips correctly
- REST API: /search, /stats, /crawl, /crawl/{id} all return correct JSON
- HTML interface: 4950 bytes, includes search box, fetch API, result rendering
- Different worker counts (1, 3, 5) all work correctly
- `--no-save` flag prevents index persistence
- Server runs on configurable port and serves all endpoints

## Known Minor Issues

1. The stemmer is simplified and may produce imperfect stems for some edge cases (e.g., "indexing" → "indexe"). Since both indexed terms and query terms go through the same stemmer, search consistency is maintained.

2. The live progress line uses `\r` carriage return which can cause display artifacts when stdout is piped or redirected. The underlying crawl logic is correct.

3. In the test environment, DNS resolution is not available, so external URL crawling cannot be tested. All tests use a local test server.

## Usage Examples

```bash
# Crawl and save index
python main.py --seeds seeds.txt --depth 2 --limit 100 --workers 5

# Crawl and start API server
python main.py --seeds seeds.txt --serve 8080

# Load existing index and serve
python main.py --load-index index.json --serve 8080

# Quick crawl without saving
python main.py --seeds seeds.txt --depth 1 --limit 20 --no-save
```
