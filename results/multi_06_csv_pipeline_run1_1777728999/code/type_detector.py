"""
Type Detector module – automatically infers column data types.
"""

from datetime import datetime
from typing import Any, Optional


# Common date formats to try
DATE_FORMATS = [
    '%Y-%m-%d',
    '%m/%d/%Y',
    '%d-%b-%Y',
    '%d/%m/%Y',
    '%Y/%m/%d',
    '%b %d, %Y',
    '%B %d, %Y',
    '%d-%m-%Y',
    '%Y-%m-%d %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S',
]


def _is_int(val: str) -> bool:
    """Check if a string can be parsed as an int."""
    try:
        int(val)
        return True
    except (ValueError, TypeError):
        return False


def _is_float(val: str) -> bool:
    """Check if a string can be parsed as a float."""
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def _try_parse_date(val: str) -> Optional[datetime]:
    """Try to parse a string as a date using common formats."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt)
        except (ValueError, TypeError):
            continue
    return None


def detect_column_type(values: list) -> str:
    """
    Determine the best-fitting type for a column based on its non-None values.

    Args:
        values: List of cell values (strings or None).

    Returns:
        One of: 'int', 'float', 'date', 'text'.
    """
    non_none = [v for v in values if v is not None]

    if not non_none:
        return 'text'  # empty column, default to text

    # Check int
    if all(_is_int(v) for v in non_none):
        return 'int'

    # Check float
    if all(_is_float(v) for v in non_none):
        # Check if any have decimal parts
        for v in non_none:
            fv = float(v)
            if fv != int(fv):
                return 'float'
        return 'int'

    # Check date (at least 80% match)
    date_count = sum(1 for v in non_none if _try_parse_date(v) is not None)
    if date_count / len(non_none) >= 0.8:
        return 'date'

    return 'text'


def detect_all_types(header: list, rows: list) -> dict:
    """
    Detect types for all columns in the dataset.

    Args:
        header: List of column names.
        rows: List of row dicts.

    Returns:
        Dict mapping column_name -> type_string ('int', 'float', 'date', 'text').
    """
    type_map = {}
    for col in header:
        values = [row.get(col) for row in rows]
        type_map[col] = detect_column_type(values)
    return type_map


def convert_value(value: Any, col_type: str) -> Any:
    """
    Convert a single cell value to its detected type.

    Args:
        value: The raw value (string or None).
        col_type: The detected column type.

    Returns:
        Converted value (int, float, datetime, str, or None).
    """
    if value is None:
        return None
    if col_type == 'int':
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    elif col_type == 'float':
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    elif col_type == 'date':
        dt = _try_parse_date(str(value))
        return dt if dt else None
    else:
        return str(value)


def convert_rows(header: list, rows: list, type_map: dict) -> list:
    """
    Convert all cell values in rows to their detected types.

    Args:
        header: List of column names.
        rows: List of row dicts with string values.
        type_map: Dict mapping column_name -> type_string.

    Returns:
        New list of row dicts with typed values.
    """
    converted = []
    for row in rows:
        new_row = {}
        for col in header:
            new_row[col] = convert_value(row.get(col), type_map.get(col, 'text'))
        converted.append(new_row)
    return converted
