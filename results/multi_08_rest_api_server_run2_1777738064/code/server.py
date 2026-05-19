#!/usr/bin/env python3
"""
REST API Server - Simple HTTP API for managing items.

Uses only Python standard library modules.
Stores items in a JSON file. Supports CRUD operations, query filtering,
Bearer token authentication, and concurrent requests via threading.

Usage:
    python server.py [--port PORT] [--host HOST]
    Default: host=0.0.0.0, port=8000
"""

import argparse
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs


# ---------------------------------------------------------------------------
# Data Store
# ---------------------------------------------------------------------------

DEFAULT_ITEMS_FILE = "items.json"
DEFAULT_AUTH_TOKEN = "my-secret-token"


class ItemStore:
    """Thread-safe JSON-backed store for item records."""

    def __init__(self, filepath: str = DEFAULT_ITEMS_FILE):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load items from the JSON file; create an empty store if missing."""
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as fh:
                    self._items = json.load(fh)
                if not isinstance(self._items, list):
                    self._items = []
            except (json.JSONDecodeError, OSError):
                self._items = []
        else:
            self._items = []

    def _save(self) -> None:
        """Atomically save items to the JSON file."""
        tmp_path = self._filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(self._items, fh, indent=2)
        os.replace(tmp_path, self._filepath)  # atomic on POSIX; best-effort on Windows

    # ------------------------------------------------------------------
    # Public CRUD API (all methods acquire the lock)
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict]:
        """Return a shallow copy of all items."""
        with self._lock:
            return list(self._items)

    def get(self, item_id: str) -> dict | None:
        """Return a single item by ID, or None."""
        with self._lock:
            for item in self._items:
                if item.get("id") == item_id:
                    return dict(item)  # shallow copy
        return None

    def create(self, data: dict) -> dict:
        """Create a new item with a generated UUID. Returns the created item."""
        with self._lock:
            new_item = {"id": str(uuid.uuid4())}
            new_item.update(data)
            self._items.append(new_item)
            self._save()
            return dict(new_item)

    def update(self, item_id: str, data: dict) -> dict | None:
        """Replace an existing item's fields with the given data. Returns updated item or None."""
        with self._lock:
            for idx, item in enumerate(self._items):
                if item.get("id") == item_id:
                    # Preserve the id, replace everything else
                    updated = {"id": item_id}
                    updated.update(data)
                    self._items[idx] = updated
                    self._save()
                    return dict(updated)
        return None

    def delete(self, item_id: str) -> bool:
        """Delete an item by ID. Returns True if deleted, False if not found."""
        with self._lock:
            for idx, item in enumerate(self._items):
                if item.get("id") == item_id:
                    del self._items[idx]
                    self._save()
                    return True
        return False

    def filter(self, params: dict) -> list[dict]:
        """Return items where all given key-value pairs match exactly."""
        with self._lock:
            result = []
            for item in self._items:
                match = True
                for key, values in params.items():
                    item_val = str(item.get(key, ""))
                    # values is a list from parse_qs; check if any value matches
                    if not any(item_val == v for v in values):
                        match = False
                        break
                if match:
                    result.append(dict(item))
            return result


