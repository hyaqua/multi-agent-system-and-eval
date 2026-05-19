"""
URL router for the REST API.
"""

import re
from http.server import BaseHTTPRequestHandler
from typing import Callable, Optional

# Route handler signature:
#   handler(request_handler) -> None
# The handler is responsible for sending the response.

HandlerFunc = Callable[["RequestHandler"], None]


class Router:
    """Simple regex-based URL router with method dispatch."""

    def __init__(self):
        # List of (method, pattern, handler)
        self._routes: list[tuple[str, re.Pattern, HandlerFunc]] = []

    def add(self, method: str, pattern: str, handler: HandlerFunc) -> None:
        """Register a route: method + regex pattern -> handler."""
        compiled = re.compile("^" + pattern + "$")
        self._routes.append((method.upper(), compiled, handler))

    def dispatch(self, method: str, path: str) -> tuple[Optional[HandlerFunc], dict]:
        """
        Find a matching route.  Returns (handler, kwargs) or (None, {}).
        kwargs contains named regex groups.
        """
        for route_method, pattern, handler in self._routes:
            if route_method == method.upper():
                m = pattern.match(path)
                if m:
                    return handler, m.groupdict()
        return None, {}

    def allowed_methods(self, path: str) -> set[str]:
        """Return the set of HTTP methods that have routes for *path*."""
        methods: set[str] = set()
        for method, pattern, _ in self._routes:
            if pattern.match(path):
                methods.add(method)
        return methods
