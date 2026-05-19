## Implementation Plan: Web Crawler & Search Engine (Python, stdlib)

### 1. Files to Create and Their Purposes

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point, argument parsing, orchestration of crawl, server, and index loading. |
| `crawler.py` | `Crawler` class managing frontier queue, workers, robots.txt, rate limiting, depth tracking, and crawling lifecycle. |
| `parser.py` | `HTMLParser` subclass to extract visible text and hyperlinks from HTML content. |
| `url_utils.py` | URL normalization, domain extraction, robots.txt parsing and caching using `urllib.robotparser`. |
| `indexer.py` | Inverted index builder, simple Porter-like stemmer, stopword filter, TF-IDF computation, persistence. |
| `search_engine.py` | Query processing, TF-IDF ranking, result snippet generation using the built index. |
| `server.py` | REST API implemented with `http.server`, routes for `/search`, `/stats`, `/crawl`, `/crawl/{job_id}`. |
| `html_generator.py` | Generates a static `search.html` page with search form and JavaScript fetching. |
| `crawl_stats.py` | Shared stats object (pages crawled, queued, failed, current URL) for progress display. |

### 2. Architecture

```
CLI (main.py)
  │
  ├─> Crawler (crawler.py)
  │   ├─ uses url_utils (normalization, robots)
  │   ├─ uses parser (text + links extraction)
  │   └─ feeds DocumentStore (in-memory list of crawled documents)
  │
  ├─> Indexer (indexer.py) processes DocumentStore → builds inverted index + document metadata → writes JSON
  │
  ├─> SearchEngine (search_engine.py) loads index JSON → provides query ranking
  │
  └─> Server (server.py)
       ├─ mounts SearchEngine for /search, /stats
       ├─ spawns Crawler threads for /crawl, tracks jobs
       └─ generates search.html via html_generator.py
```

Threading model:
- Crawling uses `threading.Thread` pool, `queue.Queue` as shared work queue protected by a `threading.Lock` for stats (actually queue thread-safe, lock for shared counter/dict updates).
- REST server runs in main thread (blocks) or in a separate thread if crawling is ongoing (but spec says server starts after crawl with `--serve`, or spawns new crawl while server running – server runs continuously).

### 3. Implementation Order

1. **Project scaffolding**: `main.py` with argparse, basic logging.
2. **URL utilities** (`url_utils.py`): normalization, robots.txt retrieval and parsing.
3. **HTML parser** (`parser.py`): extract text and anchor links.
4. **Crawling engine** (`crawler.py`):
   - Frontier management, thread pool, per-domain rate limiting.
   - Integrate URL normalization, robots.txt, extraction.
   - Store documents (URL, title, text content) in a shared list.
   - Progress display via `crawl_stats.py`.
5. **Indexer** (`indexer.py`):
   - Tokenization, stemming, stopword removal.
   - Inverted index construction + TF count.
   - JSON persistence.
6. **Search engine** (`search_engine.py`):
   - Load index, compute IDF, score queries, produce snippets.
7. **REST API** (`server.py`):
   - Start HTTP server on given port.
   - Wire search, stats, crawl endpoints.
   - Implement crawl job management (thread safe).
8. **Static HTML generation** (`html_generator.py`): write `search.html`.
9. **Integration & polish**: summary report, live progress, error logging.

### 4. Libraries

- Entirely **Python standard library**.
- Key modules: `argparse`, `urllib.request`, `urllib.parse`, `urllib.robotparser`, `html.parser`, `json`, `re`, `threading`, `queue`, `http.server`, `time`, `os`, `sys`, `math`, `collections`, `string`.

### 5. Required Features – Implementation Details

#### CLI & Configuration
- `--seeds file` (required if crawling, not with `--load-index --serve`) read lines using `pathlib` or `open`.
- `--depth` (int, default 2), `--limit` (default 100), `--workers` (default 5), `--timeout` (default 10, for fetch).
- `--port` (default 8080) for server.
- `--serve` starts API server after crawl; if `--load-index`, skip crawl and start server.
- `--load-index file` specified instead of crawling; load existing JSON.

#### URL Normalization (`url_utils.py`)
- Use `urllib.parse.urljoin` to resolve relative URLs to absolute.
- Strip fragments with `urllib.parse.urldefrag`.
- Normalize scheme/host to lower case; remove default ports; sort query params? For deduplication we will keep simple: after fragment strip, use normalized URL as string key.
- Maintain a set of seen URLs to avoid duplicates.

