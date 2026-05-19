## Revised Implementation Plan

### 1. File Structure  
*(Restructured to avoid ModuleNotFoundError when running directly)*

```
rest_api_server/            # project root (directory)
├── server.py               # Entry point – can be run as `python server.py` from this folder
├── handler.py              # HTTP request handler (subclass of BaseHTTPRequestHandler)
├── router.py               # Route matcher mapping (method, path_pattern) to callables
├── auth.py                 # Token validation logic
└── storage.py              # Thread‑safe item collection with JSON file persistence
```

All modules reside in the **same directory**. No sub‑package is used. Server starts by executing `python server.py` inside the project folder. Imports between modules use simple absolute imports, e.g., `import handler`, `from storage import Storage`, etc. The current working directory ensures modules are found.

---

### 2. Architecture

**Modules and Interactions**

- **server.py**  
  Creates a `http.server.ThreadingHTTPServer` passing a custom handler factory. It reads a configurable port via `argparse` (default `8000`), configures logging, instantiates a shared `storage.Storage` object, and passes it to the handler class via a class attribute (e.g., `handler.storage`) or by storing it in the handler’s `server` attribute. When running as `python server.py`, all local imports work because the current directory is in `sys.path`.

- **handler.py**  
  Defines `RequestHandler(BaseHTTPRequestHandler)`. Each `do_GET`, `do_POST`, `do_PUT`, `do_DELETE` follows the same pattern:
  1. Parse URL and query string with `urllib.parse.urlparse`, `parse_qs`.
  2. Perform authentication by calling `auth.validate(self.headers.get('Authorization'))`.
  3. Ask the `Router` object to resolve the (method, path) to a callable and path parameters.
  4. Call the route handler, catching invalid JSON (→ 400), missing items (→ 404), etc.
  5. Set status code, `Content‑Type: application/json` (except 204), and send JSON body.
  6. Log `method`, `path`, `status` via `logging.info`.

- **router.py**  
  The `Router` class provides `add_route(method, path_regex, handler_func)`. It stores a list of `(method, compiled_regex, handler)`. The `match(method, path)` method iterates and returns `(handler, path_kwargs)` on the first match, otherwise `(None, None)`. Path regexes use named groups for dynamic segments (e.g., `r'/items/(?P<id>\d+)$'`). For `/items` with optional trailing slash, match both.

- **auth.py**  
  Contains `validate(auth_header: str) -> bool`. It checks if the header equals `"Bearer secret-token"` (hard‑coded, or read from environment variable `API_TOKEN`). Returns `True`/`False`.

- **storage.py**  
  `Storage` class manages an in‑memory list of item dictionaries and persists to a JSON file.  
  - **Thread safety** – A single **`threading.RLock`** (re‑entrant lock) protects **all** access to `self._items` and the file. Every public method (`get_all`, `get_by_id`, `add`, `update`, `delete`, `filter_by_field`) acquires the lock **before** any read or write and releases it afterwards. This ensures mutual exclusion for both read‑only and mutating operations, preventing race conditions and reads of inconsistent state.
    - The lock is re‑entrant because the methods internally call `_save()`, which itself must acquire the lock to safely write the file. Using `RLock` allows a method that already holds the lock to call `_save()` without deadlocking.
    - The lock context is acquired once at the beginning of each public method using `with self._lock:` and spans the entire operation (including the call to `_save()` for write methods).
  - **Persistence** – On init, if the JSON file exists it is loaded into `self._items` **under the lock**; otherwise `self._items = []`. After every `add`, `update`, `delete`, the list is written back inside the same lock held by the method.
  - **Auto‑increment ID** – The storage keeps a `_next_id` integer (initialised to 1, or last max id+1 on load). New items get an `id` from this counter, which is also protected by the lock.

---

### 3. Implementation Order

1. **`storage.py`** – Implement thread‑safe storage using `threading.RLock()`. Write `_save()` and all public methods (`get_all`, `get_by_id`, `add`, `update`, `delete`, `filter_by_field`) with `with self._lock:` wrapping the entire method body. Test concurrent access locally to verify lock is always held.
2. **`auth.py`** – Hard‑coded token validation (optionally env).  
3. **`router.py`** – Regex‑based router with method and path support, returning handler and kwargs.  
4. **`handler.py`** – Skeleton `do_*` methods that dispatch to router and return 501 placeholder, after auth check.  
5. **`server.py`** – Set up `ThreadingHTTPServer`, wire handler to use shared storage and router, parse port.  
6. **Fill `handler.py`** – Implement each CRUD endpoint, full auth, error handling (400, 404, 405).  
7. **Add query filtering** – In `do_GET /items`, parse query string and call `storage.filter_by_field`.  
8. **Testing and refinement** – Verify status codes, headers, threading under concurrent requests. Ensure empty JSON objects are accepted.

