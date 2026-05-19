"""
HTTP REST API server using only the Python standard library.

Features:
- ThreadingHTTPServer for concurrent request handling
- JSON request/response bodies
- Bearer-token authentication
- CRUD operations on items persisted to a JSON file
- Query-parameter filtering on GET /items
- Proper status codes (200, 201, 204, 400, 401, 404, 405)
"""

import json
import logging
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from auth import Authenticator
from config import AUTH_TOKEN, DATA_FILE, HOST, LOG_FORMAT, PORT
from router import Router
from store import ItemStore

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("rest_api")

store = ItemStore(DATA_FILE)
authenticator = Authenticator(AUTH_TOKEN)
router = Router()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler with routing, auth, and JSON support."""

    # Silence per-request log output from BaseHTTPRequestHandler
    # We do our own logging in log_message.
    def log_message(self, fmt: str, *args) -> None:
        logger.info("%s - %s", self.client_address[0], fmt % args)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_auth(self) -> bool:
        """Return True if the request carries a valid token."""
        auth_header = self.headers.get("Authorization")
        return authenticator.authenticate(auth_header)

    def _send_json(self, status: int, data: object) -> None:
        """Send a JSON response with the given HTTP status code."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_no_content(self) -> None:
        """Send a 204 No Content response (no body)."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def _send_error(self, status: int, message: str) -> None:
        """Send a JSON error response."""
        self._send_json(status, {"error": message})

    def _read_json_body(self) -> dict | None:
        """
        Read and parse the JSON request body.
        Returns the parsed dict or sends a 400 response and returns None.
        """
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body is empty")
            return None

        try:
            raw = self.rfile.read(content_length)
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON in request body")
            return None

        if not isinstance(data, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object")
            return None

        return data

    def _parse_query_params(self) -> dict[str, str]:
        """Extract query parameters from the URL as a flat dict."""
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=False)
        # parse_qs returns {key: [val1, val2]}; flatten to first value
        return {k: v[0] for k, v in qs.items()}

    # ------------------------------------------------------------------
    # HTTP method dispatch
    # ------------------------------------------------------------------

    def _handle_request(self) -> None:
        """Main dispatcher: auth check  routing  handler."""
        # ---- Auth check (skip for OPTIONS if we ever add it) ----
        if not self._check_auth():
            self._send_error(HTTPStatus.UNAUTHORIZED, "Missing or invalid token")
            return

        # Parse path without query string
        parsed = urlparse(self.path)
        path = parsed.path

        method = self.command.upper()

        handler, kwargs = router.dispatch(method, path)

        if handler is not None:
            # Store matched kwargs for route handlers to use
            self._route_kwargs = kwargs
            handler(self)
            return

        # No matching route for this method+path.
        # Check if the path exists for other methods  405; else 404.
        allowed = router.allowed_methods(path)
        if allowed:
            # There are routes for this path but not for this method
            allow_header = ", ".join(sorted(allowed))
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Content-Type", "application/json")
            self.send_header("Allow", allow_header)
            body = json.dumps({
                "error": "Method not allowed",
                "allowed_methods": sorted(allowed),
            }).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "Not found")

    # ---- Override do_* to funnel into _handle_request ----

    def do_GET(self) -> None:
        self._handle_request()

    def do_POST(self) -> None:
        self._handle_request()

    def do_PUT(self) -> None:
        self._handle_request()

    def do_DELETE(self) -> None:
        self._handle_request()

    # Also handle PATCH, OPTIONS, HEAD gracefully
    def do_PATCH(self) -> None:
        self._handle_request()

    def do_OPTIONS(self) -> None:
        self._handle_request()

    def do_HEAD(self) -> None:
        self._handle_request()


# ---------------------------------------------------------------------------
# Route handler functions
# ---------------------------------------------------------------------------

def handle_list_items(handler: RequestHandler) -> None:
    """GET /items — return all items, optionally filtered."""
    filters = handler._parse_query_params()
    items = store.all(filters=filters if filters else None)
    handler._send_json(HTTPStatus.OK, items)


def handle_get_item(handler: RequestHandler) -> None:
    """GET /items/{id} — return a single item."""
    item_id = handler._route_kwargs["item_id"]
    item = store.get(item_id)
    if item is None:
        handler._send_error(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    else:
        handler._send_json(HTTPStatus.OK, item)


def handle_create_item(handler: RequestHandler) -> None:
    """POST /items — create a new item."""
    data = handler._read_json_body()
    if data is None:
        return  # error response already sent
    item = store.create(data)
    handler._send_json(HTTPStatus.CREATED, item)


def handle_update_item(handler: RequestHandler) -> None:
    """PUT /items/{id} — replace an existing item."""
    item_id = handler._route_kwargs["item_id"]
    data = handler._read_json_body()
    if data is None:
        return
    updated = store.update(item_id, data)
    if updated is None:
        handler._send_error(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    else:
        handler._send_json(HTTPStatus.OK, updated)


def handle_delete_item(handler: RequestHandler) -> None:
    """DELETE /items/{id} — delete an item."""
    item_id = handler._route_kwargs["item_id"]
    deleted = store.delete(item_id)
    if not deleted:
        handler._send_error(HTTPStatus.NOT_FOUND, f"Item {item_id} not found")
    else:
        handler._send_no_content()


# ---------------------------------------------------------------------------
# Register routes
# ---------------------------------------------------------------------------

router.add("GET",    r"/items",                    handle_list_items)
router.add("GET",    r"/items/(?P<item_id>\d+)",   handle_get_item)
router.add("POST",   r"/items",                    handle_create_item)
router.add("PUT",    r"/items/(?P<item_id>\d+)",   handle_update_item)
router.add("DELETE", r"/items/(?P<item_id>\d+)",   handle_delete_item)


# ---------------------------------------------------------------------------
# Custom server with SO_REUSEADDR
# ---------------------------------------------------------------------------

class ReuseThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that sets SO_REUSEADDR to avoid 'Address already in use'."""
    allow_reuse_address = True

    def server_bind(self):
        """Override to set SO_REUSEADDR before binding."""
        import socket
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the REST API server."""
    server = ReuseThreadingHTTPServer((HOST, PORT), RequestHandler)
    logger.info("REST API server starting on %s:%d", HOST, PORT)
    logger.info("Auth token: Bearer %s", AUTH_TOKEN)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
