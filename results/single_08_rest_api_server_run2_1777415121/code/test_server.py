#!/usr/bin/env python3
"""
Comprehensive test suite for the REST API server.

Tests every required feature:
1. Configurable port & request logging
2. GET /items                → JSON array
3. GET /items/{id}           → single item / 404
4. POST /items               → 201 with created item
5. PUT /items/{id}           → updated item / 404
6. DELETE /items/{id}        → 204 / 404
7. Content-Type: application/json
8. Invalid JSON → 400
9. Unsupported routes → 404
10. Unsupported methods → 405
11. Bearer token auth → 401
12. JSON file persistence
13. GET /items?field=value filtering
14. Concurrent requests (threading)
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import http.client
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration for tests
# ---------------------------------------------------------------------------
PORT = 18765                         # use an uncommon port for tests
DATA_FILE = "/tmp/test_items.json"
AUTH_TOKEN = "test-secret-token"
BASE_URL = f"http://127.0.0.1:{PORT}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class TestFailure(Exception):
    pass

def _req(method: str, path: str, body: dict | None = None,
         token: str | None = AUTH_TOKEN,
         expect_status: int | None = None) -> tuple[int, dict | None, dict]:
    """Make an HTTP request.  Returns (status, json_body, headers)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        resp = urllib.request.urlopen(req, timeout=5)
        status = resp.status
        raw = resp.read()
        headers = dict(resp.headers)
        if raw:
            parsed = json.loads(raw.decode("utf-8"))
        else:
            parsed = None
        if expect_status is not None and status != expect_status:
            raise TestFailure(
                f"{method} {path}: expected status {expect_status}, got {status}")
        return status, parsed, headers
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        headers = dict(e.headers)
        if raw:
            parsed = json.loads(raw.decode("utf-8"))
        else:
            parsed = None
        if expect_status is not None and status != expect_status:
            raise TestFailure(
                f"{method} {path}: expected status {expect_status}, got {status}  body={parsed}")
        return status, parsed, headers
    except Exception as e:
        raise TestFailure(f"{method} {path}: request failed: {e}")


def assert_status(status: int, expected: int, context: str = ""):
    if status != expected:
        raise TestFailure(f"{context}: expected {expected}, got {status}")


def assert_eq(a, b, context: str = ""):
    if a != b:
        raise TestFailure(f"{context}: expected {b!r}, got {a!r}")


def assert_in(key, d, context: str = ""):
    if key not in d:
        raise TestFailure(f"{context}: expected key {key!r} in {d}")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_no_auth_returns_401():
    """Requests without a valid token must get 401."""
    for method, path in [("GET", "/items"), ("POST", "/items"),
                          ("GET", "/items/1"), ("PUT", "/items/1"),
                          ("DELETE", "/items/1")]:
        status, body, _ = _req(method, path, token=None)
        assert_status(status, 401, f"{method} {path} without token")
        assert_in("error", body, f"{method} {path} error body")


def test_wrong_token_returns_401():
    status, body, _ = _req("GET", "/items", token="wrong-token")
    assert_status(status, 401)


def test_get_items_empty():
    """GET /items on fresh server returns []"""
    status, body, hdrs = _req("GET", "/items")
    assert_status(status, 200)
    assert_eq(body, [])
    assert_eq(hdrs.get("Content-Type"), "application/json")


def test_create_item():
    """POST /items creates an item and returns 201"""
    status, body, hdrs = _req("POST", "/items",
                              body={"name": "apple", "category": "fruit"})
    assert_status(status, 201)
    assert_in("id", body)
    assert_eq(body["name"], "apple")
    assert_eq(body["category"], "fruit")
    assert_eq(hdrs.get("Content-Type"), "application/json")
    return body["id"]


def test_get_all_items():
    """GET /items returns all created items"""
    status, body, _ = _req("GET", "/items")
    assert_status(status, 200)
    assert isinstance(body, list)
    assert len(body) >= 1


def test_get_single_item(item_id: str):
    """GET /items/{id} returns the correct item"""
    status, body, _ = _req("GET", f"/items/{item_id}")
    assert_status(status, 200)
    assert_eq(body["id"], item_id)


