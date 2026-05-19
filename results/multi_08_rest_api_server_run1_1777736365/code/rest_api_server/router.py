"""
router.py – Simple route matcher that maps (method, path_pattern) to callables.

Each pattern is a compiled regex.  When a request comes in the router
returns the matching handler together with any named groups extracted
from the URL.
"""

import re
from typing import Callable, Any

Handler = Callable[..., Any]


class Router:
    """Minimal regex-based router."""

    def __init__(self):
        # Each entry: (method_set, compiled_pattern, handler)
        self._routes: list[tuple[set[str], re.Pattern, Handler]] = []

    def add_route(self, methods: str | list[str], pattern: str, handler: Handler):
        """Register *handler* for one or more HTTP methods and a regex *pattern*."""
        if isinstance(methods, str):
            methods = [methods]
        method_set = {m.upper() for m in methods}
        compiled = re.compile("^" + pattern + "$")
        self._routes.append((method_set, compiled, handler))

    def resolve(self, method: str, path: str) -> tuple[Handler | None, dict, set[str]]:
        """
        Try to match *method* + *path*.

        Returns ``(handler, path_kwargs, allowed_methods)``.

        - If the path is unknown, *handler* is None and *allowed_methods* is empty.
        - If the path is known but the method is not allowed, *handler* is None
          and *allowed_methods* is the set of methods that *are* registered for
          that path.
        """
        known_path = False
        collected_methods: set[str] = set()

        for method_set, compiled, handler in self._routes:
            match = compiled.match(path)
            if match:
                collected_methods |= method_set
                known_path = True
                if method.upper() in method_set:
                    return handler, match.groupdict(), set()
                # continue looking – there may be another route for same path
                # with a different method.

        if known_path:
            return None, {}, collected_methods
        return None, {}, set()
