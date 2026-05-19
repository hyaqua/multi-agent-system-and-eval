#!/usr/bin/env python3
"""
REST API Server for managing a collection of items.
Uses only Python standard library (http.server, json, threading, etc.).

Features:
- GET    /items          — list all items, with optional ?field=value filtering
- GET    /items/{id}     — get single item or 404
- POST   /items          — create item from JSON body → 201
- PUT    /items/{id}     — update item → 200 or 404
- DELETE /items/{id}     — delete item → 204 or 404
- Bearer token authentication on all endpoints
- JSON file persistence
- Threaded request handling
- Request logging
"""

import json
import logging
import os
import sys
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration — can be overridden via environment variables
# ---------------------------------------------------------------------------
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(tempfile.gettempdir(), "items.json"))
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "secret-token")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("RESTServer")


# ===========================================================================
#  Item Store — JSON file persistence
# ===========================================================================
class ItemStore:
    """Thread-safe(ish) store backed by a JSON file."""

    def __init__(self, filepath: str) -> None:
        self.filepath: str = filepath
        self.items: dict[str, dict] = {}
        self._next_id: int = 1
        self.load()

    # ------------------------------------------------------------------ I/O

    def load(self) -> None:
        """Load items from disk.  Creates an empty file if none exists."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.items = data.get("items", {})
                self._next_id = data.get("_next_id", 1)
                logger.info("Loaded %d items from %s", len(self.items), self.filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Error loading %s: %s", self.filepath, exc)
                self.items = {}
                self._next_id = 1
        else:
            logger.info("No data file found — starting fresh.")
            self.save()

    def save(self) -> None:
        """Persist current state to disk."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump({"items": self.items, "_next_id": self._next_id},
                          fh, indent=2)
        except OSError as exc:
            logger.error("Error saving %s: %s", self.filepath, exc)

    # --------------------------------------------------------------- CRUD

    def get_all(self) -> list[dict]:
        """Return every item (shallow copies)."""
        return list(self.items.values())

    def get(self, item_id: str) -> Optional[dict]:
        """Return a single item or None."""
        return self.items.get(item_id)

    def create(self, data: dict) -> dict:
        """Create a new item.  The ``id`` field is auto-generated."""
        item_id = str(self._next_id)
        self._next_id += 1
        data["id"] = item_id
        self.items[item_id] = data
        self.save()
        return data

    def update(self, item_id: str, data: dict) -> Optional[dict]:
        """Replace an existing item.  Returns the updated item or None."""
        if item_id not in self.items:
            return None
        data["id"] = item_id          # keep id stable
        self.items[item_id] = data
        self.save()
        return data

    def delete(self, item_id: str) -> bool:
        """Remove an item.  Returns True if it existed."""
        if item_id not in self.items:
            return False
        del self.items[item_id]
        self.save()
        return True

    def filter(self, **kwargs: str) -> list[dict]:
        """Return items whose fields match *all* given values (string compare)."""
        results = list(self.items.values())
        for key, want in kwargs.items():
            results = [it for it in results
                       if str(it.get(key, "")) == want]
        return results


