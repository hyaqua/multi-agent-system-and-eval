"""Integration tests using only the standard library."""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8080"
TOKEN = "Bearer secret-token-123"


def req(method, path, body=None, raw_body=None, send_auth=True):
    """Make an HTTP request and return (status, headers, body_text).

    *body* is a Python object to JSON-encode and send.
    *raw_body* is bytes sent as-is (with Content-Type: application/json).
    """
    url = f"{BASE}{path}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    elif raw_body is not None:
        data = raw_body
    r = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    if send_auth:
        r.add_header("Authorization", TOKEN)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def check(name, want_status, method, path,
           body=None, raw_body=None, send_auth=True):
    print(f"\n=== {name} ===")
    s, h, b = req(method, path, body, raw_body, send_auth)
    print(f"  Status: {s}")
    ct = h.get("Content-Type", "N/A")
    print(f"  Content-Type: {ct}")
    try:
        parsed = json.loads(b) if b else None
        print(f"  Body: {json.dumps(parsed, indent=2)}")
    except json.JSONDecodeError:
        print(f"  Body (raw): {b}")
    if s == want_status:
        print(f"  ✅ PASS")
        return True
    else:
        print(f"  ❌ FAIL: expected {want_status}, got {s}")
        sys.exit(1)


# ---- Run ----
check("GET empty items",                   200, "GET",  "/items")
check("POST create Widget",                201, "POST", "/items",
      {"name": "Widget", "category": "tools", "price": 9.99})
check("POST create Book",                  201, "POST", "/items",
      {"name": "Book", "category": "books", "price": 14.99})
check("GET all items",                     200, "GET",  "/items")
check("GET item 1",                        200, "GET",  "/items/1")
check("PUT update item 1",                 200, "PUT",  "/items/1",
      {"name": "Premium Widget", "category": "tools", "price": 19.99})
check("GET filter category=tools",         200, "GET",  "/items?category=tools")
check("GET filter category=books",         200, "GET",  "/items?category=books")
check("DELETE item 2",                     204, "DELETE", "/items/2")
check("GET after delete (1 item left)",    200, "GET",  "/items")
check("GET missing item 99 → 404",         404, "GET",  "/items/99")
check("PUT missing item 99 → 404",         404, "PUT",  "/items/99", {"name": "X"})
check("DELETE missing 99 → 404",           404, "DELETE", "/items/99")
check("POST invalid JSON → 400",           400, "POST", "/items",
      raw_body=b"not json")
check("POST array not dict → 400",         400, "POST", "/items",
      body=[1, 2, 3])
check("GET /unknown → 404",                404, "GET",  "/unknown")
check("POST /items/1 → 405",               405, "POST", "/items/1", {"x": 1})
check("DELETE /items → 405",               405, "DELETE", "/items")
check("PUT /items → 405",                  405, "PUT",  "/items", {"x": 1})
check("No auth → 401",                     401, "GET",  "/items", send_auth=False)

print("\n" + "=" * 50)
print("All tests passed! ✅")
