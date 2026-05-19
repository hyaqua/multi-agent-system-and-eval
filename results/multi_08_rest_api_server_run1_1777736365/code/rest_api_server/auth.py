"""
auth.py – Token validation logic.

A fixed token is used for simplicity.  It can be overridden via the
``API_TOKEN`` environment variable.
"""

import os

_DEFAULT_TOKEN = "secret-token"


def validate(auth_header: str | None) -> bool:
    """Return True if *auth_header* contains a valid Bearer token."""
    if not auth_header:
        return False
    parts = auth_header.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    expected = os.environ.get("API_TOKEN", _DEFAULT_TOKEN)
    return parts[1] == expected
