# Revised Implementation Plan

## Overview

The crawler fails to increment `pages_crawled` when a page is successfully fetched but yields no indexable tokens (e.g., due to HTML parsing quirks). This causes the progress line to stay at 0, the index to remain empty, and search to return no results. Additionally, the `RobotHandler` lacks a timeout when fetching `robots.txt`, which can hang the entire crawl. The fixes below ensure that:

- Every successfully fetched HTML page (200, text/html) is counted.
- The `RobotHandler` respects the configured timeout and treats unreachable `robots.txt` as “allow all.”
- Text extraction is restored by excluding void elements (`<meta>`, `<link>`) from the skip-tag logic.
- Optional debug logging helps diagnose tokenisation issues.

All other features (CLI, concurrency, indexing, API, static HTML, error handling) are correctly implemented and remain unchanged.

## Key Modifications

| Component | Problem | Solution |
|-----------|---------|----------|
| `crawl_manager.py` – worker loop | `pages_crawled` incremented only after successful `indexer.add_document`, which returns `None` when no tokens are extracted → counter never advances. | **Increment `pages_crawled` immediately after confirming a `200` response with `Content-Type: text/html`**, using the shared lock to protect the counter. This fixes the live progress line and summary. |
| `robot_handler.py` – `_ensure_parser()` | Calls `parser.read()` without a timeout; if `robots.txt` is slow or unreachable, the thread can hang indefinitely. | Add a configurable `timeout` parameter (reuse the global `--timeout` value) to `urllib.request.urlopen`. On **any** exception during fetch, log a warning and skip caching a restrictive parser, effectively allowing all URLs for that domain. |
| `html_parser.py` – `TextExtractingParser` | The `skip_tags` set contains void elements (`meta`, `link`) that never trigger closing tags, causing `skip_depth` to remain > 0 permanently and discarding all subsequent text. | Remove `meta` and `link` from `skip_tags`; keep only `script`, `style`, `noscript`. This restores text extraction for pages containing these elements (e.g., `httpbin.org/html`). |
| (Optional) Debug output | No visibility into why tokens are empty. | Add conditional `print`/`logging.debug` statements in the worker to show extracted text length and token count. Helps diagnose tokenisation failures without changing production behavior. |

## Implementation Steps

### 1. Fix RobotHandler Timeout (robot_handler.py)

- Add a `timeout` parameter to the `RobotHandler` initialiser (default 10 seconds, matching the global fetch timeout).
- In `_ensure_parser()`, replace the bare `urllib.request.urlopen(robots_url)` with:
  ```python
  try:
      with urllib.request.urlopen(robots_url, timeout=self.timeout) as resp:
          parser = urllib.robotparser.RobotFileParser()
          parser.set_url(robots_url)
          parser.read()
          self._robots_parsers[domain] = parser
  except Exception as e:
      # Log a warning and do NOT add a parser – defaults to allow-all
      print(f"Warning: Could not fetch robots.txt for {domain}: {e}. Allowing all crawls.")
  ```
- Ensure that when the exception is caught, no `RobotFileParser` is stored for the domain. The `is_allowed()` method will then return `True` for any URL (because the domain is not in `_robots_parsers`).

### 2. Increment pages_crawled Early (crawl_manager.py)

In the worker loop that processes a URL:

1. After fetching the response, check `resp.status == 200` and `content_type.startswith('text/html')`.
2. Immediately increment the counter:
   ```python
   with self.lock:
       self.pages_crawled += 1
   ```
3. Then proceed to read, decode, parse HTML, extract text, tokenize, and index.  
   *If* text extraction yields no tokens (`add_document` returns `None`), the page is still counted, and the progress line will show the correct number. The `pages_failed` counter is only incremented for actual fetch failures, keeping the distinction clear.

### 3. Restore Text Extraction by Fixing Void Tags (html_parser.py)

- Change the `skip_tags` class attribute in `TextExtractingParser` from:
  ```python
  skip_tags = {'script', 'style', 'noscript', 'meta', 'link'}
  ```
  to:
  ```python
  skip_tags = {'script', 'style', 'noscript'}
  ```
- Confirm that `handle_starttag` increments `skip_depth` only for these tags, and `handle_endtag` decrements it correctly. No further changes required.

### 4. (Optional) Add Debug Logging

- Introduce a `debug` flag to the `CrawlManager` (or simply use a module-level constant).
- Inside the worker, after extracting text, add:
  ```python
  if self.debug:
      extracted_text = ...
      tokens = ... 
      print(f"[DEBUG] {url}: text length {len(extracted_text)}, tokens {len(tokens)}")
  ```
- This aids future diagnostics without cluttering normal output.

### 5. Integration & Verification

After applying the above:

- **Test with `httpbin.org/html`**:  
  - The progress line will show `Crawled: 1` (and more if depth > 1).  
  - Text will be extracted correctly (no longer suppressed by meta tags).  
  - The inverted index will contain terms, and `/search?q=html` will return results.  
  - The summary report will display non-zero totals.

- **Edge cases**:  
  - Domain with unreachable `robots.txt` → crawl proceeds without blocking.  
  - Page with empty body → crawled counter increments, but index empty (no crash).  
  - Permission errors for `search.html`/`index.json` continue to be handled gracefully with warnings.

All other existing functionality (CLI, concurrency, REST API, TF-IDF scoring, static HTML, etc.) remains unchanged and unaffected by these fixes.