#!/usr/bin/env python3
"""Unit tests for Operational Transformation."""

from ot import (
    transform,
    transform_against_list,
    transform_cursor,
    apply_operation,
    inverse_operation,
    flat_to_line_col,
    line_col_to_flat,
)


def test_transform_insert_insert_different_pos():
    # op at lower position stays
    result = transform(
        {'type': 'insert', 'position': 3, 'char': 'a'},
        {'type': 'insert', 'position': 5, 'char': 'b'},
    )
    assert result == {'type': 'insert', 'position': 3, 'char': 'a'}, f"Got {result}"


def test_transform_insert_insert_op_after():
    # op at higher position shifts
    result = transform(
        {'type': 'insert', 'position': 5, 'char': 'a'},
        {'type': 'insert', 'position': 3, 'char': 'b'},
    )
    assert result == {'type': 'insert', 'position': 6, 'char': 'a'}, f"Got {result}"


def test_transform_insert_insert_same_pos_tiebreaker():
    # Same position: 'a' <= 'b' so 'a' stays
    result = transform(
        {'type': 'insert', 'position': 5, 'char': 'a'},
        {'type': 'insert', 'position': 5, 'char': 'b'},
    )
    assert result == {'type': 'insert', 'position': 5, 'char': 'a'}, f"Got {result}"

    # Reverse: 'b' > 'a' so 'b' shifts
    result = transform(
        {'type': 'insert', 'position': 5, 'char': 'b'},
        {'type': 'insert', 'position': 5, 'char': 'a'},
    )
    assert result == {'type': 'insert', 'position': 6, 'char': 'b'}, f"Got {result}"


def test_transform_insert_delete():
    # Insert before delete: stays
    result = transform(
        {'type': 'insert', 'position': 3, 'char': 'x'},
        {'type': 'delete', 'position': 5},
    )
    assert result == {'type': 'insert', 'position': 3, 'char': 'x'}, f"Got {result}"

    # Insert at delete position: stays (insert goes before delete)
    result = transform(
        {'type': 'insert', 'position': 5, 'char': 'x'},
        {'type': 'delete', 'position': 5},
    )
    assert result == {'type': 'insert', 'position': 5, 'char': 'x'}, f"Got {result}"

    # Insert after delete: shifts back
    result = transform(
        {'type': 'insert', 'position': 7, 'char': 'x'},
        {'type': 'delete', 'position': 5},
    )
    assert result == {'type': 'insert', 'position': 6, 'char': 'x'}, f"Got {result}"


def test_transform_delete_insert():
    # Delete before insert: stays
    result = transform(
        {'type': 'delete', 'position': 3},
        {'type': 'insert', 'position': 5, 'char': 'x'},
    )
    assert result == {'type': 'delete', 'position': 3}, f"Got {result}"

    # Delete at insert position: shifts forward
    result = transform(
        {'type': 'delete', 'position': 5},
        {'type': 'insert', 'position': 5, 'char': 'x'},
    )
    assert result == {'type': 'delete', 'position': 6}, f"Got {result}"

    # Delete after insert: shifts forward
    result = transform(
        {'type': 'delete', 'position': 7},
        {'type': 'insert', 'position': 5, 'char': 'x'},
    )
    assert result == {'type': 'delete', 'position': 8}, f"Got {result}"


def test_transform_delete_delete():
    # Different positions: lower stays, higher shifts back
    result = transform(
        {'type': 'delete', 'position': 3},
        {'type': 'delete', 'position': 5},
    )
    assert result == {'type': 'delete', 'position': 3}, f"Got {result}"

    result = transform(
        {'type': 'delete', 'position': 5},
        {'type': 'delete', 'position': 3},
    )
    assert result == {'type': 'delete', 'position': 4}, f"Got {result}"

    # Same position: voided
    result = transform(
        {'type': 'delete', 'position': 5},
        {'type': 'delete', 'position': 5},
    )
    assert result is None, f"Got {result}"


def test_convergence_insert_insert():
    """Test that concurrent inserts at same position converge."""
    op_a = {'type': 'insert', 'position': 0, 'char': 'a'}
    op_b = {'type': 'insert', 'position': 0, 'char': 'b'}

    # Path 1: a first, then transform b
    doc1 = apply_operation('', op_a)
    b_transformed = transform(op_b, op_a)
    doc1 = apply_operation(doc1, b_transformed)

    # Path 2: b first, then transform a
    doc2 = apply_operation('', op_b)
    a_transformed = transform(op_a, op_b)
    doc2 = apply_operation(doc2, a_transformed)

    assert doc1 == doc2, f"Convergence failed: '{doc1}' vs '{doc2}'"
    # 'a' <= 'b' so 'a' goes first, result should be 'ab'
    assert doc1 == 'ab', f"Expected 'ab', got '{doc1}'"


