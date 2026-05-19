"""
shared.py - Common types, Operational Transformation, and Document model
for the collaborative text editor.
"""

import json
import time
from typing import Optional


# ---------------------------------------------------------------------------
# Protocol message types
# ---------------------------------------------------------------------------

MSG_CONNECT = "connect"
MSG_ACK = "ack"
MSG_OPERATION = "operation"
MSG_CURSOR_UPDATE = "cursor_update"
MSG_LOCK_REQUEST = "lock_request"
MSG_LOCK_GRANT = "lock_grant"
MSG_LOCK_RELEASE = "lock_release"
MSG_SAVE_REQUEST = "save_request"
MSG_SAVE_ACK = "save_ack"
MSG_DISCONNECT = "disconnect"
MSG_ERROR = "error"
MSG_DOCUMENT_SYNC = "document_sync"  # full document state for reconnecting clients
MSG_USER_LIST = "user_list"  # broadcast current users in room

MESSAGE_TYPES = frozenset({
    MSG_CONNECT, MSG_ACK, MSG_OPERATION, MSG_CURSOR_UPDATE,
    MSG_LOCK_REQUEST, MSG_LOCK_GRANT, MSG_LOCK_RELEASE,
    MSG_SAVE_REQUEST, MSG_SAVE_ACK, MSG_DISCONNECT, MSG_ERROR,
    MSG_DOCUMENT_SYNC, MSG_USER_LIST,
})


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

class Document:
    """A document stored as a list of lines."""

    def __init__(self, text: str = ""):
        if text:
            self.lines = text.split('\n')
        else:
            self.lines = [""]

    def get_text(self) -> str:
        return '\n'.join(self.lines)

    def get_line_count(self) -> int:
        return len(self.lines)

    def get_line(self, idx: int) -> str:
        if 0 <= idx < len(self.lines):
            return self.lines[idx]
        return ""

    def line_length(self, idx: int) -> int:
        if 0 <= idx < len(self.lines):
            return len(self.lines[idx])
        return 0

    def flat_pos_to_line_col(self, pos: int):
        """Convert a flat character position to (line, col)."""
        for line_idx, line in enumerate(self.lines):
            if pos <= len(line):
                return line_idx, pos
            pos -= len(line) + 1  # +1 for the newline
        # Position beyond end – clamp to last line
        last = len(self.lines) - 1
        return last, len(self.lines[last])

    def line_col_to_flat_pos(self, line: int, col: int) -> int:
        """Convert (line, col) to a flat character position."""
        line = max(0, min(line, len(self.lines) - 1))
        col = max(0, min(col, len(self.lines[line])))
        pos = 0
        for i in range(line):
            pos += len(self.lines[i]) + 1
        pos += col
        return pos

    def insert(self, flat_pos: int, char: str) -> int:
        """
        Insert a character at flat_pos.
        Returns the actual flat_pos used (clamped).
        """
        line, col = self.flat_pos_to_line_col(flat_pos)
        if char == '\n':
            rest = self.lines[line][col:]
            self.lines[line] = self.lines[line][:col]
            self.lines.insert(line + 1, rest)
        else:
            self.lines[line] = self.lines[line][:col] + char + self.lines[line][col:]
        return flat_pos

    def delete(self, flat_pos: int) -> Optional[str]:
        """
        Delete the character at flat_pos.
        Returns the deleted character, or None if nothing was deleted.
        """
        line, col = self.flat_pos_to_line_col(flat_pos)
        if line >= len(self.lines):
            return None
        if col < len(self.lines[line]):
            deleted = self.lines[line][col]
            self.lines[line] = self.lines[line][:col] + self.lines[line][col + 1:]
            return deleted
        else:
            # col == len(line) – delete the newline, join with next line
            if line + 1 < len(self.lines):
                self.lines[line] = self.lines[line] + self.lines[line + 1]
                del self.lines[line + 1]
                return '\n'
            return None

    def apply_op(self, op: dict) -> Optional[str]:
        """
        Apply an operation dict to this document.
        Returns the deleted character for delete ops, or None.
        """
        if op['op_type'] == 'insert':
            self.insert(op['flat_pos'], op['char'])
            return None
        elif op['op_type'] == 'delete':
            return self.delete(op['flat_pos'])
        return None

    def clone(self) -> 'Document':
        d = Document()
        d.lines = list(self.lines)
        return d


# ---------------------------------------------------------------------------
# Operational Transformation
# ---------------------------------------------------------------------------

def transform(op_a: dict, op_b: dict) -> Optional[dict]:
    """
    Transform op_a against op_b (which happened concurrently before op_a).
    Both operations are dicts with keys: op_type, flat_pos, [char].
    Returns a new operation dict (or None if op_a becomes a no-op).
    
    This implements standard OT transformation rules on flat positions.
    """
    a = dict(op_a)  # copy
    b = op_b

    if a['op_type'] == 'insert' and b['op_type'] == 'insert':
        if a['flat_pos'] > b['flat_pos']:
            a['flat_pos'] += 1
        elif a['flat_pos'] == b['flat_pos']:
            # Tie-break: lower char goes first (arbitrary but deterministic).
            # Actually, let the one with the smaller character win.
            # But we need determinism. Use the character values.
            if a.get('char', '') > b.get('char', ''):
                a['flat_pos'] += 1
            # else a stays, b would have been shifted if we were transforming b
        # else a['flat_pos'] < b['flat_pos']: no change

    elif a['op_type'] == 'insert' and b['op_type'] == 'delete':
        if a['flat_pos'] > b['flat_pos']:
            a['flat_pos'] -= 1
        # else: no change (insert is before or at delete point)

    elif a['op_type'] == 'delete' and b['op_type'] == 'insert':
        if a['flat_pos'] >= b['flat_pos']:
            a['flat_pos'] += 1
        # else: no change

    elif a['op_type'] == 'delete' and b['op_type'] == 'delete':
        if a['flat_pos'] > b['flat_pos']:
            a['flat_pos'] -= 1
        elif a['flat_pos'] == b['flat_pos']:
            return None  # already deleted, becomes no-op

    return a


def transform_against_list(op: dict, ops: list) -> Optional[dict]:
    """
    Transform op against a list of concurrent operations (in order).
    Returns the transformed op or None if it becomes a no-op.
    """
    result = dict(op)
    for other in ops:
        if result is None:
            return None
        result = transform(result, other)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_message(msg_type: str, **kwargs) -> bytes:
    """Create a JSON message with a type field, terminated by newline."""
    msg = {"type": msg_type}
    msg.update(kwargs)
    return (json.dumps(msg) + '\n').encode('utf-8')


def parse_message(data: bytes) -> Optional[dict]:
    """Parse a JSON message from bytes. Returns None on failure."""
    try:
        return json.loads(data.decode('utf-8').strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
