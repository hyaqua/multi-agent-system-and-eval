#!/usr/bin/env python3
"""Test script for the REST API server."""
import http.client
import json
import sys

BASE = "localhost:8899"
TOKEN = "my-secret-token"


def req(method, path, body=None, token=TOKEN):
    conn = http.client.HTTPConnection("localhost", 8899, timeout=5)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body_bytes = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        if isinstance(body, str):
            body_bytes = body.encode()
        else:
            body_bytes = json.dumps(body).encode()
    conn.request(method, path, body=body_bytes, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode()
    conn.close()
    return resp.status, resp.getheaders(), data


passed = 0
failed = 0


def check(test_name, status, expected_status, data, condition=None):
    global passed, failed
    ok = True
    if status != expected_status:
        print(f"FAIL [{test_name}]: expected status {expected_status}, got {status}")
        ok = False
    if condition is not None and not condition:
        print(f"FAIL [{test_name}]: condition not met. data={data}")
        ok = False
    if ok:
        print(f"PASS [{test_name}]: status={status}")
        passed += 1
    else:
        failed += 1


# Test 1: No auth -> 401
s, h, d = req("GET", "/items", token=None)
check("no auth GET /items", s, 401, d)

# Test 2: Auth GET /items -> 200 []
s, h, d = req("GET", "/items")
check("auth GET /items", s, 200, d, condition=(d == "[]"))

# Test 3: POST /items -> 201
s, h, d = req("POST", "/items", body={"name": "Test Item", "category": "books"})
item = json.loads(d) if s == 201 else {}
item_id = item.get("id", "")
check("POST /items", s, 201, d)

# Test 4: GET /items/{id} -> 200
s, h, d = req("GET", f"/items/{item_id}")
check("GET /items/{id}", s, 200, d)

# Test 5: GET /items/{id} not found -> 404
s, h, d = req("GET", "/items/nonexistent-id")
check("GET nonexistent id", s, 404, d)

# Test 6: PUT /items/{id} -> 200
s, h, d = req("PUT", f"/items/{item_id}", body={"name": "Updated Item", "category": "electronics"})
check("PUT /items/{id}", s, 200, d, condition=("Updated Item" in d))

# Test 7: PUT nonexistent -> 404
s, h, d = req("PUT", "/items/nonexistent-id", body={"name": "Nope"})
check("PUT nonexistent", s, 404, d)

# Test 8: Filter query
s, h, d = req("GET", "/items?category=electronics")
items = json.loads(d) if s == 200 else []
check("filter category=electronics", s, 200, d,
      condition=(len(items) == 1 and items[0]["id"] == item_id))

# Test 9: DELETE /items/{id} -> 204
s, h, d = req("DELETE", f"/items/{item_id}")
check("DELETE /items/{id}", s, 204, d, condition=(d == ""))

# Test 10: DELETE nonexistent -> 404
s, h, d = req("DELETE", "/items/nonexistent-id")
check("DELETE nonexistent", s, 404, d)

# Test 11: GET collection empty after delete
s, h, d = req("GET", "/items")
check("GET /items after delete", s, 200, d, condition=(d == "[]"))

# Test 12: Invalid JSON -> 400
conn = http.client.HTTPConnection("localhost", 8899, timeout=5)
conn.request("POST", "/items", body=b"not-valid-json", headers={
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
})
resp = conn.getresponse()
d = resp.read().decode()
conn.close()
check("invalid JSON POST", resp.status, 400, d)

# Test 13: 405 on POST /items/{id}
s, h, d = req("POST", "/items/some-id", body={})
check("POST /items/{id} -> 405", s, 405, d)

# Also 405 on PUT /items
s, h, d = req("PUT", "/items", body={})
check("PUT /items -> 405", s, 405, d)

# Also 405 on DELETE /items
s, h, d = req("DELETE", "/items")
check("DELETE /items -> 405", s, 405, d)

# Test 14: 404 on unknown route
s, h, d = req("GET", "/unknown")
check("GET /unknown -> 404", s, 404, d)

# Test 15: Wrong token -> 401
s, h, d = req("GET", "/items", token="wrong-token")
check("wrong token -> 401", s, 401, d)

# Test 16: Content-Type header check
s, h, d = req("GET", "/items")
content_type = dict(h).get("Content-Type", "")
check("Content-Type is json", s, 200, d,
      condition=("application/json" in content_type))

# Test 17: Concurrent request test (basic)
import threading
errors = []
def make_request():
    try:
        s2, h2, d2 = req("GET", "/items")
        if s2 != 200:
            errors.append(f"concurrent GET failed: {s2}")
    except Exception as e:
        errors.append(f"concurrent exception: {e}")

threads = [threading.Thread(target=make_request) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
if errors:
    print(f"FAIL [concurrent requests]: {errors}")
    failed += 1
else:
    print("PASS [concurrent requests]: all 10 threads got 200")
    passed += 1

print()
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed:
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
