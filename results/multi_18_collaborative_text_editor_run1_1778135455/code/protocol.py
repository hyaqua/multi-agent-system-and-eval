"""
Protocol definitions for the collaborative text editor.
Uses newline-delimited JSON messages over TCP.
"""

import json


def encode_message(msg: dict) -> bytes:
    """Encode a message dict to JSON bytes with newline framing."""
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(data: bytes) -> dict | None:
    """Decode a JSON message from bytes. Returns None if invalid."""
    try:
        text = data.decode("utf-8").strip()
        if not text:
            return None
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ── Message type constants ──────────────────────────────────────────────────

# Client -> Server
TYPE_CONNECT = "connect"
TYPE_OPERATION = "operation"
TYPE_CURSOR_UPDATE = "cursor_update"
TYPE_LOCK_REQUEST = "lock_request"
TYPE_LOCK_RELEASE = "lock_release"
TYPE_SAVE_REQUEST = "save_request"
TYPE_UNDO_REQUEST = "undo_request"
TYPE_DISCONNECT = "disconnect"

# Server -> Client
TYPE_ACK = "ack"
TYPE_ERROR = "error"
TYPE_LOCK_GRANT = "lock_grant"
TYPE_LOCK_STATUS = "lock_status"
TYPE_SAVE_ACK = "save_ack"
TYPE_USER_JOIN = "user_join"
TYPE_USER_LEAVE = "user_leave"

# Both directions
TYPE_CURSOR_UPDATE = "cursor_update"  # also server broadcasts


def make_connect(user: str, room: str, password: str = "") -> dict:
    return {"type": TYPE_CONNECT, "user": user, "room": room, "password": password}


def make_ack(status: str, document: str = "", clients: list = None,
             version: int = 0, lock_holder: str | None = None,
             user_color: int = 0) -> dict:
    return {
        "type": TYPE_ACK,
        "status": status,
        "document": document,
        "clients": clients or [],
        "version": version,
        "lock_holder": lock_holder,
        "user_color": user_color,
    }


def make_operation(op: str, pos: int, text: str,
                   base_version: int = 0, op_id: int = 0) -> dict:
    return {
        "type": TYPE_OPERATION,
        "op": op,
        "pos": pos,
        "text": text,
        "base_version": base_version,
        "op_id": op_id,
    }


def make_cursor_update(user: str, pos: int) -> dict:
    return {"type": TYPE_CURSOR_UPDATE, "user": user, "pos": pos}


def make_lock_request(user: str) -> dict:
    return {"type": TYPE_LOCK_REQUEST, "user": user}


def make_lock_release(user: str) -> dict:
    return {"type": TYPE_LOCK_RELEASE, "user": user}


def make_lock_grant(user: str) -> dict:
    return {"type": TYPE_LOCK_GRANT, "user": user}


def make_lock_status(holder: str | None, queue: list = None) -> dict:
    return {"type": TYPE_LOCK_STATUS, "holder": holder, "queue": queue or []}


def make_save_request() -> dict:
    return {"type": TYPE_SAVE_REQUEST}


def make_save_ack() -> dict:
    return {"type": TYPE_SAVE_ACK}


def make_undo_request(user: str) -> dict:
    return {"type": TYPE_UNDO_REQUEST, "user": user}


def make_error(msg: str) -> dict:
    return {"type": TYPE_ERROR, "message": msg}


def make_user_join(user: str, color: int) -> dict:
    return {"type": TYPE_USER_JOIN, "user": user, "color": color}


def make_user_leave(user: str) -> dict:
    return {"type": TYPE_USER_LEAVE, "user": user}
