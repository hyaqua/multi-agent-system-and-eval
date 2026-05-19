"""
HTTP request handler implementing the REST API.
"""
import json
import logging
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from store import DataStore

logger = logging.getLogger("api")


class APIHandler(BaseHTTPRequestHandler):
    """Single handler for all /items routes."""

    # ------------------------------------------------------------------
    # Class-level configuration (set before starting the server)
    # ------------------------------------------------------------------
    data_file: str = "items.json"
    auth_token: str = "secret-token"
    store: DataStore | None = None

    @classmethod
    def init_store(cls) -> None:
        cls.store = DataStore(cls.data_file)

    # ------------------------------------------------------------------
    # BaseHTTPRequestHandler overrides
    # ------------------------------------------------------------------

    def log_message(self, fmt: str, *args) -> None:
        """Log incoming requests via the logging framework."""
        logger.info("%s - %s", self.client_address[0], fmt % args)

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _send_json(self, data, status: int = 200) -> None:
        """Send a JSON response with the given status code."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        """Convenience wrapper for JSON error responses."""
        self._send_json({"error": message}, status)

    def _send_no_content(self) -> None:
        """Send a 204 No Content response with no body."""
        self.send_response(204)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    # ------------------------------------------------------------------
    # Request parsing
    # ------------------------------------------------------------------

    def _read_body(self) -> str | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        return self.rfile.read(length).decode("utf-8")

    def _parse_json_body(self) -> dict | None:
        """Read and parse the JSON request body, or return None on failure."""
        raw = self._read_body()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _check_auth(self) -> bool:
        """Validate the Bearer token in the Authorization header."""
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return header[7:] == self.auth_token  # strip "Bearer "

    def _parse_path(self) -> tuple[str, dict[str, str]]:
        """
        Return (normalised_path, query_params).

        * Trailing slashes are stripped.
        * Query-string values are flattened (single-value → str).
        """
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query, keep_blank_values=True)
        flat: dict[str, str] = {}
        for k, v in qs.items():
            flat[k] = v[0] if len(v) == 1 else v
        return path, flat

    _ROUTE_RE = re.compile(r"^/items(?:/([^/]+))?$")

    def _match_route(self, path: str) -> tuple[str | None, dict | None]:
        """
        Match *path* against known routes.

        Returns ``(route_name, params)`` where *route_name* is one of:

        * ``"items_collection"`` – ``/items``
        * ``"items_single"``     – ``/items/{id}``
        * ``None``               – no match
        """
        m = self._ROUTE_RE.match(path)
        if m is None:
            return None, None
        item_id = m.group(1)
        if item_id is None:
            return "items_collection", {}
        return "items_single", {"id": item_id}

    # ------------------------------------------------------------------
    # HTTP method dispatchers
    # ------------------------------------------------------------------

    # -- helpers shared by several methods -------------------------------

    def _require_auth(self) -> bool:
        """Check auth; if missing send 401 and return False."""
        if not self._check_auth():
            self._send_error(401, "Unauthorized – invalid or missing token")
            return False
        return True

    def _require_valid_route(self) -> tuple[str | None, dict | None]:
        """Parse & match route; if invalid send 404 and return (None,None)."""
        path, query = self._parse_path()
        route, params = self._match_route(path)
        if route is None:
            self._send_error(404, "Not Found")
            return None, None
        return route, {**params, "__query": query}

    def _require_json_object(self) -> dict | None:
        """Read JSON body; if missing/invalid send 400 and return None."""
        data = self._parse_json_body()
        if data is None:
            self._send_error(400, "Invalid JSON in request body")
            return None
        if not isinstance(data, dict):
            self._send_error(400, "Request body must be a JSON object")
            return None
        return data

    # -- GET ------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._require_auth():
            return

        path, query = self._parse_path()
        route, params = self._match_route(path)
        if route is None:
            return self._send_error(404, "Not Found")

        if route == "items_collection":
            items = self.store.get_all()
            # Filter by query parameters (any field)
            if query:
                filtered = []
                for item in items:
                    if all(
                        str(item.get(k, "")) == str(v)
                        for k, v in query.items()
                    ):
                        filtered.append(item)
                items = filtered
            self._send_json(items)

        else:  # items_single
            item = self.store.get(params["id"])
            if item is None:
                self._send_error(404, "Item not found")
            else:
                self._send_json(item)

    # -- POST -----------------------------------------------------------

    def do_POST(self) -> None:
        if not self._require_auth():
            return

        path, _ = self._parse_path()
        route, params = self._match_route(path)
        if route is None:
            return self._send_error(404, "Not Found")

        if route == "items_single":
            return self._send_error(405, "Method Not Allowed")

        # items_collection
        data = self._require_json_object()
        if data is None:
            return
        item = self.store.create(data)
        self._send_json(item, status=201)

    # -- PUT ------------------------------------------------------------

    def do_PUT(self) -> None:
        if not self._require_auth():
            return

        path, _ = self._parse_path()
        route, params = self._match_route(path)
        if route is None:
            return self._send_error(404, "Not Found")

        if route == "items_collection":
            return self._send_error(405, "Method Not Allowed")

        # items_single
        data = self._require_json_object()
        if data is None:
            return
        item = self.store.update(params["id"], data)
        if item is None:
            self._send_error(404, "Item not found")
        else:
            self._send_json(item)

    # -- DELETE ---------------------------------------------------------

    def do_DELETE(self) -> None:
        if not self._require_auth():
            return

        path, _ = self._parse_path()
        route, params = self._match_route(path)
        if route is None:
            return self._send_error(404, "Not Found")

        if route == "items_collection":
            return self._send_error(405, "Method Not Allowed")

        # items_single
        ok = self.store.delete(params["id"])
        if not ok:
            self._send_error(404, "Item not found")
        else:
            self._send_no_content()

    # -- Other methods → 405 on valid routes -----------------------------

    def _unsupported_method(self) -> None:
        path, _ = self._parse_path()
        route, _ = self._match_route(path)
        if route is not None:
            self._send_error(405, "Method Not Allowed")
        else:
            self._send_error(404, "Not Found")

    def do_HEAD(self) -> None:
        self._unsupported_method()

    def do_OPTIONS(self) -> None:
        self._unsupported_method()

    def do_PATCH(self) -> None:
        self._unsupported_method()
