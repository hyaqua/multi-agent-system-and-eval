import json
import logging
import traceback
from http.server import BaseHTTPRequestHandler
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import auth
from data_store import DataStore

logger = logging.getLogger("api")


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler with routing, auth, and JSON support."""

    # Will be set by server.py after instantiation
    store: DataStore = None  # type: ignore[assignment]

    # Allowed methods per route pattern
    _ROUTE_ALLOWED = {
        "items":     {"GET", "POST"},
        "items_id":  {"GET", "PUT", "DELETE"},
    }

    # ------------------------------------------------------------------
    # Override log_message to use our logger
    # ------------------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("%s %s", self.client_address[0], fmt % args)

    # ------------------------------------------------------------------
    # HTTP method dispatchers
    # ------------------------------------------------------------------
    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PUT(self) -> None:
        self._handle_request("PUT")

    def do_DELETE(self) -> None:
        self._handle_request("DELETE")

    # ------------------------------------------------------------------
    # Core request handling
    # ------------------------------------------------------------------
    def _handle_request(self, method: str) -> None:
        try:
            # 1. Authenticate every request
            if not self._authenticate():
                return  # response already sent

            # 2. Parse URL
            parsed = urlparse(self.path)
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            query_params = parse_qs(parsed.query) if parsed.query else {}

            # 3. Route matching
            if path_parts[:1] == ["items"]:
                if len(path_parts) == 1:
                    route = "items"
                elif len(path_parts) == 2:
                    route = "items_id"
                else:
                    self._send_error(404, "Not Found")
                    return
            else:
                self._send_error(404, "Not Found")
                return

            # 4. Method allowed?
            allowed = self._ROUTE_ALLOWED[route]
            if method not in allowed:
                self._send_error(405, "Method Not Allowed", extra_headers={
                    "Allow": ", ".join(sorted(allowed)),
                })
                return

            # 5. Dispatch
            if route == "items":
                if method == "GET":
                    self._get_items(query_params)
                elif method == "POST":
                    self._post_items()
            else:  # items_id
                try:
                    item_id = int(path_parts[1])
                except ValueError:
                    self._send_error(404, "Not Found")
                    return

                if method == "GET":
                    self._get_item(item_id)
                elif method == "PUT":
                    self._put_item(item_id)
                elif method == "DELETE":
                    self._delete_item(item_id)

        except Exception:
            logger.error("Unhandled exception:\n%s", traceback.format_exc())
            try:
                self._send_error(500, "Internal Server Error")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _authenticate(self) -> bool:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._send_error(401, "Unauthorized", extra_headers={
                "WWW-Authenticate": "Bearer",
            })
            return False
        token = auth_header[7:]  # strip "Bearer "
        if not auth.validate_token(token):
            self._send_error(401, "Unauthorized", extra_headers={
                "WWW-Authenticate": "Bearer",
            })
            return False
        return True

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------
    def _get_items(self, query_params: dict[str, list[str]]) -> None:
        items = self.store.get_all()

        # Apply query-parameter filtering
        for key, values in query_params.items():
            val = values[0]
            items = [it for it in items if str(it.get(key, "")) == val]

        self._send_json(200, items)

    def _get_item(self, item_id: int) -> None:
        item = self.store.get_by_id(item_id)
        if item is None:
            self._send_error(404, "Not Found")
            return
        self._send_json(200, item)

    def _post_items(self) -> None:
        body = self._read_json_body()
        if body is None:
            return  # error already sent

        if not isinstance(body, dict):
            self._send_error(400, "Request body must be a JSON object")
            return

        created = self.store.create(body)
        self._send_json(201, created)

    def _put_item(self, item_id: int) -> None:
        # Check existence first
        if self.store.get_by_id(item_id) is None:
            self._send_error(404, "Not Found")
            return

        body = self._read_json_body()
        if body is None:
            return

        if not isinstance(body, dict):
            self._send_error(400, "Request body must be a JSON object")
            return

        updated = self.store.update(item_id, body)
        self._send_json(200, updated)

    def _delete_item(self, item_id: int) -> None:
        deleted = self.store.delete(item_id)
        if not deleted:
            self._send_error(404, "Not Found")
            return
        self._send_json(204, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_json_body(self) -> Optional[Any]:
        """Read and parse JSON request body. Returns None on failure (response sent)."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_error(400, "Invalid Content-Length")
            return None

        if content_length == 0:
            self._send_error(400, "Request body required")
            return None

        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw)
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return None

    def _send_json(self, status_code: int, data: Any) -> None:
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        if status_code == 204:
            self.end_headers()
            return
        body = json.dumps(data).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(
        self,
        status_code: int,
        message: str,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Send a JSON error response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