# ===========================================================================
#  Threaded HTTP server
# ===========================================================================
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTPServer that spawns a thread per request."""
    daemon_threads = True


# ===========================================================================
#  Request Handler
# ===========================================================================
class RequestHandler(BaseHTTPRequestHandler):
    """Routes requests to CRUD methods on the shared ItemStore."""

    store: ItemStore = None  # injected before server starts

    # -- logging -----------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s - %s", self.client_address[0], fmt % args)

    # -- response helpers --------------------------------------------------

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response with the given status code."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        """Send a JSON error object."""
        self._send_json({"error": message}, status)

    def _send_no_content(self) -> None:
        """Send a 204 No Content response (no body)."""
        self.send_response(204)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    # -- request body ------------------------------------------------------

    def _read_json_body(self) -> Optional[dict]:
        """Parse the request body as JSON.  Returns None on any failure."""
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return None
        try:
            raw = self.rfile.read(int(content_length))
            if not raw.strip():
                return None
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return None
            return data
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None

    # -- authentication ----------------------------------------------------

    def _authenticate(self) -> bool:
        """Return True if the request carries a valid Bearer token."""
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return header[len("Bearer "):] == AUTH_TOKEN

    # -- helpers -----------------------------------------------------------

    def _parsed_path(self) -> tuple[str, str]:
        """Return (clean_path, query_string).  Trailing slashes are stripped."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        return path, parsed.query

    def _item_id_from_path(self, path: str) -> Optional[str]:
        """Extract item id from '/items/<id>' or return None."""
        if path.startswith("/items/") and len(path) > len("/items/"):
            return path[len("/items/"):]
        return None

    # ==================================================================
    #  HTTP method dispatchers
    # ==================================================================

    # -- GET ---------------------------------------------------------------
    def do_GET(self) -> None:
        if not self._authenticate():
            return self._send_error(401, "Unauthorized")

        path, qs = self._parsed_path()

        # GET /items  (with optional ?field=value filter)
        if path == "/items":
            filters = {}
            if qs:
                for k, v in parse_qs(qs, keep_blank_values=True).items():
                    if v:
                        filters[k] = v[0]
            items = self.store.filter(**filters) if filters else self.store.get_all()
            return self._send_json(items)

        # GET /items/{id}
        item_id = self._item_id_from_path(path)
        if item_id is not None:
            item = self.store.get(item_id)
            if item is None:
                return self._send_error(404, f"Item with id '{item_id}' not found")
            return self._send_json(item)

        # Unknown route
        return self._send_error(404, f"Not Found: {self.path}")

    # -- POST --------------------------------------------------------------
    def do_POST(self) -> None:
        if not self._authenticate():
            return self._send_error(401, "Unauthorized")

        path, _ = self._parsed_path()

        # POST /items  (create)
        if path == "/items":
            body = self._read_json_body()
            if body is None:
                return self._send_error(400, "Invalid JSON in request body")
            item = self.store.create(body)
            return self._send_json(item, 201)

        # POST /items/{id} is not allowed
        if self._item_id_from_path(path) is not None:
            return self._send_error(405, "Method Not Allowed")

        return self._send_error(404, f"Not Found: {self.path}")

    # -- PUT ---------------------------------------------------------------
    def do_PUT(self) -> None:
        if not self._authenticate():
            return self._send_error(401, "Unauthorized")

        path, _ = self._parsed_path()

        # PUT /items  (bulk update not supported)
        if path == "/items":
            return self._send_error(405, "Method Not Allowed")

        item_id = self._item_id_from_path(path)
        if item_id is not None:
            body = self._read_json_body()
            if body is None:
                return self._send_error(400, "Invalid JSON in request body")
            updated = self.store.update(item_id, body)
            if updated is None:
                return self._send_error(404, f"Item with id '{item_id}' not found")
            return self._send_json(updated)

        return self._send_error(404, f"Not Found: {self.path}")

    # -- DELETE ------------------------------------------------------------
    def do_DELETE(self) -> None:
        if not self._authenticate():
            return self._send_error(401, "Unauthorized")

        path, _ = self._parsed_path()

        # DELETE /items  (bulk delete not supported)
        if path == "/items":
            return self._send_error(405, "Method Not Allowed")

        item_id = self._item_id_from_path(path)
        if item_id is not None:
            if not self.store.delete(item_id):
                return self._send_error(404, f"Item with id '{item_id}' not found")
            return self._send_no_content()

        return self._send_error(404, f"Not Found: {self.path}")

    # -- Unsupported methods on any route ----------------------------------
    def do_PATCH(self) -> None:
        self._send_error(405, "Method Not Allowed")

    def do_HEAD(self) -> None:
        self._send_error(405, "Method Not Allowed")

    def do_OPTIONS(self) -> None:
        self._send_error(405, "Method Not Allowed")


# ===========================================================================
#  Entry point
# ===========================================================================
def main() -> None:
    store = ItemStore(DATA_FILE)
    RequestHandler.store = store

    server = ThreadedHTTPServer((HOST, PORT), RequestHandler)
    logger.info("REST API server listening on %s:%d", HOST, PORT)
    logger.info("Data file  : %s", os.path.abspath(DATA_FILE))
    logger.info("Auth token : %s", AUTH_TOKEN)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down …")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