def test_get_nonexistent_returns_404():
    """GET /items/nonexistent → 404"""
    status, body, _ = _req("GET", "/items/99999")
    assert_status(status, 404)
    assert_in("error", body)


def test_update_item(item_id: str):
    """PUT /items/{id} updates and returns the item"""
    status, body, _ = _req("PUT", f"/items/{item_id}",
                           body={"name": "green apple", "category": "fruit"})
    assert_status(status, 200)
    assert_eq(body["id"], item_id)
    assert_eq(body["name"], "green apple")

    # Verify GET also reflects change
    _, get_body, _ = _req("GET", f"/items/{item_id}")
    assert_eq(get_body["name"], "green apple")


def test_update_nonexistent_returns_404():
    """PUT /items/99999 → 404"""
    status, body, _ = _req("PUT", "/items/99999", body={"name": "x"})
    assert_status(status, 404)
    assert_in("error", body)


def test_delete_item(item_id: str):
    """DELETE /items/{id} → 204, then GET → 404"""
    status, body, hdrs = _req("DELETE", f"/items/{item_id}")
    assert_status(status, 204)
    assert body is None
    assert_eq(hdrs.get("Content-Type"), "application/json")

    # Confirm gone
    status2, body2, _ = _req("GET", f"/items/{item_id}")
    assert_status(status2, 404)


def test_delete_nonexistent_returns_404():
    """DELETE /items/99999 → 404"""
    status, body, _ = _req("DELETE", "/items/99999")
    assert_status(status, 404)


def test_invalid_json_returns_400():
    """Malformed JSON body → 400"""
    url = f"{BASE_URL}/items"
    data = b"this is not json"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as e:
        assert_status(e.code, 400)
        body = json.loads(e.read().decode("utf-8"))
        assert_in("error", body)
    else:
        raise TestFailure("Expected 400 for invalid JSON")

    # Also test JSON array (not a dict)
    data2 = json.dumps([1, 2, 3]).encode("utf-8")
    req2 = urllib.request.Request(url, data=data2, method="POST")
    req2.add_header("Content-Type", "application/json")
    req2.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    try:
        urllib.request.urlopen(req2, timeout=5)
    except urllib.error.HTTPError as e:
        assert_status(e.code, 400, "JSON array body")
        body = json.loads(e.read().decode("utf-8"))
        assert_in("error", body)
    else:
        raise TestFailure("Expected 400 for JSON array body")


def test_unsupported_route_returns_404():
    """Requests to unknown paths → 404"""
    for path in ["/", "/foo", "/api/items", "/items/1/extra"]:
        status, body, _ = _req("GET", path)
        assert_status(status, 404, f"GET {path}")
        assert_in("error", body)


