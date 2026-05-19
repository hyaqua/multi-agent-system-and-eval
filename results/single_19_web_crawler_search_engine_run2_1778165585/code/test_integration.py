"""Integration test script for the web crawler and search engine."""

import sys
import os
import time
import json
import threading
import urllib.request
import urllib.error
import socket

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_server import start_test_server
from url_utils import normalize_url, get_domain
from crawler import CrawlManager
from indexer import InvertedIndex, Document
from reporter import CrawlReporter
from server import SearchAPIServer, generate_search_html, SearchAPIHandler

# Find free ports
def _free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

TEST_PORT = _free_port()
API_PORT = _free_port()
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

PASS_COUNT = 0
FAIL_COUNT = 0

def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"    PASS: {name}")
    else:
        FAIL_COUNT += 1
        print(f"    FAIL: {name} {detail}")

def run_tests():
    global PASS_COUNT, FAIL_COUNT
    
    print("=" * 70)
    print("  WEB CRAWLER & SEARCH ENGINE - INTEGRATION TESTS")
    print("=" * 70)

    # Start test server
    print("\n[1] Starting test HTTP server...")
    server = start_test_server(TEST_PORT)
    time.sleep(0.5)

    try:
        req = urllib.request.Request(f"{BASE_URL}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode()
            assert "Test Home" in content
            print("    Test server is running OK")
    except Exception as e:
        print(f"    FAILED: Test server not responding: {e}")
        server.shutdown()
        return False

    # === Test 1: URL normalization ===
    print("\n[2] URL normalization...")
    check("strip fragment", normalize_url("http://example.com/path/#frag") == "http://example.com/path")
    check("resolve relative", normalize_url("/relative", "http://example.com/base") == "http://example.com/relative")
    check("lowercase host", normalize_url("https://EXAMPLE.COM") == "https://example.com/")
    check("empty URL", normalize_url("") == "")
    check("reject ftp", normalize_url("ftp://bad.com") == "")
    check("dedup trailing slash", normalize_url("http://example.com//path//") == "http://example.com/path")
    check("remove default port", normalize_url("http://example.com:80/path") == "http://example.com/path")
    check("domain extraction", get_domain("https://www.example.com/path") == "www.example.com")

    # === Test 2: Seed file parsing ===
    print("\n[3] Seed file parsing...")
    seed_file = "/tmp/test_seeds.txt"
    with open(seed_file, "w") as f:
        f.write(f"{BASE_URL}/\n")
        f.write(f"# comment line\n")
        f.write(f"  {BASE_URL}/page1  \n")
    from main import read_seeds
    seeds = read_seeds(seed_file)
    check("seed count", len(seeds) == 2, f"got {len(seeds)}")
    check("seed URL", seeds[0] == f"{BASE_URL}/")
    check("seed URL 2", seeds[1] == f"{BASE_URL}/page1")

    # === Test 3: Crawling ===
    print("\n[4] Crawler...")
    reporter = CrawlReporter()
    index = InvertedIndex()

    cm = CrawlManager(
        seeds=[f"{BASE_URL}/"],
        depth=2,
        limit=10,
        workers=2,
        timeout=5.0,
        index=index,
        reporter=reporter,
    )

    print("    Starting crawl...")
    index = cm.crawl()

    pages_crawled = cm.pages_crawled
    pages_failed = cm.pages_failed
    print(f"\n    Crawled: {pages_crawled} pages, {pages_failed} failed")
    print(f"    Index: {index.doc_count} docs, {len(index.index)} terms")

    check("pages crawled", pages_crawled >= 3, f"got {pages_crawled}")
    check("terms indexed", len(index.index) > 10, f"got {len(index.index)}")
    check("doc count matches", index.doc_count == pages_crawled)
    check("robots.txt respected", all("/private" not in url for url in index.documents))
    check("non-HTML skipped", all("/not-html" not in url for url in index.documents))

    # === Test 4: TF-IDF Search ===
    print("\n[5] TF-IDF Search...")
    results = index.search("python programming", limit=10)
    print(f"    Results for 'python programming': {len(results)}")
    for r in results:
        print(f"      {r['title'][:50]} (score: {r['score']})")
    check("search returns results", len(results) > 0)
    check("result has title", all("title" in r for r in results))
    check("result has url", all("url" in r for r in results))
    check("result has score", all("score" in r for r in results))
    check("result has snippet", all("snippet" in r for r in results))
    check("snippet has bold tags", any("<b>" in r["snippet"] for r in results))

    results_limited = index.search("web crawl", limit=1)
    check("search limit", len(results_limited) == 1, f"got {len(results_limited)}")

    results_empty = index.search("", limit=10)
    check("empty query", len(results_empty) == 0)

    # === Test 5: Index Persistence ===
    print("\n[6] Index persistence...")
    index_path = "/tmp/test_index.json"
    index.save(index_path)
    file_size = os.path.getsize(index_path)
    print(f"    Index file: {file_size} bytes")
    check("index file exists", os.path.exists(index_path))
    check("index file non-empty", file_size > 0)

    loaded_index = InvertedIndex.load(index_path)
    check("loaded doc count", loaded_index.doc_count == index.doc_count)
    check("loaded term count", len(loaded_index.index) == len(index.index))

    results2 = loaded_index.search("search engine", limit=5)
    check("loaded index search", len(results2) > 0)

    # === Test 6: REST API Handler (unit test without server) ===
    print("\n[7] REST API handler...")
    from http.server import HTTPServer
    import io

    # Set up handler class variables
    SearchAPIHandler.index = loaded_index
    SearchAPIHandler.crawl_manager = cm
    SearchAPIHandler.seeds = seeds
    SearchAPIHandler.crawl_duration = 2.5

    # We can't easily unit test the handler without a real request,
    # but we can verify search.html exists
    html = generate_search_html()
    check("search.html generation", len(html) > 1000)
    check("search.html has search box", 'input type="text"' in html.lower() or "queryInput" in html)
    check("search.html has fetch API", "fetch(" in html)
    check("search.html has bold tags", "<b>" in html)

    # Write search.html to disk
    html_path = "/tmp/search.html"
    with open(html_path, "w") as f:
        f.write(html)
    check("search.html written", os.path.exists(html_path))

    # === Test 7: Robots.txt parsing ===
    print("\n[8] Robots.txt parsing...")
    from robots import RobotsChecker
    rc = RobotsChecker(timeout=5.0)
    rules = rc.fetch_robots(f"127.0.0.1:{TEST_PORT}")
    check("robots.txt fetched", rules["fetched"])
    check("crawl delay", rules["crawl_delay"] == 0.5, f"got {rules['crawl_delay']}")
    check("disallow rules", len(rules["disallow"]) > 0)
    check("allowed path", rc.is_allowed(f"{BASE_URL}/page1"))
    check("disallowed path", not rc.is_allowed(f"{BASE_URL}/private"))

    # === Test 8: Stemming & text processing ===
    print("\n[9] Stemming & text processing...")
    from indexer import simple_stem, tokenize, filter_stopwords, normalize_term

    check("stem running->run", simple_stem("running") == "run")
    check("stem jumps->jump", simple_stem("jumps") == "jump")
    check("stem making->make", simple_stem("making") == "make")
    check("stem stopped->stop", simple_stem("stopped") == "stop")
    check("stem swimming->swim", simple_stem("swimming") == "swim")

    tokens = tokenize("The Quick Brown Fox Jumps!")
    check("tokenize lowercase", all(t.islower() for t in tokens))
    check("tokenize no punct", "!" not in " ".join(tokens))

    filtered = filter_stopwords(tokenize("the quick brown fox jumps over the lazy dog"))
    check("stopword the removed", "the" not in filtered)
    check("stopword over removed", "over" not in filtered)
    check("content words kept", "quick" in filtered and "brown" in filtered)

    # === Test 9: URL deduplication ===
    print("\n[10] URL deduplication...")
    urls = list(index.documents.keys())
    check("unique URLs", len(urls) == len(set(urls)))
    print(f"    {len(urls)} unique URLs")

    # === Test 10: Error handling ===
    print("\n[11] Error handling...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/nonexistent")
        urllib.request.urlopen(req, timeout=5)
        check("404 detection", False, "should have raised HTTPError")
    except urllib.error.HTTPError as e:
        check("404 error code", e.code == 404)

    # Test malformed URL handling
    from fetcher import fetch_url
    result = fetch_url("http://invalid.domain.zzz/", timeout=2)
    check("invalid domain handled", not result.success, f"error: {result.error}")

    # Test non-HTML detection
    result_json = fetch_url(f"{BASE_URL}/not-html", timeout=5)
    check("non-HTML detected", not result_json.is_html or result_json.error != "")

    # === Test 11: Crawl job tracking ===
    print("\n[12] Crawl job tracking...")
    job_id = cm.create_job(seeds, 2, 10)
    check("job created", job_id.startswith("crawl_"))
    job = cm.get_job(job_id)
    check("job found", job is not None)
    check("job status", job.status == "pending")

    # === Summary ===
    server.shutdown()
    print("\n" + "=" * 70)
    print(f"  RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    print("=" * 70)
    
    if FAIL_COUNT == 0:
        print("  ALL TESTS PASSED!")
    else:
        print(f"  {FAIL_COUNT} TEST(S) FAILED!")
    
    return FAIL_COUNT == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
