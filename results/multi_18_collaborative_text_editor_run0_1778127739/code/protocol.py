"""
protocol.py — Message type definitions, JSON validation, and constants.

All communication uses newline-delimited JSON over TCP.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Union
import json

# ── Message types ──────────────────────────────────────────────────────────

@dataclass
class Message:
    """Base message. Subclasses set the 'type' field."""
    type: str

@dataclass
class Connect(Message):
    """Client sends to server on connection."""
    type: str = "connect"
    username: str = ""
    room: str = ""
    password: str = ""

@dataclass
class Ack(Message):
    """Server responds after successful connect."""
    type: str = "ack"
    client_id: str = ""
    document: str = ""
    version: int = 0
    users: List[str] = field(default_factory=list)
    lock_holder: Optional[str] = None

@dataclass
class Operation(Message):
    """Client → server: request to apply an edit.
    Server → clients (broadcast): confirmed edit."""
    type: str = "operation"
    op_type: str = ""          # "insert" or "delete"
    position: int = 0           # character offset in flat string
    text: str = ""              # for insert
    length: int = 0             # for delete
    base_version: int = 0       # server version the client based this on
    client_id: str = ""
    seq_no: int = 0             # client-local sequence number
    op_id: Optional[str] = None # server-assigned unique ID (in broadcasts)

@dataclass
class OperationAck(Message):
    """Server → originating client: confirms op with transformed version."""
    type: str = "operation_ack"
    seq_no: int = 0
    op_id: str = ""
    op_type: str = ""
    position: int = 0
    text: str = ""
    length: int = 0
    new_version: int = 0
    client_id: str = ""

@dataclass
class CursorUpdate(Message):
    """Broadcast cursor position change."""
    type: str = "cursor_update"
    username: str = ""
    line: int = 0
    col: int = 0
    offset: int = 0

@dataclass
class LockRequest(Message):
    """Client requests the exclusive edit lock."""
    type: str = "lock_request"
    client_id: str = ""

@dataclass
class LockGrant(Message):
    """Server grants the lock to a client."""
    type: str = "lock_grant"
    holder: str = ""      # client_id who now holds the lock

@dataclass
class LockRelease(Message):
    """Client releases the lock."""
    type: str = "lock_release"
    client_id: str = ""

@dataclass
class LockUpdate(Message):
    """Server broadcasts lock status change."""
    type: str = "lock_update"
    holder: Optional[str] = None
    queue: List[str] = field(default_factory=list)

@dataclass
class SaveRequest(Message):
    """Client requests a save."""
    type: str = "save_request"
    client_id: str = ""

@dataclass
class SaveAck(Message):
    """Server confirms save."""
    type: str = "save_ack"

@dataclass
class UndoRequest(Message):
    """Client requests undo of their last operation."""
    type: str = "undo"
    client_id: str = ""

@dataclass
class Disconnect(Message):
    """Notification of disconnect."""
    type: str = "disconnect"
    username: str = ""

@dataclass
class Error(Message):
    """Server sends an error."""
    type: str = "error"
    message: str = ""

@dataclass
class UserListUpdate(Message):
    """Server broadcasts updated user list."""
    type: str = "user_list_update"
    users: List[str] = field(default_factory=list)


# ── Type mapping ───────────────────────────────────────────────────────────

_TYPE_MAP: Dict[str, type] = {
    "connect": Connect,
    "ack": Ack,
    "operation": Operation,
    "operation_ack": OperationAck,
    "cursor_update": CursorUpdate,
    "lock_request": LockRequest,
    "lock_grant": LockGrant,
    "lock_release": LockRelease,
    "lock_update": LockUpdate,
    "save_request": SaveRequest,
    "save_ack": SaveAck,
    "undo": UndoRequest,
    "disconnect": Disconnect,
    "error": Error,
    "user_list_update": UserListUpdate,
}


def encode(msg: Message) -> bytes:
    """Serialize a Message to JSON bytes with newline terminator."""
    data = _msg_to_dict(msg)
    return (json.dumps(data) + "\n").encode("utf-8")


def decode(line: str) -> Message:
    """Parse a JSON line into a Message instance."""
    data = json.loads(line)
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError(f"Invalid message: missing 'type': {line}")
    msg_type = data["type"]
    cls = _TYPE_MAP.get(msg_type)
    if cls is None:
        raise ValueError(f"Unknown message type: {msg_type}")
    # Build instance from dict, only passing known fields
    import dataclasses
    fields = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in data.items() if k in fields}
    return cls(**kwargs)


def _msg_to_dict(msg: Message) -> Dict[str, Any]:
    """Convert a dataclass message to dict, omitting None values."""
    import dataclasses
    result = {}
    for f in dataclasses.fields(msg):
        val = getattr(msg, f.name)
        if val is not None or f.name == "type":
            result[f.name] = val
    return result