def test_convergence_insert_delete():
    """Test that concurrent insert and delete at same position converge."""
    op_ins = {'type': 'insert', 'position': 1, 'char': 'x'}
    op_del = {'type': 'delete', 'position': 1}

    doc_start = 'abc'

    # Path 1: insert first, then delete
    doc1 = apply_operation(doc_start, op_ins)
    del_transformed = transform(op_del, op_ins)
    doc1 = apply_operation(doc1, del_transformed)

    # Path 2: delete first, then insert
    doc2 = apply_operation(doc_start, op_del)
    ins_transformed = transform(op_ins, op_del)
    doc2 = apply_operation(doc2, ins_transformed)

    assert doc1 == doc2, f"Convergence failed: '{doc1}' vs '{doc2}'"
    # insert 'x' at 1, delete at 1 -> "axc"
    assert doc1 == 'axc', f"Expected 'axc', got '{doc1}'"


def test_transform_against_list():
    ops = [
        {'type': 'insert', 'position': 0, 'char': 'a'},
        {'type': 'insert', 'position': 1, 'char': 'b'},
    ]
    op = {'type': 'insert', 'position': 0, 'char': 'c'}
    result = transform_against_list(op, ops)
    # c at 0 vs a at 0: c > a -> c at 1
    # c at 1 vs b at 1: c > b -> c at 2
    assert result == {'type': 'insert', 'position': 2, 'char': 'c'}, f"Got {result}"


def test_cursor_transform():
    # Insert before cursor: cursor shifts right
    assert transform_cursor(5, {'type': 'insert', 'position': 3, 'char': 'x'}) == 6
    # Insert after cursor: cursor unchanged
    assert transform_cursor(5, {'type': 'insert', 'position': 7, 'char': 'x'}) == 5
    # Insert at cursor: cursor shifts right
    assert transform_cursor(5, {'type': 'insert', 'position': 5, 'char': 'x'}) == 6
    # Delete before cursor: cursor shifts left
    assert transform_cursor(5, {'type': 'delete', 'position': 3}) == 4
    # Delete after cursor: cursor unchanged
    assert transform_cursor(5, {'type': 'delete', 'position': 7}) == 5
    # Delete at cursor: cursor unchanged (cursor is after the deleted char)
    assert transform_cursor(5, {'type': 'delete', 'position': 5}) == 5


def test_flat_line_col_conversion():
    text = "hello\nworld\nfoo"
    # Basic positions
    assert flat_to_line_col(text, 0) == (0, 0)
    assert flat_to_line_col(text, 5) == (0, 5)
    assert flat_to_line_col(text, 6) == (1, 0)  # after first newline
    assert flat_to_line_col(text, 12) == (2, 0)
    assert flat_to_line_col(text, 15) == (2, 3)

    # Round-trip
    for pos in range(len(text) + 1):
        r, c = flat_to_line_col(text, pos)
        assert line_col_to_flat(text, r, c) == pos, f"Mismatch at pos {pos}: ({r},{c})"


def test_inverse_operation():
    # Insert inverse is delete
    inv = inverse_operation({'type': 'insert', 'position': 5, 'char': 'x'})
    assert inv == {'type': 'delete', 'position': 5}, f"Got {inv}"

    # Delete inverse is insert with char
    inv = inverse_operation({'type': 'delete', 'position': 5}, deleted_char='z')
    assert inv == {'type': 'insert', 'position': 5, 'char': 'z'}, f"Got {inv}"


if __name__ == '__main__':
    tests = [
        test_transform_insert_insert_different_pos,
        test_transform_insert_insert_op_after,
        test_transform_insert_insert_same_pos_tiebreaker,
        test_transform_insert_delete,
        test_transform_delete_insert,
        test_transform_delete_delete,
        test_convergence_insert_insert,
        test_convergence_insert_delete,
        test_transform_against_list,
        test_cursor_transform,
        test_flat_line_col_conversion,
        test_inverse_operation,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    exit(0 if failed == 0 else 1)