#### Robots.txt Handling & Rate Limiting
- Before first fetch from a domain, fetch `robots.txt` using `urllib.robotparser.RobotFileParser`.
- Store parser instance per domain, reuse for all URLs in that domain.
- Respect `Crawl-delay` by tracking last access time per domain; before fetching, if delay is required, sleep in worker thread (no starvation because worker only one per domain at a time? We can hold a per-domain last_access timestamp with threading.Lock, sleep difference).
- Obey `Disallow` rules for each URL path.

#### Crawler (`crawler.py`)
- **Work Queue**: `queue.Queue` holding tuples `(url, depth)`.
- **Seed reading**: enqueue seeds with depth 0.
- **Thread Pool**: create `N` worker threads, each run loop: get task, fetch/mark done, extract links at depth < max_depth, enqueue new URLs.
- **Depth limit**: do not enqueue if depth+1 > max_depth.
- **Page limit**: stop enqueue if total pages fetched >= limit; workers exit when queue empty or limit reached.
- **Fetch**: use `urllib.request.urlopen` with timeout; catch `URLError`, `HTTPError`, `ssl.SSLError` (since stdlib can raise) and log one line per failed URL.
- **Content-Type detection**: check `response.headers['Content-Type']`, skip if not starting with 'text/html'.
- **Malformed HTML**: `html.parser` handles robustly; exceptions caught and logged.
- **Store documents**: each successful crawl stores a dict `{url, title (from <title>), text (cleaned), outlinks}` into a thread-safe shared list (append protected by lock).
- **Progress**: update `crawl_stats` object with current counters, print to terminal using `\r`.

#### HTML Parsing (`parser.py`)
- Subclass `html.parser.HTMLParser`.
- `handle_starttag` and data collection to extract text while ignoring `<script>`, `<style>`.
- Collect title from `<title>` tag.
- Extract links: from `<a href="...">` attributes; add to list if not `None`.

#### Text Processing for Indexing (`indexer.py`)
- **Tokenization**: split on whitespace and punctuation (use `re.findall(r'\b\w+\b')` after lowercasing).
- **Lowercasing**: `.lower()`.
- **Stopword filtering**: list of ~100 common English stop words (hard-coded as set).
- **Stemming**: implement a lightweight suffix-stripping stemmer (Porter-like) with rules: e.g., remove plurals `s`, `es`, `ies`; remove `ing`, `ed`, `ly`, etc. A simple function with replacement rules applied iteratively.
- **Term frequency**: For each document, count occurrences of each stemmed term.

#### Inverted Index & TF-IDF
- **Inverted Index** (`term -> {doc_id: tf_count}`).
- **Document metadata**: `doc_id -> {url, title, text_snippet (first 200 chars)}`.
- **TF-IDF computation**: After crawling, compute document frequency (df) for each term.
  - `idf = log(1 + N / (1 + df))` to avoid division by zero.
  - For each doc-term pair, store tf and precomputed weight? Or store only tf and compute score on the fly with idf to save memory.
- **Persistence**: after crawl, dump index + metadata + idf values to one JSON file. Structure:
  ```json
  {"doc_count": N, "terms": {"term": {"df": d, "docs": {"doc_id": tf}}}, "docs": {"doc_id": {...}}}
  ```
- **Loading**: `--load-index` reads this JSON and recreates index dict in memory.

#### Search Engine (`search_engine.py`)
- **Query processing**: tokenize, lower, stem, filter stopwords → query terms.
- **Ranking**: for each document that contains any query term:
  - Compute score = sum over terms (query_tf (1 normally) * term_tf * idf). Since query is short, no normalisation needed, but we can normalize by document length? Standard TF-IDF: tf * idf. Use sum of tf-idf scores across terms.
  - Use `SMOOTHING` if needed. We'll compute `score = sum(tf_doc * idf)`.
- **Result set**: after scoring, sort descending, return top `limit` results.
- **Snippet generation**: extract a window ~100 chars around each query term occurrence in document text, highlight terms with `<b>` (or store raw text and highlight client-side? The spec: "text snippet with query terms wrapped in bold tags" – server should send snippet with `<b>` tags). We'll do simple: find first occurrence of any query term in raw text, take a substring and insert `<b>` around matched terms using regex. Send snippet in JSON.
- **JSON response format**: `[{"title": ..., "url": ..., "score": ..., "snippet": "..."}, ...]`.

