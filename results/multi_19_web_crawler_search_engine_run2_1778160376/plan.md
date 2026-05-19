```markdown
# Revised Implementation Plan: Web Crawler Search Engine

## 1. Project Structure and Files

```
project/
├── main.py                # Entry point, CLI argument parsing, orchestration
├── crawler.py             # Crawler class: frontier, workers, fetching, parsing
├── indexer.py             # Inverted index builder, TF-IDF computation, persistence
├── search_engine.py       # Search logic: query processing, ranking, snippet extraction
├── api_server.py          # REST API server (http.server), crawl job management
├── html_generator.py      # Generates static search.html
├── utils.py               # URL normalization, live progress display, logging
├── stemmer.py             # Simple suffix-stripping stemmer
└── stopwords.py           # Set of English stopwords
```

All code uses only the Python standard library.

## 2. Architecture Overview

The system is composed of four main subsystems:

- **Crawler** (`crawler.py`): Maintains a URL frontier (thread-safe queue), a thread pool of workers, and per‑domain rate‑limiters. Workers fetch pages, respect `robots.txt`, extract text and links, and feed them to the Indexer.
- **Indexer** (`indexer.py`): Receives (doc_id, text) pairs, tokenizes, normalizes, stems, filters stopwords, and builds an inverted index with term frequencies. After crawling, it computes IDF values and writes the complete index to disk as JSON.
- **Search Engine** (`search_engine.py`): Loads a persisted index, processes query strings using the same pipeline, computes TF‑IDF scores, ranks documents, and generates snippets.
- **API Server** (`api_server.py`): Starts an HTTP server on a configurable port. It serves endpoints `/search`, `/stats`, `/crawl`, `/crawl/<job_id>`, and manages background crawl jobs using threads and a job state dictionary.

The flow:
1. `main.py` reads CLI flags. If `--load‑index` is given, it loads the index and optionally starts the server. Otherwise, it creates a `Crawler` instance, runs the crawl, builds the index, persists it, and finally starts the server if `--serve` is set.
2. During crawling, workers update a shared `Indexer` (protected by a lock). A live progress line is printed to the terminal.
3. The API server holds a reference to the current `SearchEngine` instance. When a new crawl job is triggered via `/crawl`, the server spawns a thread that runs a new crawl, builds a fresh index, and atomically swaps it into the active `SearchEngine`.

## 3. Implementation Order

1. **Utilities** (`utils.py`, `stemmer.py`, `stopwords.py`)
   - URL normalisation, logging helper, progress display, stemmer, stopword list.

2. **Indexer** (`indexer.py`)
   - Tokeniser, text normalisation, stemming, stopword filter.
   - In‑memory inverted index building (thread‑safe with lock).
   - Serialisation to/from JSON.

3. **Crawler** (`crawler.py`)
   - `RobotsParser` (fetch and parse `robots.txt`, query allow/disallow, enforce `Crawl‑delay` correctly using `rp.crawl_delay('*')`).
   - `Fetcher` (urllib, timeout, Content‑Type check, error logging).
   - `HTMLProcessor` (html.parser, extract text, extract links).
   - `Crawler` class: thread pool, `queue.Queue` frontier, visited set, coordination with Indexer, live progress callback.
   - **RateLimiter**: a helper class that given a domain and its cached `RobotFileParser`, calls `rp.crawl_delay("*")` to obtain the required delay (defaulting to `0.0` on any error or `None`). It uses a lock (`threading.Lock`) to protect access to a per‑domain last‑fetch timestamp dictionary, ensuring the sleep interval is calculated inside the locked section but the `time.sleep()` is performed outside the lock to avoid blocking other threads.

4. **Search Engine** (`search_engine.py`)
   - Load index from JSON.
   - Query processing (same pipeline as indexing).
   - TF‑IDF scoring and ranking.
   - Snippet generation.

5. **Main orchestration** (`main.py`)
   - Argparse setup for `--seeds`, `--depth`, `--limit`, `--workers`, `--timeout`, `--port`, `--serve`, `--load‑index`.
   - Run crawl, print summary, persist index.
   - Start server if needed.

6. **API Server** (`api_server.py`)
   - Custom `BaseHTTPRequestHandler` routing.
   - Endpoint handlers for `/search`, `/stats`, `/crawl`, `/crawl/<id>`.
   - Job manager: generate job IDs, launch crawl threads, track progress.

7. **HTML Generator** (`html_generator.py`)
   - Write a static `search.html` that uses JavaScript’s `fetch` to query `/search` and render results with bold query terms.

## 4. Libraries Used

- `argparse` – CLI parsing.
- `urllib` (request, parse, error, robotparser) – HTTP fetching, URL parsing, robots.txt handling.
- `html.parser` – built‑in HTML parser.
- `queue`, `threading`, `concurrent.futures` – thread pool (use `ThreadPoolExecutor` from `concurrent.futures`; shared state protected with `threading.Lock`).
- `json` – index persistence.
- `http.server` – REST API.
- `sys`, `os`, `time`, `re`, `uuid`, `logging` – general utilities.
- `math` – for `log` in TF‑IDF.

## 5. Feature Implementation Details

### CLI & Configuration
- `argparse` defines all flags with defaults:
  - `--seeds` (required unless `--load-index`), `--depth` (2), `--limit` (100), `--workers` (5), `--timeout` (10s), `--port` (8080), `--serve` (store_true), `--load-index` (optional index file).
- `--limit` cap on crawled pages is enforced in the crawler loop.
- `--timeout` given to `urllib.request.urlopen`.

### Seed File
- Read line‑by‑line, strip whitespace, skip empty lines.
- Each URL is normalised and added to the initial crawl queue.

### URL Normalisation (`utils.py`)
- Use `urllib.parse.urljoin` to resolve relatives to the base page’s URL.
- Strip fragment with `urldefrag`.
- Remove trailing `/` from path unless it’s the root.
- Use a set for deduplication (visited URLs).

### Crawler Concurrency
- A `ThreadPoolExecutor` with `max_workers = args.workers` manages worker threads.
- The URL frontier is a `queue.Queue` (unbounded) that holds `(url, depth)` pairs.
- Workers fetch from the queue, fetch page, extract links, submit normalized new URLs back to the queue.
- Shared mutable state (visited set, indexer, domain rate limits) protected by `threading.Lock`.

### HTML Parsing (`crawler.py`)
- Subclass `html.parser.HTMLParser`.
- Override `handle_starttag` to collect `<a>` tags and extract `href`.
- Override `handle_data` to capture visible text.
- Ignore `<script>` and `<style>` content: in `handle_starttag`, if tag is script or style, set a flag to skip data until closing tag.
- On `handle_endtag`, reset skip flag.
- Text extraction: join all `handle_data` chunks with a space, then clean whitespace.

### Robots.txt Handling
- A `RobotsCache` dictionary mapping domain → `urllib.robotparser.RobotFileParser`, protected by a lock.
- Before fetching any page on a domain:
  - If domain not in cache, create `RobotFileParser`, set its URL to `http(s)://domain/robots.txt`, call `read()`.
  - Query `can_fetch("*", url)` – if False, skip the URL and log.
  - For rate limiting, use a separate `RateLimiter` class that:
    - Obtains the crawl delay by calling `rp.crawl_delay("*")` on the cached parser. If the call returns `None` or raises an exception, the delay defaults to `0.0`.
    - Maintains a dictionary `last_fetch[domain]` (timestamp) protected by a lock.
    - Before a fetch for a given domain, the worker calls `RateLimiter.wait(domain)`. The method:
      1. acquires the lock,
      2. reads the last fetch timestamp and the delay,
      3. calculates the required wait (`max(0.0, delay - (now - last_fetch))`),
      4. releases the lock,
      5. if wait > 0, sleeps for that duration,
      6. after the fetch, updates the `last_fetch` timestamp again under the lock.
    - This design ensures locks are held only for a minimal critical section and never during `time.sleep()`, following the review’s exception‑safety requirement.

