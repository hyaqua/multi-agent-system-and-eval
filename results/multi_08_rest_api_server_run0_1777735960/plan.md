```markdown
# Implementation Plan: Standard-Library REST API Server

## 1. Files to Create

| File | Purpose |
|---|---|
| `server.py` | Entry point; parses CLI args (port), loads or creates data file, starts HTTP server with threading. |
| `api_handler.py` | Contains `APIHandler(BaseHTTPRequestHandler)`: routing, request parsing, authentication, response formatting. |
| `data_store.py` | `DataStore` class: manages items in-memory (a dict), loads/saves to JSON file, provides CRUD methods. |
| `auth.py` | Simple token validation; a hardcoded token (or loaded from env) for basic auth. |
| `logger.py` | Basic request logger using `logging` module. |
| `items.json` | (auto-created) Persistent storage file. |

## 2. Architecture

- **`server.py`** initialises `DataStore` (loads `items.json`), creates an `HTTPServer` with a custom `ThreadingMixIn` subclass and the `APIHandler`.
- **`api_handler.py`** extends `BaseHTTPRequestHandler`. On each request:
  - Logs method, path, client.
  - Checks `Authorization` header via `auth.validate_token()`; returns 401 if invalid.
  - Parses the URL path to extract resource and optional ID. Determines allowed methods per route.
  - If method not allowed → 405.
  - For POST/PUT, reads and parses JSON body; returns 400 on malformed JSON.
  - Delegates to `DataStore` methods for CRUD.
  - Sets correct `Content-Type: application/json` and status code.
  - Handles query string for GET /items filtering.
- **`data_store.py`** holds items in a dict `{id: item_dict}`. On start, loads from JSON file; after each mutation (create, update, delete) writes the whole dict back. Auto-generates integer IDs.
- **`auth.py`** expects `Authorization: Bearer <token>` and compares against a configured token (default hardcoded, or loaded from environment variable `API_TOKEN`).
- **`logger.py`** configures `logging.basicConfig` with a format including timestamp and client address.

## 3. Implementation Order

1. `logger.py` – simple logging setup.
2. `auth.py` – token validation function.
3. `data_store.py` – `DataStore` class with `load()`, `save()`, `get_all()`, `get_by_id()`, `create(item)`, `update(id, item)`, `delete(id)`, and filtering by query params.
4. `api_handler.py` – request routing, authentication, JSON parsing, response helpers.
5. `server.py` – wire everything together: CLI port, threading mixin, start server.
6. Integration testing (manual, as no external test framework required).

## 4. Libraries Needed

- **Standard library only**:
  - `http.server` (for `HTTPServer`, `BaseHTTPRequestHandler`)
  - `socketserver` (for `ThreadingMixIn`)
  - `json`
  - `argparse` (configurable port)
  - `logging`
  - `os` (environment variable for token)
  - `urllib.parse` (for parsing query strings, URL paths)
  - `traceback` (optional, for error logging)

## 5. Detailed Implementation per Feature

### Configurable Port & Logging
- `server.py` uses `argparse` to accept `--port` (default 8000). Passes port to `HTTPServer` address.
- `APIHandler.log_message` overridden to use the project’s logger with client IP and request line.

### Routing and URL Parsing
- `APIHandler.do_GET/POST/PUT/DELETE` are implemented. Each extracts path via `urllib.parse.urlparse(self.path)`.
- Path split into parts: `["items"]` or `["items", "<id>"]`.
- If path does not match `/items` or `/items/<id>`, send 404.
- Method validation: `GET` and `POST` allowed on `/items`; `GET`, `PUT`, `DELETE` on `/items/<id>`. If method not in allowed set → 405 with `Allow` header.

### JSON Serialization & Content-Type
- All responses set `self.send_header("Content-Type", "application/json")` and include JSON body (except 204).
- Helper `_send_json(status_code, data)` that serializes `data` dict and sends response.
- `_send_error(status_code, message)` for non-2xx responses, sends `{"error": message}`.

### GET /items
- Call `self.store.get_all()` which returns a list of item dicts.
- Query parameter filtering: `urllib.parse.parse_qs` extracts query params; if present, filter items where each param matches (using `str` comparison). e.g., `?category=books` filters items with `category == "books"`.
- Return 200 with JSON array.

### GET /items/{id}
- Parse `id` from path; call `store.get_by_id(id)`. If `None`, return 404.
- Return 200 with JSON object.

### POST /items
- Read body: `content_length = int(self.headers.get('Content-Length', 0))` then `self.rfile.read(content_length)`.
- Attempt `json.loads()`. If `JSONDecodeError`, return 400 with error message.
- Validate that body is a JSON object (dict). If not, 400.
- Call `store.create(item)`. Returns created item with assigned ID.
- Return 201 with the created item.

### PUT /items/{id}
- Parse ID, read and validate JSON body same as POST.
- Ensure the resource exists: call `store.get_by_id(id)`. If not found, 404.
- Call `store.update(id, item)` which replaces the existing item.
- Return 200 with updated item.

### DELETE /items/{id}
- Call `store.delete(id)`. If item exists, it’s deleted; return 204 with no body.
- If not found, return 404.

### 400 Bad Request for Invalid JSON
- Wrapped in try/except around `json.loads`. On `json.JSONDecodeError`, respond 400 `{"error": "Invalid JSON"}`.

### 404 Not Found for Unsupported Routes
- In each `do_*` method, before routing, check path; if not matched, call `self._send_error(404, "Not Found")`.

### 405 Method Not Allowed
- Before routing, check if method is allowed for that route using a mapping. If not allowed, send 405 with `Allow` header listing permitted methods (e.g., `Allow: GET, POST`). Use `self._send_error(405, "Method Not Allowed")` and manually call `self.send_header("Allow", ...)` before sending.

### Token Authentication
- In `APIHandler`, override `do_GET`, etc., by first calling `self.authenticate()`.
- `authenticate` reads the `Authorization` header. If missing or not starting with `Bearer `, return 401.
- Extract token and call `auth.validate_token(token)`. If invalid, 401 with `WWW-Authenticate: Bearer` header and `{"error": "Unauthorized"}`.
- Token is checked for every request (even for 404 routes) to prevent information leakage.

### Persistent JSON File
- `DataStore.__init__(file_path)` loads `items.json` if exists; else initializes empty dict `{}` and next_id=1.
- `save()` writes entire dict to the file using `json.dump` with indent for readability.
- After `create`, `update`, `delete`, call `self.save()`.
- Ensure atomic writes by writing to a temp file and renaming (optional but recommended). Use `tempfile` and `os.replace`.

### Query Parameter Filtering on GET /items
- After fetching all items, if `self.path` contains query string, parse with `urllib.parse.parse_qs`. For each key/value pair, filter items where `str(item.get(key)) == str(value[0])`. Return filtered list.

### Concurrency via Threading
- `server.py` defines a class `ThreadedHTTPServer(ThreadingMixIn, HTPServer)`. This handles each request in a separate thread, preventing blocking. Python’s GIL still applies but I/O waits allow concurrency.
- `DataStore` methods are not inherently thread-safe; use `threading.Lock` in `DataStore` for all read/write operations to avoid data corruption under concurrent writes. Example: acquire lock before any mutation and when saving/loading. Use `with self.lock:`.

This plan provides all necessary details to implement the server using only Python’s standard library.
```