#### REST API Server (`server.py`)
- Extend `http.server.BaseHTTPRequestHandler`.
- **Routing**: parse `path` manually with regex/if-else.
  - `GET /search?q=query&limit=N` → calls search engine, returns JSON.
  - `GET /stats` → reads current stats (page count, term count, index file size, crawl duration) and returns JSON. Stats stored in a global dict updated by crawl/setup.
  - `GET /crawl` → starts new crawl in a new thread. Assign an incrementing `job_id`, store job status dict: `{status: "running", pages_crawled: 0, total_queued: 0}`. Return `{"job_id": int}`.
  - `GET /crawl/{job_id}` → look up job status, return JSON.
- **Thread safety**: access to global search engine (index) may be read while crawl updates. For simplicity, when a crawl job finishes, it replaces the global index atomically (using a lock). During crawl, /search uses the existing index. If no index exists, return empty.
- **CORS** (for local HTML fetch): add `Access-Control-Allow-Origin: *` header to responses.
- **Content-Type**: `application/json`.

#### Static HTML Generation (`html_generator.py`)
- Generate `search.html` with:
  - A text input and search button.
  - On submit (or keyup), use `fetch('/search?q=' + encodeURIComponent(query) + '&limit=10')` (assumes server on same host and port? For local file opened via `file://`, fetch to same origin won't work directly. We'll set the API base URL to `http://localhost:<port>` with `<script> const API_BASE = 'http://localhost:' + new URLSearchParams(window.location.search).get('port') || '8080';` But better: serve HTML from server with a route, so we don't need cross-origin. But spec says "static search.html file... that queries the REST API". We'll embed the server address as a JavaScript variable that can be configured. Include a note to open on same server. We'll add a route `GET /` that serves the same HTML, making it self-contained.
- Display results: each result as `<div>` with link, URL, score, and snippet with bold tags (already in snippet).
- Use `innerHTML` to render (safe because we generated snippet with plain text + `<b>`).

#### Error Handling & Logging
- All `urllib` errors caught, log to stderr: e.g., `print(f"ERROR: {url} - {e}", file=sys.stderr)`.
- Malformed HTML: catch exceptions from `HTMLParser`, log and skip content extraction but still may collect links if possible.
- Timeouts: set `urllib.request.urlopen` timeout parameter.

#### Live Progress Display
- Use `print(f"\rCrawled: {crawled} | Queued: {queued} | Failed: {failed} | Current: {current_url[:60]:<60}", end="")` and `sys.stdout.flush()`.
- Update every 0.5s using a separate reporting thread or in main after crawl completes.

#### Summary Report
- After crawl: print total pages, total unique terms, index size, top 10 domains by number of pages linked (count of in-links? Actually "top 10 most linked domains": count how many pages in the corpus link to each domain; crawl links from parsed outlinks). We'll count occurrences of link domains in all crawled pages. Print elapsed time.

#### Concurrency Details
- Thread pool via `threading.Thread(target=worker)`.
- Queue is `queue.Queue`.
- Protect shared data: `seen_urls` set use lock; `documents` list append with lock; `crawl_stats` counters use lock.
- Rate limiting: per-domain `threading.Lock` for last_access timestamp dict.

### Additional Implementation Notes
- The stemmer will be a simple function with a series of `re.sub` rules to strip common suffixes; no need for full Porter.
- For `robots.txt` caching, use a dict keyed by domain, initialized once per domain; each worker thread can use without lock (since dict keys are read from master, each domain’s robot parser is created once and not reused? Actually create when first URL encountered; use a lock to ensure only one thread creates it, then all use it).
- JSON file writable with `json.dump`; for large index, but default 100 pages is small.
- When `--serve` is used, the server blocks; if also crawling before, wait crawl complete then start server.
- `GET /crawl` triggers asynchronous crawl: the server handler will start a new thread that runs the same crawl logic but also sets a global `current_crawl_job`. This thread accesses the same index later? After completion, it builds a new index and replaces the global index with a lock. Be careful with server handler concurrency (multiple requests). Use `threading.Lock` to protect swapping index.