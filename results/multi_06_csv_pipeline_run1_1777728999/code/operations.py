"""
Operations module – filtering, sorting, and joining rows.
"""

import operator
import re
from datetime import datetime
from typing import Any, Callable

from type_detector import convert_value, detect_all_types


# Operator mapping
OP_MAP = {
    '=': operator.eq,
    '==': operator.eq,
    '!=': operator.ne,
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
}


def _parse_filter_condition(condition: str) -> tuple:
    """
    Parse a filter condition string like 'age>30' or 'name=Alice'.

    Args:
        condition: Filter string, e.g. 'column>=value'.

    Returns:
        Tuple of (column_name, operator_str, value_str).

    Raises:
        ValueError: If the condition cannot be parsed.
    """
    # Match: column name (alphanumeric + underscores), operator, value
    pattern = r'^(\w[\w\s]*?)\s*(>=|<=|!=|==|[<>=])\s*(.+)$'
    match = re.match(pattern, condition.strip())
    if not match:
        raise ValueError(
            f"Invalid filter condition: '{condition}'. "
            f"Expected format: 'column>value', 'column=value', etc."
        )
    col_name = match.group(1).strip()
    op_str = match.group(2)
    value_str = match.group(3).strip()

    # Remove surrounding quotes if present
    if len(value_str) >= 2 and (
        (value_str.startswith('"') and value_str.endswith('"')) or
        (value_str.startswith("'") and value_str.endswith("'"))
    ):
        value_str = value_str[1:-1]

    return col_name, op_str, value_str


def filter_rows(rows: list, header: list, condition: str, type_map: dict = None) -> list:
    """
    Filter rows based on a condition string.

    Args:
        rows: List of row dicts (typed values).
        header: List of column names.
        condition: Filter string like 'age>30'.
        type_map: Dict mapping column_name -> type_string.

    Returns:
        Filtered list of row dicts.
    """
    col_name, op_str, value_str = _parse_filter_condition(condition)

    if col_name not in header:
        raise ValueError(f"Filter column '{col_name}' not found in data.")

    if type_map is None:
        type_map = detect_all_types(header, rows)

    col_type = type_map.get(col_name, 'text')
    target_value = convert_value(value_str, col_type)

    if op_str not in OP_MAP:
        raise ValueError(f"Unknown operator: '{op_str}'")

    op_func = OP_MAP[op_str]

    filtered = []
    for row in rows:
        cell_value = row.get(col_name)
        if cell_value is None:
            continue  # skip rows with None in filter column
        try:
            if op_func(cell_value, target_value):
                filtered.append(row)
        except TypeError:
            # Type mismatch, skip this row
            continue

    return filtered


def sort_rows(rows: list, header: list, sort_column: str, descending: bool = False) -> list:
    """
    Sort rows by a specified column.

    Args:
        rows: List of row dicts.
        header: List of column names.
        sort_column: Column name to sort by.
        descending: If True, sort in descending order.

    Returns:
        Sorted list of row dicts.

    Raises:
        ValueError: If sort column not found.
    """
    if sort_column not in header:
        raise ValueError(f"Sort column '{sort_column}' not found in data.")

    def sort_key(row):
        val = row.get(sort_column)
        if val is None:
            # Place None values at the end
            # Use a sentinel that will sort after everything
            if descending:
                return (1, None)  # None goes last even in descending
            else:
                return (1, None)  # None goes last
        return (0, val)

    return sorted(rows, key=sort_key, reverse=descending)


def join_csvs(
    primary_rows: list,
    primary_header: list,
    primary_key: str,
    secondary_file: str,
    secondary_key: str = None
) -> tuple:
    """
    Perform an inner join between primary rows and a secondary CSV file.

    Args:
        primary_rows: List of row dicts from the primary file.
        primary_header: Header of the primary file.
        primary_key: Join key column in the primary file.
        secondary_file: Path to the secondary CSV file.
        secondary_key: Join key column in the secondary file (defaults to primary_key).

    Returns:
        Tuple of (joined_header: list[str], joined_rows: list[dict]).
    """
    if secondary_key is None:
        secondary_key = primary_key

    from reader import read_csv

    secondary_header, secondary_rows, _ = read_csv(secondary_file)

    if secondary_key not in secondary_header:
        raise ValueError(
            f"Join key '{secondary_key}' not found in secondary file '{secondary_file}'."
        )
    if primary_key not in primary_header:
        raise ValueError(
            f"Join key '{primary_key}' not found in primary file."
        )

    # Build lookup from secondary rows
    lookup = {}
    for row in secondary_rows:
        key_val = row.get(secondary_key)
        if key_val is not None and key_val not in lookup:
            lookup[key_val] = row

    # Build joined header
    # Prefix conflicting columns from secondary with 'right_'
    joined_header = list(primary_header)
    for col in secondary_header:
        if col == secondary_key and secondary_key == primary_key:
            # Same key column, don't duplicate
            if col not in joined_header:
                joined_header.append(col)
            continue
        if col == secondary_key and secondary_key != primary_key:
            if col not in joined_header:
                joined_header.append(col)
            continue
        if col in joined_header:
            joined_header.append(f"right_{col}")
        else:
            joined_header.append(col)

    # Perform join
    joined_rows = []
    for row in primary_rows:
        key_val = row.get(primary_key)
        if key_val is None:
            continue
        # Convert key to string for lookup since lookup keys from reading are strings
        key_str = str(key_val)
        if key_str in lookup:
            secondary_row = lookup[key_str]
            new_row = {}
            # Add primary columns
            for col in primary_header:
                new_row[col] = row.get(col)
            # Add secondary columns (excluding duplicate key)
            for col in secondary_header:
                if col == primary_key and primary_key == secondary_key:
                    continue  # already added
                val = secondary_row.get(col)
                if col in new_row and col != primary_key:
                    new_row[f"right_{col}"] = val
                else:
                    new_row[col] = val
            joined_rows.append(new_row)

    return joined_header, joined_rows
