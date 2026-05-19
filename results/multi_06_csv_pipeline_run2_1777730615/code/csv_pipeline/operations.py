"""Filtering, sorting, and joining operations on datasets."""

import re

# Pattern for filter expressions: column operator value
# e.g. "age>30", "name==John", "price<=9.99"
FILTER_PATTERN = re.compile(r"^(.+?)\s*(<=|>=|!=|==|<|>)\s*(.+)$")


def _try_number(s: str) -> int | float | str:
    """Attempt to convert string to int or float; fall back to string."""
    s = s.strip().strip('"').strip("'")
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _compare(row_value: str, op: str, literal_str: str) -> bool:
    """Compare a row value against a literal using the given operator.

    If both sides can be numeric, numeric comparison is used;
    otherwise string comparison.
    """
    row_val = row_value.strip()
    target_val = _try_number(literal_str)

    # Determine if we should do numeric comparison
    if isinstance(target_val, (int, float)):
        # Missing/empty values never satisfy numeric filters
        if row_val == "":
            return False
        try:
            row_num = float(row_val)
            if op == ">":
                return row_num > target_val
            elif op == "<":
                return row_num < target_val
            elif op == ">=":
                return row_num >= target_val
            elif op == "<=":
                return row_num <= target_val
            elif op == "==":
                return row_num == target_val
            elif op == "!=":
                return row_num != target_val
        except (ValueError, TypeError):
            pass  # fall through to string comparison

    # String comparison
    target_str = literal_str.strip().strip('"').strip("'")
    if op == ">":
        return row_val > target_str
    elif op == "<":
        return row_val < target_str
    elif op == ">=":
        return row_val >= target_str
    elif op == "<=":
        return row_val <= target_str
    elif op == "==":
        return row_val == target_str
    elif op == "!=":
        return row_val != target_str

    return False


def filter_rows(rows: list[dict], expression: str) -> list[dict]:
    """Filter rows based on a column value condition.

    Expression format: "column operator value"
    Supported operators: ==, !=, <, >, <=, >=

    Returns a new filtered list.
    """
    m = FILTER_PATTERN.match(expression.strip())
    if not m:
        print(f"Warning: Invalid filter expression '{expression}'. Ignoring filter.", flush=True)
        return rows

    col, op, val = m.group(1).strip().strip('"'), m.group(2), m.group(3)
    return [row for row in rows if col in row and _compare(row.get(col, ""), op, val)]


def sort_rows(rows: list[dict], column_key: str, column_types: dict | None = None) -> list[dict]:
    """Sort rows by the given column.

    If the column type (from column_types dict) is int/float, numeric sort is used.
    Otherwise case-insensitive string sort.
    """
    col_type = None
    if column_types:
        col_type = column_types.get(column_key, "text")

    if col_type in ("int", "float"):
        def key_fn(row):
            v = row.get(column_key, "").strip()
            try:
                return float(v)
            except (ValueError, TypeError):
                return float("-inf")
    else:
        def key_fn(row):
            v = row.get(column_key, "").strip()
            return v.lower()

    return sorted(rows, key=key_fn)


def join_datasets(left_rows: list[dict], right_rows: list[dict], key_column: str) -> list[dict]:
    """Inner join two datasets on the given key column.

    Left row values take precedence on column name collisions.
    """
    # Build lookup: key_value -> list of right rows
    right_index: dict[str, list[dict]] = {}
    for row in right_rows:
        key = row.get(key_column, "").strip()
        right_index.setdefault(key, []).append(row)

    result = []
    total_matched = 0
    for left_row in left_rows:
        key = left_row.get(key_column, "").strip()
        matches = right_index.get(key, [])
        if matches:
            total_matched += 1
        for right_row in matches:
            # Merge: right columns added, left values take precedence
            merged = dict(right_row)  # start with right
            merged.update(left_row)   # left overwrites
            result.append(merged)

    if total_matched == 0:
        print("Warning: Join produced no matching rows. All left rows dropped.", flush=True)

    return result
