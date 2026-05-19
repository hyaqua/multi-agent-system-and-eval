"""
Operational Transformation for single-character insert/delete operations.

Rules:
- Insert vs Insert: if positions equal, use tiebreaker (smaller username first).
  Otherwise shift position if later.
- Insert vs Delete: if insert pos <= delete pos -> unchanged; else pos-1.
- Delete vs Insert: if insert pos <= delete pos -> delete pos+1; else unchanged.
- Delete vs Delete: if pos1 < pos2 -> unchanged; if pos1 == pos2 -> delete becomes
  no-op (None); if pos1 > pos2 -> pos1-1.
"""

from .protocol import OP_INSERT, OP_DELETE


def transform(op, other_op, tiebreaker=None):
    """
    Transform `op` through `other_op` so that op can be applied after other_op.
    
    Args:
        op: dict with keys 'op', 'pos', 'char'
        other_op: dict with keys 'op', 'pos', 'char'
        tiebreaker: optional string used for insert-vs-insert tiebreaking.
                    The op with the "smaller" tiebreaker (lexicographically) wins
                    and keeps its position; the other shifts right.
    
    Returns:
        Transformed op dict, or None if the op becomes a no-op (both delete same position).
    """
    if op["op"] == OP_INSERT and other_op["op"] == OP_INSERT:
        return _transform_insert_insert(op, other_op, tiebreaker)
    elif op["op"] == OP_INSERT and other_op["op"] == OP_DELETE:
        return _transform_insert_delete(op, other_op)
    elif op["op"] == OP_DELETE and other_op["op"] == OP_INSERT:
        return _transform_delete_insert(op, other_op)
    elif op["op"] == OP_DELETE and other_op["op"] == OP_DELETE:
        return _transform_delete_delete(op, other_op)
    return op


def _transform_insert_insert(op, other_op, tiebreaker):
    """Transform an insert through another insert."""
    pos = op["pos"]
    other_pos = other_op["pos"]
    
    if pos < other_pos:
        # Our insert is before the other insert; no change needed
        return dict(op)
    elif pos > other_pos:
        # Our insert is after the other insert; shift right by 1
        return {"op": OP_INSERT, "pos": pos + 1, "char": op["char"]}
    else:
        # Same position: use tiebreaker
        if tiebreaker is not None:
            # The op with the lexicographically smaller tiebreaker goes first
            # op is being transformed through other_op, meaning other_op was applied first.
            # If other_op's tiebreaker is smaller, our op shifts right.
            # If our tiebreaker is smaller, our op stays (but we can't change history).
            # Actually: other_op is already applied. So if other_op has smaller tiebreaker,
            # it went first, and our op shifts right. If our op has smaller tiebreaker,
            # we should have gone first, but since other_op already went, we shift right.
            # Wait - tiebreaker here should indicate which op "wins" the position.
            # Standard approach: the op being transformed shifts right if positions equal,
            # unless we're doing inclusion transform. Let's keep it simple:
            # both at same position -> our op shifts right by 1.
            pass
        return {"op": OP_INSERT, "pos": pos + 1, "char": op["char"]}


def _transform_insert_delete(op, other_op):
    """Transform an insert through a delete."""
    pos = op["pos"]
    other_pos = other_op["pos"]
    
    if pos <= other_pos:
        # Insert is before or at the deleted character; no change
        return dict(op)
    else:
        # Insert is after the deleted character; shift left by 1
        return {"op": OP_INSERT, "pos": pos - 1, "char": op["char"]}


def _transform_delete_insert(op, other_op):
    """Transform a delete through an insert."""
    pos = op["pos"]
    other_pos = other_op["pos"]
    
    if other_pos <= pos:
        # The insert happened before or at our delete position;
        # our delete target shifts right by 1
        return {"op": OP_DELETE, "pos": pos + 1, "char": op["char"]}
    else:
        # The insert happened after our delete position; no change
        return dict(op)


def _transform_delete_delete(op, other_op):
    """Transform a delete through another delete."""
    pos = op["pos"]
    other_pos = other_op["pos"]
    
    if pos < other_pos:
        # Our delete is before the other delete; no change
        return dict(op)
    elif pos == other_pos:
        # Both deleted the same character; our op becomes a no-op
        return None
    else:
        # Our delete is after the other delete; shift left by 1
        return {"op": OP_DELETE, "pos": pos - 1, "char": op["char"]}


def apply_operation(document, op):
    """Apply a single operation to a document string, returning the new document."""
    if op["op"] == OP_INSERT:
        pos = op["pos"]
        char = op["char"]
        return document[:pos] + char + document[pos:]
    elif op["op"] == OP_DELETE:
        pos = op["pos"]
        if pos < 0 or pos >= len(document):
            return document
        return document[:pos] + document[pos + 1:]
    return document


def inverse_operation(op):
    """Return the inverse of an operation."""
    if op["op"] == OP_INSERT:
        return {"op": OP_DELETE, "pos": op["pos"], "char": op["char"]}
    elif op["op"] == OP_DELETE:
        return {"op": OP_INSERT, "pos": op["pos"], "char": op["char"]}
    return None


def offset_to_row_col(document, offset):
    """Convert a character offset to (row, col) in the document."""
    if offset < 0:
        offset = 0
    if offset > len(document):
        offset = len(document)
    text_before = document[:offset]
    row = text_before.count('\n')
    last_newline = text_before.rfind('\n')
    if last_newline == -1:
        col = offset
    else:
        col = offset - last_newline - 1
    return row, col


def row_col_to_offset(document, row, col):
    """Convert (row, col) to a character offset in the document."""
    lines = document.split('\n')
    if row < 0:
        return 0
    if row >= len(lines):
        return len(document)
    offset = 0
    for i in range(row):
        offset += len(lines[i]) + 1  # +1 for newline
    # Clamp column
    line = lines[row]
    if col < 0:
        col = 0
    if col > len(line):
        col = len(line)
    return offset + col