### Rate Limiting (detailed)
- The `RateLimiter` class encapsulates the logic described above.
- Domains without a `robots.txt` entry default to `crawl_delay = 0.0`.
- The class stores a shared `last_fetch` dictionary and a reference to the `RobotsCache` to query delays.
- Its `wait(domain)` method is thread‑safe and uses a `with self.lock:` context manager for timestamp read/write, solving the exception‑safety issue.

### Text Normalisation & Stemming
- Tokenisation: split on non‑alphanumeric characters, lowercasing.
- Punctuation removal (handled by tokenisation).
- Stopword filter: use a predefined set from `stopwords.py`.
- Stemming: a simple rule‑based stemmer in `stemmer.py` (e.g., remove common suffixes `"ing"`, `"ed"`, `"s"`, `"ly"`, `"ness"`) applied iteratively.

### Inverted Index (`indexer.py`)
- Shared `Indexer` instance:
  - `index`: dict `{term: {doc_id: tf}}` where `tf` = raw term frequency in that doc.
  - `doc_texts`: dict `{doc_id: original plain text}` (for snippet generation).
  - `doc_meta`: dict `{doc_id: {url, title}}`.
  - `doc_count`: integer.
  - Lock for all shared structures.
- Method `add_document(doc_id, url, title, text)`:
  - Tokenize, normalise, stem, remove stopwords.
  - Count term frequencies, update `index[term][doc_id] += count`.
  - Store `doc_texts[doc_id] = text`, `doc_meta[doc_id] = {url, title}`.
