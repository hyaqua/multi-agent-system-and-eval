"""
handler.py – HTTP request handler subclass.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import auth
from router import Router
from storage import ItemStorage

logger = logging.getLogger(__name__)


class RequestHandler(BaseHTTPRequestHandler):
    """
    Custom request handler that delegates to the *shared_router* and
    *shared_storage* class-level attributes.
    """

    # These are set by the server factory before starting.
    shared_router: Router | None = None
    shared_storage: ItemStorage | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_auth(self) -> bool:
        if not auth.validate(self.headers.get("Authorization")):
            self._send_error(401, "Unauthorized")
            return False
        return True

    def _send_json(self, status: int, data):
        """Send a JSON response with the given status code."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        """Send a JSON error response."""
        self._send_json(status, {"error": message})

    def _read_body(self) -> dict | None:
        """Read and parse JSON body.  Returns None on failure."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Invalid JSON: %s", exc)
            self._send_error(400, "Invalid JSON")
            return None

    def _log_request(self, status: int):
        logger.info("%s %s → %d", self.command, self.path, status)

    # ------------------------------------------------------------------
    # HTTP method dispatchers
    # ------------------------------------------------------------------

    def _handle(self):
        """Common request handling: auth → route → execute."""
        # Auth check
        if not self._require_auth():
            self._log_request(401)
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        # Flatten single-value query params
        flat_params = {k: v[0] for k, v in query_params.items()}

        router: Router = self.shared_router
        handler, path_kwargs, allowed_methods = router.resolve(self.command, path)

        # Parse body for methods that typically carry one
        body: dict | None = None
        if self.command in ("POST", "PUT", "PATCH"):
            body = self._read_body()
            if body is None:  # JSON parse error already sent
                self._log_request(400)
                return

        if handler is not None:
            try:
                handler(
                    self,
                    path_params=path_kwargs,
                    query_params=flat_params,
                    body=body or {},
                )
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)
                self._send_error(500, "Internal server error")
                self._log_request(500)
            return

        # No handler – either unknown path or unsupported method
        if allowed_methods:
            # Known path, wrong method → 405
            allowed = ", ".join(sorted(allowed_methods))
            self.send_response(405)
            self.send_header("Allow", allowed)
            self.send_header("Content-Type", "application/json")
            body_bytes = json.dumps({"error": "Method Not Allowed"}).encode("utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
            self._log_request(405)
        else:
            self._send_error(404, "Not found")
            self._log_request(404)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    # Suppress default request logging; we log ourselves.
    def log_request(self, code="-", size="-"):
        pass
