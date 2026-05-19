"""Helper functions: type converters, condition parser, comparisons."""

import re
from datetime import date, datetime

# Common date formats to try
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y%m%d",
]


def try_parse_numeric(value: str):
    """Try to parse a string as int or float.  Returns the number or None."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    # Try int first
    try:
        return int(stripped)
    except (ValueError, OverflowError):
        pass
    # Try float
    try:
        return float(stripped)
    except (ValueError, OverflowError):
        pass
    return None


def try_parse_date(value: str):
    """Try to parse a string as a date.  Returns a date object or None."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(stripped, fmt)
            return dt.date()
        except (ValueError, OverflowError):
            continue
    # Try ISO-like with time component
    try:
        # Handle '2021-03-14T00:00:00' etc.
        dt = datetime.fromisoformat(stripped)
        return dt.date()
    except (ValueError, OverflowError, TypeError):
        pass
    return None


def _find_op(condition_str: str):
    """Find the comparison operator in a condition string.
    Returns (col, op, value) or None."""
    # Operators in descending length to match >= before >, etc.
    ops = ["!=", ">=", "<=", "==", ">", "<"]
    for op in ops:
        idx = condition_str.find(op)
        if idx >= 0:
            col = condition_str[:idx].strip()
            val = condition_str[idx + len(op):].strip()
            if col and val:
                # Remove quotes around value if present
                if len(val) >= 2 and (
                    (val.startswith('"') and val.endswith('"'))
                    or (val.startswith("'") and val.endswith("'"))
                ):
                    val = val[1:-1]
                return (col, op, val)
    return None


def parse_condition(condition_str: str):
    """Parse a condition string like 'age>30' into ('age', '>', '30')."""
    if not condition_str or not condition_str.strip():
        return None
    parsed = _find_op(condition_str.strip())
    if parsed is None:
        raise ValueError(
            f"Invalid condition: '{condition_str}'. "
            f"Expected format: 'column op value' (e.g. 'age>30')."
        )
    return parsed


def safe_compare(a, op: str, b):
    """Type-coerced comparison between two values (strings or numbers)."""
    # Try numeric comparison
    num_a = try_parse_numeric(str(a)) if a is not None else None
    num_b = try_parse_numeric(str(b)) if b is not None else None
    if num_a is not None and num_b is not None:
        a_val, b_val = num_a, num_b
    else:
        # String comparison
        a_val = str(a) if a is not None else ""
        b_val = str(b) if b is not None else ""

    if op == ">":
        return a_val > b_val
    elif op == "<":
        return a_val < b_val
    elif op == ">=":
        return a_val >= b_val
    elif op == "<=":
        return a_val <= b_val
    elif op == "==":
        return a_val == b_val
    elif op == "!=":
        return a_val != b_val
    else:
        raise ValueError(f"Unknown operator: '{op}'")


def matches_condition(row: dict, headers: list, condition) -> bool:
    """Evaluate a parsed condition on a row (dict keyed by header)."""
    if condition is None:
        return True
    col, op, val = condition
    if col not in headers:
        # Column doesn't exist – can't match
        return False
    cell = row.get(col, "")
    return safe_compare(cell, op, val)
