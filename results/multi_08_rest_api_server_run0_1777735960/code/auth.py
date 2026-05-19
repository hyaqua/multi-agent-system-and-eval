import os

# Default token; can be overridden via API_TOKEN environment variable.
_DEFAULT_TOKEN = "secret-token-123"

def validate_token(token: str) -> bool:
    """Return True if the given token matches the configured token."""
    expected = os.environ.get("API_TOKEN", _DEFAULT_TOKEN)
    return token == expected
