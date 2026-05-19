"""
Text-based protocol definitions for the distributed key-value store.

All messages end with a newline character (\\n). The protocol uses simple
space-delimited commands and responses.

SET values may be enclosed in double quotes to preserve spaces.
LIST responses use a count-based format (count on first line, then keys).
"""

# Command constants
CMD_SET = "SET"
CMD_GET = "GET"
CMD_DELETE = "DELETE"
CMD_LIST = "LIST"
CMD_PING = "PING"
CMD_REGISTER = "REGISTER"

# Response constants
RESP_OK = "OK"
RESP_VALUE = "VALUE"
RESP_NOTFOUND = "NOTFOUND"
RESP_DELETED = "DELETED"
RESP_PONG = "PONG"
RESP_ERROR = "ERROR"


def encode_command(*args) -> str:
    """Encode a command line from arguments. Joins with spaces and appends newline."""
    return " ".join(str(a) for a in args) + "\n"


def _quote_value(value: str) -> str:
    """Quote a value if it contains spaces or special characters.
    Inside the quoted string, double-quotes are escaped with backslash."""
    if " " in value or "\t" in value or "\n" in value or '"' in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def encode_set(key: str, value: str, ttl: int = 0) -> str:
    """Encode a SET command. ttl=0 means no expiry.
    Values with spaces are automatically quoted."""
    quoted = _quote_value(value)
    if ttl > 0:
        return encode_command(CMD_SET, key, quoted, ttl)
    return encode_command(CMD_SET, key, quoted)


def encode_get(key: str) -> str:
    return encode_command(CMD_GET, key)


def encode_delete(key: str) -> str:
    return encode_command(CMD_DELETE, key)


def encode_list(prefix: str = "") -> str:
    if prefix:
        return encode_command(CMD_LIST, prefix)
    return encode_command(CMD_LIST)


def encode_ping() -> str:
    return encode_command(CMD_PING)


def encode_register(node_id: str, vcount: int) -> str:
    return encode_command(CMD_REGISTER, node_id, vcount)


def encode_ok() -> str:
    return RESP_OK + "\n"


def encode_value(value: str) -> str:
    return f"{RESP_VALUE} {value}\n"


def encode_notfound() -> str:
    return RESP_NOTFOUND + "\n"


def encode_deleted() -> str:
    return RESP_DELETED + "\n"


def encode_pong() -> str:
    return RESP_PONG + "\n"


def encode_error(msg: str) -> str:
    return f"{RESP_ERROR} {msg}\n"


def parse_command(line: str):
    """
    Parse a command line into (command, args).
    Returns (command_uppercase, list_of_args) or (None, []) if empty/malformed.
    """
    line = line.strip()
    if not line:
        return None, []
    parts = line.split()
    cmd = parts[0].upper()
    args = parts[1:] if len(parts) > 1 else []
    return cmd, args


def parse_set(line: str):
    """
    Parse a SET command line into (key, value, ttl).

    Handles quoted values with escape sequences.
    Returns (key, value, ttl) where ttl defaults to 0.
    Raises ValueError if the line is malformed.

    Examples:
        SET mykey hello          -> ("mykey", "hello", 0)
        SET mykey "hello world"  -> ("mykey", "hello world", 0)
        SET mykey "hello world" 3600 -> ("mykey", "hello world", 3600)
        SET mykey value 3600     -> ("mykey", "value", 3600)
    """
    line = line.strip()
    # Remove the leading "SET " (case-insensitive)
    rest = line[4:].strip() if line.upper().startswith("SET ") else ""
    if not rest:
        raise ValueError("SET requires key and value")

    # Read key (first token, no quoting for keys)
    if rest.startswith('"'):
        raise ValueError("Key must not be quoted")

    parts = rest.split(None, 1)  # split on whitespace, max 1 split
    key = parts[0]
    remainder = parts[1] if len(parts) > 1 else ""

    if not remainder:
        raise ValueError("SET requires a value")

    remainder = remainder.strip()

    # Parse value
    if remainder.startswith('"'):
        # Quoted value: read until closing unescaped quote
        # The first char is ", so start from index 1
        value_chars = []
        i = 1
        while i < len(remainder):
            ch = remainder[i]
            if ch == '\\' and i + 1 < len(remainder):
                # Escape sequence
                next_ch = remainder[i + 1]
                if next_ch == '"':
                    value_chars.append('"')
                elif next_ch == '\\':
                    value_chars.append('\\')
                else:
                    value_chars.append(ch)
                    value_chars.append(next_ch)
                i += 2
            elif ch == '"':
                # Closing quote
                i += 1
                break
            else:
                value_chars.append(ch)
                i += 1
        else:
            raise ValueError("Unterminated quoted value")

        value = "".join(value_chars)
        # After closing quote, read optional TTL
        after_quote = remainder[i:].strip()
        ttl = 0
        if after_quote:
            try:
                ttl = int(after_quote)
            except ValueError:
                raise ValueError(f"Invalid TTL value: {after_quote}")
    else:
        # Unquoted value: first token is value, optionally followed by TTL
        rem_parts = remainder.split(None, 1)
        value = rem_parts[0]
        ttl = 0
        if len(rem_parts) >= 2:
            try:
                ttl = int(rem_parts[1])
            except ValueError:
                raise ValueError(f"Invalid TTL value: {rem_parts[1]}")

    return key, value, ttl


def parse_list(line: str) -> str:
    """
    Parse a LIST command line. Returns the prefix (empty string if none).

    Example:
        LIST        -> ""
        LIST abc    -> "abc"
    """
    line = line.strip()
    if line.upper() == "LIST":
        return ""
    # Remove "LIST " prefix
    rest = line[5:].strip() if line.upper().startswith("LIST ") else ""
    return rest


def encode_list_response(keys: list[str]) -> str:
    """
    Encode a LIST response as count + newline-separated keys.
    Format:
        <count>\\n
        <key1>\\n
        ...
        <keyN>\\n
    """
    return str(len(keys)) + "\n" + "".join(k + "\n" for k in keys)
