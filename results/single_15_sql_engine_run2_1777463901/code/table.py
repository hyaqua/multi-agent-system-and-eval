"""Table module - CSV-backed table storage and operations."""

import csv
from typing import Any


class Table:
    def __init__(self, name: str, columns: list[str], rows: list[list[str]]):
        self.name = name
        self.columns = columns
        self.rows = rows  # List of list of strings (all values stored as strings)

    def column_index(self, name: str) -> int:
        if name not in self.columns:
            raise ValueError(f"Column '{name}' not found in table '{self.name}'. Available columns: {', '.join(self.columns)}")
        return self.columns.index(name)

    def get_column(self, row: list[str], name: str) -> str:
        return row[self.column_index(name)]

    def get_row_dict(self, row: list[str]) -> dict[str, str]:
        return {col: row[i] for i, col in enumerate(self.columns)}

    def __repr__(self):
        return f"Table({self.name}, cols={self.columns}, rows={len(self.rows)})"


def load_csv(name: str, filepath: str) -> 'Table':
    """Load a CSV file into a Table object."""
    try:
        with open(filepath, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: '{filepath}'")
    except Exception as e:
        raise Exception(f"Error reading file '{filepath}': {e}")

    if not rows:
        raise ValueError(f"CSV file '{filepath}' is empty")

    columns = rows[0]
    data = rows[1:]
    return Table(name=name, columns=columns, rows=data)


def save_csv(table: 'Table', filepath: str):
    """Save a Table to a CSV file."""
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(table.columns)
            writer.writerows(table.rows)
    except PermissionError:
        raise PermissionError(f"Permission denied writing to '{filepath}'")
    except Exception as e:
        raise Exception(f"Error writing file '{filepath}': {e}")


def _to_number(value: str) -> int | float | str:
    """Try to convert a string to a number, fall back to string."""
    if not value:
        return value
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _typed_compare(a: str, b: str, op: str) -> bool:
    """Compare two values using operator, trying numeric comparison first."""
    na = _to_number(a)
    nb = _to_number(b)

    # If both are numbers, compare numerically
    if isinstance(na, (int, float)) and isinstance(nb, (int, float)):
        if op == '=':
            return na == nb
        elif op == '!=' or op == '<>':
            return na != nb
        elif op == '<':
            return na < nb
        elif op == '>':
            return na > nb
        elif op == '<=':
            return na <= nb
        elif op == '>=':
            return na >= nb
    else:
        # String comparison
        sa = str(na)
        sb = str(nb)
        if op == '=':
            return sa == sb
        elif op == '!=' or op == '<>':
            return sa != sb
        elif op == '<':
            return sa < sb
        elif op == '>':
            return sa > sb
        elif op == '<=':
            return sa <= sb
        elif op == '>=':
            return sa >= sb

    raise ValueError(f"Unknown operator: {op}")


def _typed_sort_key(value: str):
    """Key for sorting: try numeric first."""
    n = _to_number(value)
    if isinstance(n, (int, float)):
        return (0, n, '')
    return (1, 0, value)
