"""
protocol.py — Message formats, parsing helpers, and constants for the
distributed key-value store wire protocol.

All messages are UTF-8, newline-delimited strings.
"""

# ----- constants ------------------------------------------------------------
DELIMITER = "\n"
ENCODING = "utf-8"

# Command keywords
CMD_REGISTER = "REGISTER"
CMD_SET = "SET"
CMD_GET = "GET"
CMD_DELETE = "DELETE"
CMD_LIST = "LIST"
CMD_PING = "PING"
CMD_PONG = "PONG"
CMD_OK = "OK"
CMD_ERROR = "ERROR"
CMD_QUIT = "QUIT"

# ---------------------------------------------------------------------------


def encode_msg(*parts: str) -> bytes:
    """Join parts with a single space and append a newline."""
    return (" ".join(parts) + DELIMITER).encode(ENCODING)


def decode_msg(data: bytes) -> str:
    """Decode bytes to a stripped string."""
    return data.decode(ENCODING).strip()


def split_cmd(line: str) -> list[str]:
    """Split a command line by whitespace.  Values may contain spaces so we
    use a special convention for SET: the last optional token is TTL."""
    return line.split(" ")


def parse_set(line: str) -> tuple[str, str, int | None]:
    """
    Parse a SET command line.
    Returns (key, value, ttl | None).
    Format: SET <key> <value> [TTL]
    """
    parts = line.split(" ", 2)  # ['SET', 'key', 'value [TTL]']
    if len(parts) < 3:
        raise ValueError("SET requires key and value")
    key = parts[1]
    rest = parts[2].rsplit(" ", 1)
    if len(rest) == 2:
        try:
            ttl = int(rest[1])
            value = rest[0]
            return key, value, ttl
        except ValueError:
            pass
    # No TTL or TTL parsing failed
    value = parts[2]
    return key, value, None


def parse_get(line: str) -> str:
    """Parse GET command. Returns key."""
    parts = line.split(" ", 1)
    if len(parts) < 2:
        raise ValueError("GET requires a key")
    return parts[1]


def parse_delete(line: str) -> str:
    """Parse DELETE command. Returns key."""
    parts = line.split(" ", 1)
    if len(parts) < 2:
        raise ValueError("DELETE requires a key")
    return parts[1]


def parse_list(line: str) -> str | None:
    """Parse LIST command. Returns prefix or None."""
    parts = line.split(" ", 1)
    if len(parts) == 2:
        return parts[1]
    return None


def parse_register(line: str) -> tuple[str, str, int]:
    """Parse REGISTER command. Returns (node_id, host, port)."""
    parts = line.split(" ")
    if len(parts) != 4:
        raise ValueError("REGISTER requires node_id host port")
    return parts[1], parts[2], int(parts[3])


def ok_resp(data: str | None = None) -> str:
    """Build an OK response."""
    if data:
        return f"OK {data}"
    return "OK"


def error_resp(msg: str) -> str:
    """Build an ERROR response."""
    return f"ERROR {msg}"