# ---------------------------------------------------------------------------
# Threading HTTP Server
# ---------------------------------------------------------------------------

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a separate thread."""
    allow_reuse_address = True
    daemon_threads = True


# ---------------------------------------------------------------------------
# Request Handler
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):
    """
    Handles HTTP requests with routing, authentication, and JSON responses.

    All responses include Content-Type: application/json.
    """

    # Reference to the shared store – set by main() after creation
    store: ItemStore = None  # type: ignore[assignment]
    auth_token: str = DEFAULT_AUTH_TOKEN

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route(self) -> tuple[str | None, str | None]:
        """Parse the request path and return (route_type, item_id) or (None, None)."""
        path = self.path.split("?")[0]  # strip query string
        parts = [p for p in path.split("/") if p]  # remove empty segments
        if parts == ["items"]:
            return "items", None
        elif len(parts) == 2 and parts[0] == "items" and parts[1] != "":
            return "items_id", parts[1]
        else:
            return None, None

    # ------------------------------------------------------------------
    # HTTP method dispatchers
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._authenticate():
            return
        route_type, item_id = self._route()
        query_params = parse_qs(urlparse(self.path).query)

        if route_type == "items":
            self._handle_get_items(query_params)
        elif route_type == "items_id":
            self._handle_get_item(item_id)
        else:
            self._send_error(404, "Not Found")

    def do_POST(self) -> None:
        if not self._authenticate():
            return
        route_type, item_id = self._route()

        if route_type == "items":
            self._handle_create_item()
        elif route_type == "items_id":
            self._send_method_not_allowed(["GET", "PUT", "DELETE"])
        else:
            self._send_error(404, "Not Found")

    def do_PUT(self) -> None:
        if not self._authenticate():
            return
        route_type, item_id = self._route()

        if route_type == "items_id":
            self._handle_update_item(item_id)
        elif route_type == "items":
            self._send_method_not_allowed(["GET", "POST"])
        else:
            self._send_error(404, "Not Found")

    def do_DELETE(self) -> None:
        if not self._authenticate():
            return
        route_type, item_id = self._route()

        if route_type == "items_id":
            self._handle_delete_item(item_id)
        elif route_type == "items":
            self._send_method_not_allowed(["GET", "POST"])
        else:
            self._send_error(404, "Not Found")

    def do_PATCH(self) -> None:
        """PATCH is not supported on any route."""
        self._dispatch_unsupported_method(["GET", "POST"], ["GET", "PUT", "DELETE"])

    def do_OPTIONS(self) -> None:
        """OPTIONS is not supported on any route."""
        self._dispatch_unsupported_method(["GET", "POST"], ["GET", "PUT", "DELETE"])

    def do_HEAD(self) -> None:
        """HEAD is not supported on any route."""
        self._dispatch_unsupported_method(["GET", "POST"], ["GET", "PUT", "DELETE"])

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_message(self, format: str, *args) -> None:
        """Override to include timestamp and format as: (timestamp) METHOD PATH -> STATUS."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # args[0] is usually the status code, but let's reconstruct method/path
        print(f"({timestamp}) {self.command} {self.path} -> {args[0]}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> bool:
        """
        Check the Authorization header for a valid Bearer token.

        Returns True if authenticated, False otherwise (and sends 401).
        """
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._send_error(401, "Unauthorized", extra_headers={"WWW-Authenticate": "Bearer"})
            return False

        token = auth_header[len("Bearer "):].strip()
        if token != RequestHandler.auth_token:
            self._send_error(401, "Unauthorized", extra_headers={"WWW-Authenticate": "Bearer"})
            return False

        return True

    # ------------------------------------------------------------------
    # Route Handlers
    # ------------------------------------------------------------------

    def _handle_get_items(self, query_params: dict) -> None:
        """GET /items - return all items, optionally filtered."""
        if query_params:
            items = self.store.filter(query_params)
        else:
            items = self.store.get_all()
        self._send_json(200, items)

    def _handle_get_item(self, item_id: str) -> None:
        """GET /items/{id} - return a single item."""
        item = self.store.get(item_id)
        if item is None:
            self._send_error(404, "Not Found")
            return
        self._send_json(200, item)

    def _handle_create_item(self) -> None:
        """POST /items - create a new item from JSON body."""
        data = self._read_json_body()
        if data is None:
            return  # _read_json_body already sent 400
        if not isinstance(data, dict):
            self._send_error(400, "Invalid JSON: expected a JSON object")
            return
        new_item = self.store.create(data)
        self._send_json(201, new_item)

    def _handle_update_item(self, item_id: str) -> None:
        """PUT /items/{id} - update an existing item."""
        data = self._read_json_body()
        if data is None:
            return
        if not isinstance(data, dict):
            self._send_error(400, "Invalid JSON: expected a JSON object")
            return
        updated = self.store.update(item_id, data)
        if updated is None:
            self._send_error(404, "Not Found")
            return
        self._send_json(200, updated)

    def _handle_delete_item(self, item_id: str) -> None:
        """DELETE /items/{id} - delete an item."""
        deleted = self.store.delete(item_id)
        if not deleted:
            self._send_error(404, "Not Found")
            return
        # 204 No Content – no body, no Content-Type
        self.send_response(204)
        self.end_headers()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _dispatch_unsupported_method(self, items_methods: list[str],
                                     items_id_methods: list[str]) -> None:
        """Handle unsupported HTTP methods (PATCH, OPTIONS, HEAD, etc.).

        Authenticates first, then sends 405 with Allow header for known
        routes, or 404 for unknown routes.
        """
        if not self._authenticate():
            return
        route_type, item_id = self._route()
        if route_type == "items":
            self._send_method_not_allowed(items_methods)
        elif route_type == "items_id":
            self._send_method_not_allowed(items_id_methods)
        else:
            self._send_error(404, "Not Found")

    def _read_json_body(self) -> dict | list | None:
        """Read and parse the request body as JSON. Returns None and sends 400 on failure."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error(400, "Invalid JSON: empty body")
            return None

        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return None
        except Exception:
            self._send_error(400, "Invalid JSON")
            return None

    def _send_json(self, status_code: int, data: dict | list) -> None:
        """Send a JSON response with the given status code."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, message: str,
                    extra_headers: dict | None = None) -> None:
        """Send an error response as JSON."""
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_method_not_allowed(self, allowed: list[str]) -> None:
        """Send a 405 Method Not Allowed response (no body, no Content-Type)."""
        self.send_response(405)
        self.send_header("Allow", ", ".join(allowed))
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Simple REST API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--token", type=str, default=DEFAULT_AUTH_TOKEN,
                        help=f"Bearer token for auth (default: {DEFAULT_AUTH_TOKEN})")
    parser.add_argument("--file", type=str, default=DEFAULT_ITEMS_FILE,
                        help=f"JSON file for item storage (default: {DEFAULT_ITEMS_FILE})")
    args = parser.parse_args()

    # Create shared store
    store = ItemStore(filepath=args.file)

    # Inject store and auth token into the request handler class
    RequestHandler.store = store
    RequestHandler.auth_token = args.token

    server = ThreadingHTTPServer((args.host, args.port), RequestHandler)

    print(f"Server starting on {args.host}:{args.port}", file=sys.stderr)
    print(f"Auth token: {args.token}", file=sys.stderr)
    print(f"Data file: {args.file}", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