---

### 4. Libraries / Requirements

- **Standard library only**: `http.server`, `threading`, `json`, `pathlib`, `logging`, `urllib.parse`, `re`, `argparse`, `os`.  
- No external dependencies. Python 3.7+ sufficient (ThreadingHTTPServer available).  
- The project runs directly with `python server.py` from its directory, no `-m` switch needed.

---

### 5. Feature Implementation Details

| Feature | How It Is Implemented |
|---------|-----------------------|
| **Configurable port** | `server.py` uses `argparse` for `--port` (default 8000). |
| **Logging incoming requests** | `handler.py` logs `method`, `path`, `status` using `logging.info`. |
| **GET /items** | Router `(GET, r'/items/?$')` → view calls `storage.get_all()` – which **acquires the lock**, returns a copy of the list, then releases the lock. Returns 200 + JSON array. |
| **GET /items/{id}** | Router regex `r'/items/(?P<id>\d+)/?$'` → view calls `storage.get_by_id(int(id))` under lock. 200 + JSON if found, else 404 `{"error": "Not found"}`. |
| **POST /items** | Route `(POST, '/items/?$')`. Read body, `json.loads` (catch `JSONDecodeError` → 400 `{"error": "Invalid JSON"}`). **Validate that the parsed value is a dict.** `if not isinstance(body, dict):` → 400. **An empty dictionary `{}` is allowed** – no additional empty‑body check (i.e., do **not** use `if not body:`). Call `storage.add(item)` which acquires the lock, auto‑increments id, appends to list, calls `_save()` (still under the same lock), and releases. Return 201 with created item and `Location` header. |
| **PUT /items/{id}** | Same regex. Read body, parse JSON. **Validate it is a dict** (emptiness allowed). Call `storage.update(int(id), data)`: **lock** is acquired, item located by id, fields merged (preserving id), `_save()`, lock released. Returns 200 + updated dict if existed, else 404. |
| **DELETE /items/{id}** | Route `(DELETE, '/items/{id}')`. `storage.delete(id)` **acquires lock**, removes item if found, calls `_save()`, releases lock. Returns 204 with no body if successful, else 404. |
| **Content‑Type header** | Every response that has a body sets `Content-Type: application/json`. 204 responses omit this header. |
| **Invalid JSON → 400** | Try/except block around `json.loads`. On failure, send 400 `{"error": "Invalid JSON"}`. |
| **Unsupported routes → 404** | Router returns no match → handler sends 404 `{"error": "Not found"}`. |
| **Unsupported methods → 405** | If a path matches a known pattern but the HTTP method is not registered for that path, the router can return a special sentinel or the handler checks method against a list of allowed methods and returns 405 with `Allow` header. Implementation: after path matching, if handler is `None` but the path pattern existed, set status 405. A small mapping in handler from path regex to allowed verbs enables this. |
| **Token authentication → 401** | In every `do_*` method, before anything else, call `auth.validate(self.headers.get('Authorization'))`. If invalid, send 401 `{"error": "Unauthorized"}` and return. |
| **JSON file persistence** | `storage.Storage.__init__` loads from file under lock. `_save()` uses `json.dump` with indent, always called inside a lock held by the calling public method (using RLock to allow re‑entry). |
| **Query parameter filtering** | `GET /items?field=value&...` uses `urllib.parse.parse_qs`. `storage.filter_by_field(query_dict)` **acquires the lock**, iterates `self._items` under protection, and returns matching items. Supports any field, simple equality. |
| **Concurrent request handling** | Server is `http.server.ThreadingHTTPServer` – each request runs in a separate thread. All access to the item list and file is serialized by a single `threading.RLock`. Every public storage method acquires the lock for its entire duration, ensuring reads cannot see intermediate writes, and writes are atomic. The lock is re‑entrant so that `_save()` can be safely called from within a method that already holds it. This guarantees thread safety and prevents crashes or data corruption under concurrent access. |

**Correction from Review Feedback**  
- Removed the `or not body` condition from the JSON body validation in POST and PUT handlers. The only required check is `if not isinstance(body, dict)`, which accepts empty dictionaries `{}` as valid inputs. This allows creation/update of an item with no extra fields (just an id). The storage layer already handles empty dicts correctly.

**Additional Notes**  
- The `id` field is an integer, added automatically by `storage.add`. Clients should not supply `id` in POST/PUT bodies; if they do, it’s ignored (or overwritten).  
- Query filtering applies only to `GET /items`; `GET /items/{id}` ignores query strings.  
- Error responses always contain a JSON body with an `"error"` key and appropriate `Content-Type`.  
- The server binds to `0.0.0.0` (all interfaces) unless overridden.  
- The storage lock is released **after** the JSON file is fully written, so no two operations can interleave and leave the file in an inconsistent state.