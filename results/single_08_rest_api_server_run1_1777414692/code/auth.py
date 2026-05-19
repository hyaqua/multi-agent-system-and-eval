"""
Basic token-based authentication.
"""


class Authenticator:
    """Validates Bearer tokens from the Authorization header."""

    def __init__(self, valid_token: str):
        self._valid_token = valid_token

    def authenticate(self, authorization_header: str | None) -> bool:
        """Return True if the provided header contains a valid token."""
        if not authorization_header:
            return False
        parts = authorization_header.split(maxsplit=1)
        if len(parts) != 2:
            return False
        scheme, token = parts
        if scheme.lower() != "bearer":
            return False
        return token == self._valid_token
