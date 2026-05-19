"""
ot.py — Operational Transformation for collaborative text editing.

Treats the document as a flat character string (newlines are '\\n').
Operations:
  - insert(pos, text): insert text at offset pos
  - delete(pos, length): delete length characters starting at pos

Key functions:
  - transform(op1, op2, tie_breaker) → op1': op1 transformed against op2
  - apply_operation(doc, op) → new_doc
  - inverse(op, doc_at_time) → op_inv: operation that undoes op
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
import copy


# ── Operation representation ───────────────────────────────────────────────

@dataclass
class OTMessage:
    """Internal OT operation representation (simpler than protocol.Operation)."""
    op_type: str        # "insert" or "delete"
    position: int       # character offset
    text: str = ""      # for insert
    length: int = 0     # for delete
    client_id: str = ""
    seq_no: int = 0

    def __post_init__(self):
        if self.op_type == "insert":
            self.length = len(self.text)
        elif self.op_type == "delete":
            self.text = ""


# ── Transformation ─────────────────────────────────────────────────────────

def transform(op1: OTMessage, op2: OTMessage,
              tie_breaker: Callable[[], int] = lambda: 0) -> OTMessage:
    """
    Transform op1 against op2, returning op1' such that:
        apply(op2, apply(op1, doc)) == apply(op1', apply(op2, doc))

    tie_breaker returns:
      - negative if op1 should go before op2 when they conflict
      - positive if op1 should go after op2
      - 0 for default (compare client_id strings)
    """
    op1 = copy.deepcopy(op1)
    op2 = copy.deepcopy(op2)

    if op1.op_type == "insert" and op2.op_type == "insert":
        return _transform_insert_insert(op1, op2, tie_breaker)
    elif op1.op_type == "insert" and op2.op_type == "delete":
        return _transform_insert_delete(op1, op2)
    elif op1.op_type == "delete" and op2.op_type == "insert":
        return _transform_delete_insert(op1, op2)
    elif op1.op_type == "delete" and op2.op_type == "delete":
        return _transform_delete_delete(op1, op2)
    else:
        raise ValueError(f"Unknown op types: {op1.op_type}, {op2.op_type}")


def _transform_insert_insert(op1: OTMessage, op2: OTMessage,
                              tie_breaker: Callable[[], int]) -> OTMessage:
    """
    Both insert. If positions differ, just adjust position.
    If same position, use tie-breaker to decide which goes first.
    """
    if op1.position < op2.position:
        # op1 is before op2; no change to op1 position
        return op1
    elif op1.position > op2.position:
        # op1 is after op2; shift op1 right by op2's insertion length
        op1.position += len(op2.text)
        return op1
    else:
        # Same position. Use tie-breaker.
        tb = tie_breaker()
        if tb == 0:
            # Default: compare client_id strings, then seq_no
            if op1.client_id < op2.client_id:
                tb = -1
            elif op1.client_id > op2.client_id:
                tb = 1
            else:
                tb = -1 if op1.seq_no < op2.seq_no else 1
        if tb < 0:
            # op1 goes first; op2 shifts op1
            op1.position += len(op2.text)
            return op1
        else:
            # op1 goes after op2; no shift
            return op1


def _transform_insert_delete(op1: OTMessage, op2: OTMessage) -> OTMessage:
    """op1 is insert, op2 is delete."""
    if op1.position <= op2.position:
        # Insert is before or at start of delete; no shift
        return op1
    elif op1.position > op2.position + op2.length:
        # Insert is after the deleted region; shift left by delete length
        op1.position -= op2.length
        return op1
    else:
        # Insert is inside the deleted region; shift to start of deletion
        op1.position = op2.position
        return op1


def _transform_delete_insert(op1: OTMessage, op2: OTMessage) -> OTMessage:
    """op1 is delete, op2 is insert."""
    if op1.position >= op2.position:
        # Delete starts at or after insert; shift right by insert length
        op1.position += len(op2.text)
    # If delete is entirely before insert, no change.
    # If delete spans across insert, expand to include the inserted text
    if op1.position < op2.position and op1.position + op1.length >= op2.position:
        op1.length += len(op2.text)
    return op1


def _transform_delete_delete(op1: OTMessage, op2: OTMessage) -> OTMessage:
    """Both are deletes."""
    if op2.position >= op1.position + op1.length:
        # op2 is entirely after op1; no change
        return op1
    elif op1.position >= op2.position + op2.length:
        # op1 is entirely after op2; shift left by op2's length
        op1.position -= op2.length
        return op1
    else:
        # Overlapping deletes
        # The part of op1 that overlaps op2 is removed
        if op1.position >= op2.position:
            # op1 starts within or after op2
            overlap_end = min(op1.position + op1.length,
                              op2.position + op2.length)
            new_len = op1.length - (overlap_end - op1.position)
            op1.position = op2.position
            op1.length = max(0, new_len)
        else:
            # op1 starts before op2
            overlap_start = op2.position
            overlap_end = min(op1.position + op1.length,
                              op2.position + op2.length)
            new_len = op1.length - (overlap_end - overlap_start)
            op1.length = max(0, new_len)
        return op1


# ── Apply ──────────────────────────────────────────────────────────────────

def apply_operation(document: str, op: OTMessage) -> str:
    """Apply an operation to a flat string document."""
    if op.op_type == "insert":
        return document[:op.position] + op.text + document[op.position:]
    elif op.op_type == "delete":
        if op.length == 0:
            return document
        return document[:op.position] + document[op.position + op.length:]
    else:
        raise ValueError(f"Unknown op type: {op.op_type}")


# ── Inverse ────────────────────────────────────────────────────────────────

def inverse(op: OTMessage, original_doc: str) -> OTMessage:
    """
    Compute the inverse of an operation.
    Given document state BEFORE op was applied, return the operation
    that undoes it.
    """
    if op.op_type == "insert":
        return OTMessage(
            op_type="delete",
            position=op.position,
            length=len(op.text),
            client_id=op.client_id,
            seq_no=op.seq_no,
        )
    elif op.op_type == "delete":
        # The deleted text is in the original document at op.position
        deleted_text = original_doc[op.position:op.position + op.length]
        return OTMessage(
            op_type="insert",
            position=op.position,
            text=deleted_text,
            client_id=op.client_id,
            seq_no=op.seq_no,
        )
    else:
        raise ValueError(f"Unknown op type: {op.op_type}")


# ── Utility ────────────────────────────────────────────────────────────────

def offset_to_line_col(document: str, offset: int):
    """Convert a character offset to (line, col) 0-indexed."""
    if offset < 0:
        offset = 0
    if offset > len(document):
        offset = len(document)
    text_before = document[:offset]
    line = text_before.count('\n')
    last_newline = text_before.rfind('\n')
    if last_newline == -1:
        col = offset
    else:
        col = offset - last_newline - 1
    return line, col


def line_col_to_offset(document: str, line: int, col: int) -> int:
    """Convert (line, col) 0-indexed to character offset."""
    lines = document.split('\n')
    if line >= len(lines):
        return len(document)
    offset = 0
    for i in range(line):
        offset += len(lines[i]) + 1  # +1 for the newline
    # Clamp col to line length
    col = max(0, min(col, len(lines[line])))
    return offset + col


def operation_to_otmessage(op) -> OTMessage:
    """Convert protocol.Operation or dict to OTMessage."""
    if hasattr(op, 'op_type'):
        return OTMessage(
            op_type=op.op_type,
            position=op.position,
            text=getattr(op, 'text', ''),
            length=getattr(op, 'length', 0),
            client_id=getattr(op, 'client_id', ''),
            seq_no=getattr(op, 'seq_no', 0),
        )
    else:
        return OTMessage(
            op_type=op['op_type'],
            position=op['position'],
            text=op.get('text', ''),
            length=op.get('length', 0),
            client_id=op.get('client_id', ''),
            seq_no=op.get('seq_no', 0),
        )


# ── Tests ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run some basic tests
    doc = "hello world\nfoo bar\nbaz"

    # Test insert
    op = OTMessage("insert", 0, text="ABC", client_id="a", seq_no=1)
    doc2 = apply_operation(doc, op)
    assert doc2 == "ABChello world\nfoo bar\nbaz", f"Got: {doc2!r}"

    # Test delete
    op2 = OTMessage("delete", 0, length=3, client_id="b", seq_no=1)
    doc3 = apply_operation(doc2, op2)
    assert doc3 == "hello world\nfoo bar\nbaz", f"Got: {doc3!r}"

    # Test transform: both insert at same position
    op_a = OTMessage("insert", 0, text="AAA", client_id="a", seq_no=1)
    op_b = OTMessage("insert", 0, text="BBB", client_id="b", seq_no=1)
    op_a_t = transform(op_a, op_b)
    assert op_a_t.position == 3, f"Expected 3, got {op_a_t.position}"  # a < b, so a shifts right

    # Test transform: insert before delete
    op_ins = OTMessage("insert", 5, text="XXX", client_id="a", seq_no=1)
    op_del = OTMessage("delete", 10, length=3, client_id="b", seq_no=1)
    op_ins_t = transform(op_ins, op_del)
    assert op_ins_t.position == 5  # before delete, unchanged

    # Test transform: insert inside delete region
    op_ins = OTMessage("insert", 11, text="YYY", client_id="a", seq_no=1)
    op_del = OTMessage("delete", 10, length=5, client_id="b", seq_no=1)
    op_ins_t = transform(op_ins, op_del)
    assert op_ins_t.position == 10  # pushed to start of delete

    # Test inverse
    orig = "hello world"
    ins = OTMessage("insert", 5, text="XXX", client_id="a", seq_no=1)
    after = apply_operation(orig, ins)
    assert after == "helloXXX world"
    inv = inverse(ins, orig)
    after_inv = apply_operation(after, inv)
    assert after_inv == orig, f"Got: {after_inv!r}"

    # Test delete inverse
    orig2 = "hello world"
    d = OTMessage("delete", 5, length=1, client_id="a", seq_no=1)
    after2 = apply_operation(orig2, d)
    assert after2 == "helloworld"
    inv2 = inverse(d, orig2)
    after_inv2 = apply_operation(after2, inv2)
    assert after_inv2 == orig2, f"Got: {after_inv2!r}"

    # Test offset/line/col conversion
    doc = "ab\ncd\nef"
    assert offset_to_line_col(doc, 0) == (0, 0)
    assert offset_to_line_col(doc, 3) == (1, 0)  # 'c' is at line 1, col 0
    assert offset_to_line_col(doc, 4) == (1, 1)
    assert line_col_to_offset(doc, 0, 0) == 0
    assert line_col_to_offset(doc, 1, 1) == 4
    assert line_col_to_offset(doc, 0, 2) == 2

    print("All OT tests passed!")
