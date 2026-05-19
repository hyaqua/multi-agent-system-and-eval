"""
protocol.py – Shared constants, message formats, and text-protocol parsing/serialisation.
All messages are UTF-8 encoded lines terminated by \\n.
"""

# Special response markers
OK = "OK"
NOT_FOUND = "NOT_FOUND"
ERROR = "ERROR"
VALUE = "VALUE"
LIST = "LIST"
PING = "PING"
PONG = "PONG"
REGISTER = "REGISTER"

# Command constants
CMD_SET = "SET"
CMD_GET = "GET"
CMD_DELETE = "DELETE"
CMD_LIST = "LIST"
CMD_PING = "PING"
CMD_REGISTER = "REGISTER"
CMD_QUIT = "QUIT"

# Network
ENCODING = "utf-8"
LINE_TERMINATOR = b"\n"


def encode_message(*parts) -> bytes:
    """Encode a message as UTF-8 bytes with \\n terminator."""
    text = " ".join(str(p) for p in parts)
    return text.encode(ENCODING) + LINE_TERMINATOR


def decode_message(data: bytes) -> str:
    """Decode received bytes to a stripped string."""
    return data.decode(ENCODING).strip()


def parse_command(line: str):
    """Parse a command line into (command, args_list). Returns (None, []) on empty."""
    line = line.strip()
    if not line:
        return None, []
    parts = line.split()
    command = parts[0].upper()
    args = parts[1:]
    return command, args


def build_set_command(key: str, value: str, ttl: int = None) -> str:
    """Build a SET command string (for forwarding to node)."""
    if ttl is not None:
        return f"{CMD_SET} {key} {value} {ttl}"
    return f"{CMD_SET} {key} {value}"


def build_get_command(key: str) -> str:
    return f"{CMD_GET} {key}"


def build_delete_command(key: str) -> str:
    return f"{CMD_DELETE} {key}"


def build_list_command(prefix: str = "") -> str:
    if prefix:
        return f"{CMD_LIST} {prefix}"
    return CMD_LIST