- After crawl, `finalize()`:
  - For each term, compute `df` = number of docs containing it.
  - Compute `idf = math.log(N / df)` where N = total docs.
  - Store `idf` in a separate dict or directly within the serialisable structure.
- `save(path)` writes a JSON dict with keys: `"docs"`, `"index"`, `"N"`. The `"index"` maps `term → {doc_id: tf, df: int, idf: float}`.
- `load(path)` reconstructs the index and the `SearchEngine` can use it directly.

### TF‑IDF Scoring (`search_engine.py`)
- Query processor same as indexing pipeline.
- For each query term:
  - If term in index, fetch `{doc_id: tf}` and use the term’s `idf`.
  - For each doc, `score += tf * idf` (TF itself can be scaled: raw TF used here; may be extended with logarithmic scaling).
- Rank docs by descending score.
- Return top `limit` results with: title, url, score, snippet.

### Text Snippet
- For each matching doc, locate the first occurrence of any query term in the original text (case‑insensitive).
- Extract a window of ~150 characters around that position (split on word boundaries).
- Wrap every occurrence of any query term with `<b>` tags (for the final HTML rendering).

### API Server (`api_server.py`)
- Inherit from `http.server.BaseHTTPRequestHandler`.
- Routes:
  - `GET /search?q=…&limit=N` → calls `search_engine.search(q, limit)` → returns JSON array.
  - `GET /stats` → reads current index’s stats (total crawled pages, unique terms, index file size, crawl duration stored from last crawl).
  - `GET /crawl` → generates a `job_id` (uuid4), starts a background thread that runs a new crawl using the same seed file, updates job status. Returns `{"job_id": …}`.
  - `GET /crawl/{job_id}` → looks up job in a thread‑safe dict and returns `{"status": "running", "pages_crawled": N}` or `"completed"`.
- Job execution: the crawl thread creates its own Crawler and Indexer; when finished, it replaces the server’s `search_engine` instance atomically (using a lock).

### Static HTML Interface (`html_generator.py`)
- Function `generate_search_html(port)` writes a file named `search.html` in the current directory.
- The HTML contains a simple form with an input field and a submit button.
- JavaScript attaches an event listener to the form’s submit; on submit, it fetches `http://localhost:{port}/search?q=` + query + `&limit=20`.
- Results are rendered as a list: each result shows a clickable title (`<a href="url">`), the URL, the score, and the snippet (innerHTML set to the received snippet which may contain `<b>` tags).

### Error Handling & Logging
- All network errors (HTTP errors, timeout, SSL) are caught in the fetcher; one‑line error log per failed URL using `logging.error`.
- Non‑HTML content is skipped by checking `Content-Type` header: if `text/html` not in content type (lowercased), discard.
- Malformed HTML: the parser continues silently; we catch any `HTMLParser.HTMLParseError` (rare) and log, then skip indexing that page.
- At the end of crawling, a summary of total pages, terms, duration is printed.

### Live Progress & Summary Report
- A `ProgressMonitor` thread or callback updates a single line on the terminal:
  `\rCrawled: X | Queued: Y | Failed: Z | Current: <url> ...` using `sys.stdout.write` and `flush()`.
- After crawl, print a summary:
  - total pages crawled, total unique terms indexed, crawl duration.
  - Top 10 most linked domains (aggregate domain from all extracted links, count occurrences, sort descending, print top 10).

All these pieces fit together in `main.py` which orchestrates the workflow based on CLI flags.

## 6. Key Changes to Address Review Feedback

- **Fixed `Crawl-delay` extraction**: In `crawler.py`, the `RobotsCache` no longer uses `getattr`; it directly calls `rp.crawl_delay("*")`. Any exception or `None` return causes a fallback to `0.0`. This ensures the rate‑limiting is fully functional.
- **Exception‑safe lock usage**: The `RateLimiter` class uses a `with self.lock:` context manager for all accesses to the `last_fetch` dictionary. The actual `time.sleep()` is performed outside the lock, preventing deadlocks and lock contention issues.
- **Missing feature now correctly implemented**: “Obeys Disallow rules and Crawl-delay directives from robots.txt with per-domain rate limiting” is fully covered by the updated design. Disallow rules are already handled via `can_fetch`, and the revised `RateLimiter` correctly applies the crawl delay.

No other parts of the plan require modification. The CLI error shown in the test output is expected when no `--seeds` or `--load-index` flag is provided; the plan already describes this behaviour. The implementation will handle the required argument logic as specified.
```