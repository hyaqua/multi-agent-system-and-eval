STATUS: COMPLETE

## REST API Server — Progress Report

All 14 required features are implemented and verified via automated tests.

### Implemented Features

1. **Configurable port & request logging** — Server binds to `HOST:PORT` (env vars, default 0.0.0.0:8080). Every request is logged with timestamp, client IP, method, path, and status code.

2. **GET /items** — Returns a JSON array of all items. Verified: status 200, `Content-Type: application/json`, empty `[]` on fresh server.

3. **GET /items/{id}** — Returns a single item by its string ID. Returns 404 with `{"error": "..."}` when the ID doesn't exist.

4. **POST /items** — Creates a new item from a JSON request body. Auto-generates an `"id"` field. Returns 201 with the created item.

5. **PUT /items/{id}** — Replaces an existing item. Body must be a JSON object. Returns the updated item (200) or 404.

6. **DELETE /items/{id}** — Deletes an item. Returns 204 No Content (no body) on success, 404 if not found. Subsequent GET confirms removal.

7. **Content-Type header** — All responses (200, 201, 400, 401, 404, 405) include `Content-Type: application/json`.

8. **Invalid JSON → 400** — Malformed syntax and non-object JSON (arrays, strings, numbers) all return 400 with `{"error": "Invalid JSON in request body"}`.

9. **Unsupported routes → 404** — Unknown paths (`/`, `/foo`, `/api/items`, `/items/1/extra`) return 404.

10. **Unsupported methods → 405** — `PUT /items`, `DELETE /items`, `POST /items/{id}`, `PATCH`, `HEAD`, `OPTIONS` all return 405.

11. **Bearer token authentication** — Every endpoint checks the `Authorization: Bearer <token>` header. Missing or wrong token returns 401 `{"error": "Unauthorized"}`.

12. **JSON file persistence** — Items stored in a JSON file (default `/tmp/items.json`, configurable via `DATA_FILE` env var). Survives restarts: data is loaded on startup and saved after every mutation.

13. **Query-parameter filtering** — `GET /items?category=books&author=alice` returns only items matching all provided field values (exact string match).

14. **Threading** — `ThreadingMixIn` with `daemon_threads=True` handles concurrent requests. Tested with 10 threads × 10 requests each without errors.

### Files

| File | Purpose |
|------|---------|
| `server.py` | Main REST API server (single file, ~180 lines) |
| `test_server.py` | Automated test suite covering all 14 features |

### How to Run

```bash
# Default settings (port 8080, token "secret-token")
python server.py

# Custom settings
PORT=9000 AUTH_TOKEN="my-token" DATA_FILE="./data.json" python server.py

# Run tests
python test_server.py
```

### Test Results

```
============================================================
  ✓ No auth → 401
  ✓ Wrong token → 401
  ✓ GET /items empty
  ✓ Content-Type header
  ✓ POST /items (create)
  ✓ GET all items
  ✓ GET single item
  ✓ GET nonexistent → 404
  ✓ PUT update item
  ✓ PUT nonexistent → 404
  ✓ DELETE item → 204
  ✓ DELETE nonexistent → 404
  ✓ Invalid JSON → 400
  ✓ Unsupported route → 404
  ✓ Unsupported method → 405
  ✓ Filtering
  ✓ 10 threads each made 10 requests without errors
  ✓ Concurrent requests
  ✓ Data file exists with 53 items
  ✓ Persistence
============================================================
ALL TESTS PASSED
============================================================
```
