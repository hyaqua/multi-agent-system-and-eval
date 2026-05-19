"""
String-based Operational Transformation engine.

Operations:
  {"op": "insert", "pos": int, "text": str}
  {"op": "delete", "pos": int, "text": str}  -- text is the deleted content

All functions are pure – they do not mutate their inputs.
"""

from copy import deepcopy


class Op:
    """Immutable-ish operation."""
    __slots__ = ("op", "pos", "text")

    def __init__(self, op: str, pos: int, text: str):
        if op not in ("insert", "delete"):
            raise ValueError(f"Unknown operation type: {op}")
        self.op = op
        self.pos = pos
        self.text = text

    def to_dict(self) -> dict:
        return {"op": self.op, "pos": self.pos, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "Op":
        return cls(d["op"], d["pos"], d["text"])

    def __repr__(self):
        return f"Op({self.op!r}, pos={self.pos}, text={self.text!r})"

    def copy(self) -> "Op":
        return Op(self.op, self.pos, self.text)


def apply_op(document: str, op: Op) -> str:
    """Apply an operation to a document string. Returns new string."""
    if op.op == "insert":
        return document[:op.pos] + op.text + document[op.pos:]
    else:  # delete
        end = op.pos + len(op.text)
        return document[:op.pos] + document[end:]


def invert(op: Op) -> Op:
    """Return the inverse of an operation.
    invert(apply(doc, op)) == doc  when applied after op.
    """
    if op.op == "insert":
        return Op("delete", op.pos, op.text)
    else:
        return Op("insert", op.pos, op.text)


def transform(op1: Op, op2: Op, side: str = "left") -> Op:
    """Transform op1 against op2 so that op1' applies after op2.

    Both op1 and op2 originate from the same document state.
    'side' indicates priority when both insert at the same position:
      - 'left':  op1 came first (server transforming client op against earlier ops)
                 Actually 'left' means op1 has priority at same position.
      - 'right': op2 has priority.

    Returns a new Op.
    """
    if op1.op == "insert" and op2.op == "insert":
        return _transform_ii(op1, op2, side)
    elif op1.op == "insert" and op2.op == "delete":
        return _transform_id(op1, op2)
    elif op1.op == "delete" and op2.op == "insert":
        return _transform_di(op1, op2)
    elif op1.op == "delete" and op2.op == "delete":
        return _transform_dd(op1, op2)
    else:
        raise ValueError(f"Unknown op types: {op1.op}, {op2.op}")


def _transform_ii(op1: Op, op2: Op, side: str) -> Op:
    """insert vs insert"""
    if op1.pos < op2.pos or (op1.pos == op2.pos and side == "left"):
        return op1.copy()
    else:
        return Op("insert", op1.pos + len(op2.text), op1.text)


def _transform_id(op1: Op, op2: Op) -> Op:
    """insert vs delete"""
    if op1.pos <= op2.pos:
        return op1.copy()
    elif op1.pos > op2.pos + len(op2.text):
        return Op("insert", op1.pos - len(op2.text), op1.text)
    else:
        # Insert position falls inside deleted range – place at start of deletion
        return Op("insert", op2.pos, op1.text)


def _transform_di(op1: Op, op2: Op) -> Op:
    """delete vs insert"""
    # op1 is the delete, op2 is the insert
    new_pos = op1.pos
    new_text = op1.text

    if op2.pos < op1.pos:
        new_pos += len(op2.text)
    elif op1.pos <= op2.pos < op1.pos + len(op1.text):
        # Insert falls inside the deleted range – the deleted text
        # should include the inserted text so it deletes it too.
        offset = op2.pos - op1.pos
        new_text = op1.text[:offset] + op2.text + op1.text[offset:]
    # else: op2.pos >= op1.pos + len(op1.text): no change

    return Op("delete", new_pos, new_text)


def _transform_dd(op1: Op, op2: Op) -> Op:
    """delete vs delete"""
    r1_start = op1.pos
    r1_end = op1.pos + len(op1.text)
    r2_start = op2.pos
    r2_end = op2.pos + len(op2.text)

    if r1_end <= r2_start:
        # op1 entirely before op2, no change
        return op1.copy()
    elif r1_start >= r2_end:
        # op1 entirely after op2, shift left
        return Op("delete", op1.pos - len(op2.text), op1.text)
    elif r1_start >= r2_start and r1_end <= r2_end:
        # op1 fully inside op2 – op1 becomes a no-op (delete empty)
        return Op("delete", r2_start, "")
    elif r1_start < r2_start and r1_end > r2_end:
        # op2 fully inside op1 – remove op2's range from op1
        prefix = op1.text[:r2_start - r1_start]
        suffix = op1.text[r2_end - r1_start:]
        return Op("delete", op1.pos, prefix + suffix)
    elif r1_start < r2_start and r1_end <= r2_end:
        # Overlap: op1 starts before op2, ends inside op2
        overlap = r1_end - r2_start
        new_text = op1.text[:-overlap]
        return Op("delete", op1.pos, new_text)
    else:  # r1_start >= r2_start and r1_end > r2_end
        # Overlap: op1 starts inside op2, ends after op2
        overlap = r2_end - r1_start
        new_text = op1.text[overlap:]
        return Op("delete", r2_start, new_text)


def compose(op1: Op, op2: Op) -> Op | None:
    """Try to compose two sequential ops into one. Returns None if not possible."""
    if op1.op == "insert" and op2.op == "insert":
        if op1.pos + len(op1.text) == op2.pos:
            return Op("insert", op1.pos, op1.text + op2.text)
    elif op1.op == "delete" and op2.op == "delete":
        if op1.pos == op2.pos:
            return Op("delete", op1.pos, op1.text + op2.text)
    return None
