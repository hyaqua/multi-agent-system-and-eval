"""
Operational Transformation for collaborative text editing.

Operations are single-character inserts and single-character deletes.
- insert: {'op': 'insert', 'pos': int, 'char': str}
- delete: {'op': 'delete', 'pos': int}

Transform takes two concurrent operations (op1 happened before op2 at the server)
and returns op2 transformed to be applied after op1.
"""


def transform(op1, op2):
    """Transform op2 against op1.
    
    op1 and op2 are concurrent operations. op1 was applied first at the server.
    Returns a new op2' that can be applied after op1, or None if op2 becomes a no-op.
    """
    if op1['op'] == 'insert':
        if op2['op'] == 'insert':
            # Two concurrent inserts
            if op1['pos'] <= op2['pos']:
                return {'op': 'insert', 'pos': op2['pos'] + 1, 'char': op2['char']}
            else:
                return op2.copy()
        elif op2['op'] == 'delete':
            # insert vs delete
            if op1['pos'] <= op2['pos']:
                return {'op': 'delete', 'pos': op2['pos'] + 1}
            else:
                return op2.copy()
    elif op1['op'] == 'delete':
        if op2['op'] == 'insert':
            # delete vs insert
            if op2['pos'] > op1['pos']:
                return {'op': 'insert', 'pos': op2['pos'] - 1, 'char': op2['char']}
            else:
                return op2.copy()
        elif op2['op'] == 'delete':
            # Two concurrent deletes
            if op1['pos'] < op2['pos']:
                return {'op': 'delete', 'pos': op2['pos'] - 1}
            elif op1['pos'] == op2['pos']:
                # Both deleted the same character - op2 becomes no-op
                return None
            else:
                return op2.copy()
    return op2.copy()


def transform_batch(ops, against_ops):
    """Transform a list of ops against a list of ops that happened before them.
    
    ops: the operations to transform (these are concurrent with against_ops)
    against_ops: the operations that happened first (in order)
    
    Returns the transformed ops (some may become None and are filtered out).
    """
    result = []
    for op in ops:
        current = op.copy()
        for against in against_ops:
            if current is None:
                break
            current = transform(against, current)
        if current is not None:
            result.append(current)
    return result


def apply_op(document, op):
    """Apply a single operation to a document string. Returns new string."""
    if op['op'] == 'insert':
        return document[:op['pos']] + op['char'] + document[op['pos']:]
    elif op['op'] == 'delete':
        if op['pos'] < len(document):
            return document[:op['pos']] + document[op['pos'] + 1:]
        return document
    return document


def apply_ops(document, ops):
    """Apply a list of operations in order. Returns new string."""
    for op in ops:
        document = apply_op(document, op)
    return document


def invert_op(document_before, op):
    """Compute the inverse of an operation given the document state before the op was applied."""
    if op['op'] == 'insert':
        return {'op': 'delete', 'pos': op['pos']}
    elif op['op'] == 'delete':
        if op['pos'] < len(document_before):
            char = document_before[op['pos']]
            return {'op': 'insert', 'pos': op['pos'], 'char': char}
        return None
    return None


def position_to_row_col(document, pos):
    """Convert an absolute position in the document string to (row, col)."""
    row = 0
    col = 0
    for i in range(pos):
        if i >= len(document):
            break
        if document[i] == '\n':
            row += 1
            col = 0
        else:
            col += 1
    return row, col


def row_col_to_position(document, row, col):
    """Convert (row, col) to absolute position in the document string."""
    lines = document.split('\n')
    pos = 0
    for i in range(min(row, len(lines))):
        pos += len(lines[i]) + 1  # +1 for newline
    pos += min(col, len(lines[row]) if row < len(lines) else 0)
    return pos
