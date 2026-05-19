"""Operational Transformation for collaborative text editing.

Implements the core OT functions for transforming insert/delete operations
against each other when they occur concurrently.
"""


def transform(op, against):
    """Transform op against another operation.

    Both op and against are assumed to be based on the same document state.
    Returns a new op that can be applied after against, or None if op is voided.

    Args:
        op: {'type': 'insert'|'delete', 'position': int, 'char': str (for insert)}
        against: same format

    Returns:
        Transformed operation dict, or None if the operation becomes a no-op.
    """
    op_type = op['type']
    against_type = against['type']
    op_pos = op['position']
    against_pos = against['position']

    if op_type == 'insert' and against_type == 'insert':
        if op_pos < against_pos:
            return dict(op)
        elif op_pos > against_pos:
            return {'type': 'insert', 'position': op_pos + 1, 'char': op['char']}
        else:
            # Same position: use character as deterministic tiebreaker.
            # Smaller character (by ord) goes first. This ensures
            # transform(A,B) and transform(B,A) are consistent.
            if op['char'] <= against['char']:
                # op goes first, stays at same position
                return dict(op)
            else:
                # op goes after against, shifts by 1
                return {'type': 'insert', 'position': op_pos + 1, 'char': op['char']}

    elif op_type == 'insert' and against_type == 'delete':
        if op_pos <= against_pos:
            return dict(op)
        else:
            return {'type': 'insert', 'position': op_pos - 1, 'char': op['char']}

    elif op_type == 'delete' and against_type == 'insert':
        if op_pos < against_pos:
            return dict(op)
        else:
            return {'type': 'delete', 'position': op_pos + 1}

    elif op_type == 'delete' and against_type == 'delete':
        if op_pos < against_pos:
            return dict(op)
        elif op_pos > against_pos:
            return {'type': 'delete', 'position': op_pos - 1}
        else:
            # Both delete the same character — second delete is a no-op
            return None

    return dict(op)


def transform_against_list(op, ops):
    """Transform op against a list of concurrent operations in order.

    Args:
        op: The operation to transform.
        ops: List of operations to transform against (oldest first).

    Returns:
        Transformed operation or None if voided.
    """
    result = dict(op)
    for other in ops:
        result = transform(result, other)
        if result is None:
            return None
    return result


def transform_cursor(cursor_pos, op):
    """Adjust a cursor position when an operation is applied.

    Args:
        cursor_pos: Integer position in the document.
        op: The operation being applied.

    Returns:
        New cursor position after the operation.
    """
    op_type = op['type']
    op_pos = op['position']

    if op_type == 'insert':
        if cursor_pos >= op_pos:
            return cursor_pos + 1
        return cursor_pos
    elif op_type == 'delete':
        if cursor_pos > op_pos:
            return cursor_pos - 1
        return cursor_pos
    return cursor_pos


def apply_operation(document, op):
    """Apply an operation to a document string.

    Args:
        document: The document as a string.
        op: The operation to apply.

    Returns:
        The new document string.
    """
    if op is None:
        return document
    if op['type'] == 'insert':
        pos = op['position']
        char = op['char']
        return document[:pos] + char + document[pos:]
    elif op['type'] == 'delete':
        pos = op['position']
        if 0 <= pos < len(document):
            return document[:pos] + document[pos + 1:]
        return document
    return document


def inverse_operation(op, deleted_char=''):
    """Compute the inverse of an operation.

    Args:
        op: The operation to invert.
        deleted_char: The character that was deleted (for delete ops).

    Returns:
        The inverse operation.
    """
    if op['type'] == 'insert':
        return {'type': 'delete', 'position': op['position']}
    elif op['type'] == 'delete':
        return {'type': 'insert', 'position': op['position'], 'char': deleted_char}
    return None


def flat_to_line_col(text, pos):
    """Convert a flat position to (row, col) in a text string.

    Args:
        text: The document as a string.
        pos: Flat character position.

    Returns:
        (row, col) tuple. Row is 0-based, col is 0-based.
    """
    if pos <= 0:
        return 0, 0
    row = 0
    col = 0
    for i, ch in enumerate(text):
        if i >= pos:
            break
        if ch == '\n':
            row += 1
            col = 0
        else:
            col += 1
    return row, col


def line_col_to_flat(text, row, col):
    """Convert (row, col) to a flat position in a text string.

    Args:
        text: The document as a string.
        row: 0-based row.
        col: 0-based column.

    Returns:
        Flat position integer.
    """
    lines = text.split('\n')
    pos = 0
    for r in range(min(row, len(lines))):
        pos += len(lines[r]) + 1  # +1 for the newline
    # Clamp column to line length
    if row < len(lines):
        actual_col = min(col, len(lines[row]))
    else:
        actual_col = 0
    pos += actual_col
    return min(pos, len(text))
