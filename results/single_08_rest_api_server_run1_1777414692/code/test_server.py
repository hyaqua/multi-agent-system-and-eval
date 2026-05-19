#!/usr/bin/env python3
"""
Comprehensive test suite for the REST API server.

Starts the server in a background thread, runs all tests, then shuts down.
"""

import json
import sys
import time
import threading
import urllib.request
import urllib.error

HOST = "127.0.0.1"
PORT = 8080
BASE = f"http://{HOST}:{PORT}"
TOKEN = "secret-token-12345"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

passed = 0
failed = 0


def test(name: str):
    """Decorator-like wrapper that prints test results."""
    def decorator(fn):
        global passed, failed
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        return fn
    return decorator


def request(method: str, path: str, data=None, headers=None, expect_status: int = None):
    """Make an HTTP request and return (status, body_dict)."""
    url = BASE + path
    if headers is None:
        headers = {}
    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            raw = resp.read()
            if raw:
                body = json.loads(raw.decode("utf-8"))
            else:
                body = None
            if expect_status and status != expect_status:
                raise AssertionError(f"Expected status {expect_status}, got {status}: {body}")
            return status, body
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        if raw:
            body = json.loads(raw.decode("utf-8"))
        else:
            body = None
        if expect_status and status != expect_status:
            raise AssertionError(f"Expected status {expect_status}, got {status}: {body}")
        return status, body


# ---------------------------------------------------------------------------
# Start server in background
# ---------------------------------------------------------------------------

def start_server():
    from server import main
    main()

# Reset the data file before each test run
import os
DATA_FILE = "/tmp/items.json"
INITIAL_DATA = {
    "items": [
        {"id": "1", "name": "Widget", "category": "tools", "price": 9.99},
        {"id": "2", "name": "Gadget", "category": "electronics", "price": 24.99},
        {"id": "3", "name": "Thingamajig", "category": "tools", "price": 14.50},
    ],
    "next_id": 4,
}
with open(DATA_FILE, "w") as f:
    json.dump(INITIAL_DATA, f)
print(f"Reset data file: {DATA_FILE}")

print("Starting server in background thread...")
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(0.5)  # Give the server a moment to bind
print("Server started.\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@test("GET /items returns all items (200)")
def _():
    status, body = request("GET", "/items", headers=HEADERS, expect_status=200)
    assert isinstance(body, list), "Body should be a list"
    assert len(body) == 3, f"Expected 3 items, got {len(body)}"


@test("GET /items/1 returns single item (200)")
def _():
    status, body = request("GET", "/items/1", headers=HEADERS, expect_status=200)
    assert body["id"] == "1"
    assert body["name"] == "Widget"


@test("GET /items/999 returns 404 Not Found")
def _():
    status, body = request("GET", "/items/999", headers=HEADERS, expect_status=404)
    assert "error" in body


@test("POST /items creates item and returns 201")
def _():
    status, body = request("POST", "/items",
                           data={"name": "NewItem", "category": "test", "price": 5.0},
                           headers=HEADERS, expect_status=201)
    assert body["name"] == "NewItem"
    assert "id" in body


@test("PUT /items/1 updates item and returns 200")
def _():
    status, body = request("PUT", "/items/1",
                           data={"name": "UpdatedWidget", "category": "tools", "price": 11.99},
                           headers=HEADERS, expect_status=200)
    assert body["name"] == "UpdatedWidget"
    assert body["id"] == "1"


@test("PUT /items/999 returns 404 Not Found")
def _():
    status, body = request("PUT", "/items/999",
                           data={"name": "Ghost"},
                           headers=HEADERS, expect_status=404)
    assert "error" in body


@test("DELETE /items/2 returns 204 No Content")
def _():
    status, body = request("DELETE", "/items/2", headers=HEADERS, expect_status=204)
    assert body is None


@test("DELETE /items/999 returns 404 Not Found")
def _():
    status, body = request("DELETE", "/items/999", headers=HEADERS, expect_status=404)
    assert "error" in body


@test("Responses include Content-Type: application/json")
def _():
    url = BASE + "/items"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct, f"Wrong Content-Type: {ct}"


@test("Invalid JSON POST returns 400 Bad Request")
def _():
    url = BASE + "/items"
    bad_json = b'{"name": "oops", invalid}'
    req = urllib.request.Request(url, data=bad_json, headers=HEADERS, method="POST")
    try:
        urllib.request.urlopen(req)
        assert False, "Should have raised HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        body = json.loads(e.read().decode("utf-8"))
        assert "error" in body


@test("Empty body POST returns 400 Bad Request")
def _():
    status, body = request("POST", "/items", data=None, headers=HEADERS, expect_status=400)


@test("Unsupported route returns 404 Not Found")
def _():
    status, body = request("GET", "/nonexistent", headers=HEADERS, expect_status=404)


@test("Unsupported method returns 405 Method Not Allowed")
def _():
    status, body = request("PATCH", "/items", headers=HEADERS, expect_status=405)
    assert "allowed_methods" in body
    assert "GET" in body["allowed_methods"]
    assert "POST" in body["allowed_methods"]


@test("Missing auth token returns 401 Unauthorized")
def _():
    status, body = request("GET", "/items", headers={}, expect_status=401)
    assert "error" in body


@test("Invalid auth token returns 401 Unauthorized")
def _():
    bad_headers = {"Authorization": "Bearer wrong-token"}
    status, body = request("GET", "/items", headers=bad_headers, expect_status=401)


@test("GET /items?category=tools filters by category field")
def _():
    status, body = request("GET", "/items?category=tools", headers=HEADERS, expect_status=200)
    assert isinstance(body, list)
    for item in body:
        assert item.get("category") == "tools", f"Item {item['id']} has category {item.get('category')}"


@test("GET /items?name=Gadget filters by name field (after delete may be empty)")
def _():
    status, body = request("GET", "/items?name=Gadget", headers=HEADERS, expect_status=200)
    # Gadget was deleted, so list should be empty
    assert isinstance(body, list)
    assert len(body) == 0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
    sys.exit(0)