def test_unsupported_method_returns_405():
    """Valid paths with wrong method → 405"""
    # PUT /items (no id) should be 405
    status, body, _ = _req("PUT", "/items", body={"name": "x"})
    assert_status(status, 405)

    # DELETE /items (no id) should be 405
    status, body, _ = _req("DELETE", "/items")
    assert_status(status, 405)

    # POST /items/1 should be 405
    status, body, _ = _req("POST", "/items/1", body={"name": "x"})
    assert_status(status, 405)

    # PATCH anywhere
    status, body, _ = _req("PATCH", "/items/1", body={"name": "x"})
    assert_status(status, 405)

    # HEAD /items (we return 405 for HEAD)
    # Actually we can't easily test HEAD with urllib - skip or use http.client
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    conn.request("HEAD", "/items", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    resp = conn.getresponse()
    resp.read()  # consume
    assert_status(resp.status, 405, "HEAD /items")
    conn.close()


def test_filtering():
    """GET /items?category=fruit returns only matching items"""
    # Create two items with different categories
    _req("POST", "/items", body={"name": "banana", "category": "fruit"})
    _req("POST", "/items", body={"name": "carrot", "category": "vegetable"})

    # Filter by category
    status, body, _ = _req("GET", "/items?category=fruit")
    assert_status(status, 200)
    assert all(it["category"] == "fruit" for it in body), f"Filter mismatch: {body}"
    assert len(body) >= 1

    # Filter by name
    status, body, _ = _req("GET", "/items?name=carrot")
    assert_status(status, 200)
    assert len(body) == 1
    assert_eq(body[0]["name"], "carrot")

    # Filter with no matches
    status, body, _ = _req("GET", "/items?category=nonexistent")
    assert_status(status, 200)
    assert_eq(body, [])


def test_content_type_header():
    """All responses must include Content-Type: application/json"""
    paths_and_methods = [
        ("GET", "/items"),
        ("POST", "/items"),
        ("GET", "/items/1"),
        ("PUT", "/items/1"),
    ]
    for method, path in paths_and_methods:
        status, _, hdrs = _req(method, path,
                               body={"name": "test"} if method in ("POST", "PUT") else None)
        assert_eq(hdrs.get("Content-Type"), "application/json",
                  f"{method} {path} Content-Type")


def test_concurrent_requests():
    """Server handles concurrent requests without crashing."""
    errors = []
    def worker(worker_id: int):
        try:
            for i in range(5):
                _req("GET", "/items", expect_status=200)
                _req("POST", "/items", body={"worker": worker_id, "seq": i},
                     expect_status=201)
        except Exception as e:
            errors.append(f"worker {worker_id}: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    if errors:
        raise TestFailure(f"Concurrent test errors: {errors}")
    print(f"  ✓ {len(threads)} threads each made 10 requests without errors")


def test_persistence():
    """Data survives a server restart (store reload)."""
    # We can't easily restart the server in the same process.
    # Instead, verify the file exists and contains valid data.
    assert os.path.exists(DATA_FILE), "Data file should exist"
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    assert "items" in data
    assert "_next_id" in data
    assert isinstance(data["items"], dict)
    print(f"  ✓ Data file exists with {len(data['items'])} items")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def main():
    # Clean up any stale data file
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)

    # Import and start the server in a background thread
    import server as server_module
    # Override config for tests
    server_module.PORT = PORT
    server_module.DATA_FILE = DATA_FILE
    server_module.AUTH_TOKEN = AUTH_TOKEN

    store = server_module.ItemStore(DATA_FILE)
    server_module.RequestHandler.store = store
    httpd = server_module.ThreadedHTTPServer(("127.0.0.1", PORT),
                                              server_module.RequestHandler)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)  # let the server boot

    print("=" * 60)
    print("REST API Server — Feature Test Suite")
    print("=" * 60)

    all_pass = True
    tests = [
        ("No auth → 401", test_no_auth_returns_401),
        ("Wrong token → 401", test_wrong_token_returns_401),
        ("GET /items empty", test_get_items_empty),
        ("Content-Type header", test_content_type_header),
        ("POST /items (create)", test_create_item),
        ("GET all items", test_get_all_items),
        ("GET single item", lambda: test_get_single_item("1")),
        ("GET nonexistent → 404", test_get_nonexistent_returns_404),
        ("PUT update item", lambda: test_update_item("1")),
        ("PUT nonexistent → 404", test_update_nonexistent_returns_404),
        ("DELETE item → 204", lambda: test_delete_item("1")),
        ("DELETE nonexistent → 404", test_delete_nonexistent_returns_404),
        ("Invalid JSON → 400", test_invalid_json_returns_400),
        ("Unsupported route → 404", test_unsupported_route_returns_404),
        ("Unsupported method → 405", test_unsupported_method_returns_405),
        ("Filtering", test_filtering),
        ("Concurrent requests", test_concurrent_requests),
        ("Persistence", test_persistence),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
        except TestFailure as e:
            print(f"  ✗ {name}  —  {e}")
            all_pass = False
        except Exception as e:
            print(f"  ✗ {name}  —  UNEXPECTED: {e}")
            all_pass = False

    # Shut down
    httpd.shutdown()
    httpd.server_close()

    # Cleanup
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)

    print("=" * 60)
    if all_pass:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
