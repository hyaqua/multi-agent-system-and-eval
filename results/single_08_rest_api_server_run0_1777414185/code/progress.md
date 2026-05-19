STATUS: COMPLETE

## REST API Server – Progress Report

### Architecture

Three modules, all using only the Python standard library:

| File | Purpose |
|---|---|
| `server.py` | CLI entry point, `ThreadingMixIn`-based HTTP server, argument parsing |
| `handlers.py` | `BaseHTTPRequestHandler` subclass — routing, auth, JSON serialisation, HTTP status codes |
| `store.py` | Thread-safe JSON file data store with CRUD operations |

### Features Implemented & Verified

1. **Configurable port** — `--port`, `--host`, `--data-file`, `--token` CLI arguments
2. **Request logging** — every request logged via Python's `logging` module with timestamp, client IP, method, path, and status
3. **GET /items** — returns JSON array of all items (200)
4. **GET /items/{id}** — returns single item (200) or `{"error": "Item not found"}` (404)
5. **POST /items** — creates item from JSON body, returns 201 with the created item (including generated UUID if no `id` supplied)
6. **PUT /items/{id}** — updates existing item, returns 200 with updated item, or 404; the `id` field is protected from overwrite
7. **DELETE /items/{id}** — deletes item, returns 204 No Content, or 404
8. **Content-Type: application/json** — set on every response including errors and 204
9. **Invalid JSON → 400** — syntactically broken JSON returns `{"error": "Invalid JSON in request body"}`; valid JSON that is not an object returns `{"error": "Request body must be a JSON object"}` (also 400)
10. **Unsupported routes → 404** — e.g. `/nonexistent`, `/items/too/many/segments`
11. **Unsupported methods → 405** — e.g. `POST /items/{id}`, `PUT /items`, `DELETE /items`, `PATCH /items/…`
12. **Bearer token auth → 401** — every endpoint checks the `Authorization: Bearer <token>` header; missing or wrong token returns `{"error": "Unauthorized …"}` (401)
13. **JSON file persistence** — items survive server restarts; data file is auto-created on first run
14. **Query parameter filtering** — `GET /items?category=books` and multi-field `GET /items?category=books&name=first` both work; comparisons are string-based so `?price=10` matches `"price": 10`
15. **Concurrent requests (threading)** — `ThreadingMixIn` spawns one thread per request; tested with 20 parallel GETs, all succeeded

### Test Results

A 58-check test suite was run against the live server. **All checks passed** covering:

- Auth (missing token, wrong token, valid token)
- CRUD lifecycle (create → read → update → delete)
- Query filtering (single field, multi field, non-matching)
- Error handling (400, 401, 404, 405)
- Content-Type header verification
- PATCH/HEAD/OPTIONS on valid and invalid routes
- 20-thread concurrency smoke test
- Data file persistence across server restart

### How to Run

```bash
python server.py --port 8080 --host 127.0.0.1 --data-file items.json --token my-secret
```

Then:

```bash
curl -H "Authorization: Bearer my-secret" http://127.0.0.1:8080/items
```
