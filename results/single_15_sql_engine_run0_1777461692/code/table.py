"""Table module - CSV-backed tables for the SQL engine."""

import csv
import os
from typing import Optional


class TableError(Exception):
    """Error related to table operations."""
    pass


class Table:
    """Represents a table loaded from or to be saved to a CSV file."""

    def __init__(self, name: str, columns: list[str], rows: list[dict]):
        self.name = name
        self.columns = columns
        self.rows = rows  # list of dicts: {col_name: value}

    def __len__(self):
        return len(self.rows)

    @classmethod
    def load_csv(cls, name: str, filepath: str) -> 'Table':
        """Load a table from a CSV file."""
        if not os.path.exists(filepath):
            raise TableError(f"File not found: '{filepath}'")

        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows_list = list(reader)
        except Exception as e:
            raise TableError(f"Error reading file '{filepath}': {e}")

        if not rows_list:
            raise TableError(f"CSV file '{filepath}' is empty")

        columns = [c.strip() for c in rows_list[0]]
        # Check for duplicate column names
        seen = set()
        for c in columns:
            if c in seen:
                raise TableError(f"Duplicate column name '{c}' in '{filepath}'")
            seen.add(c)

        rows = []
        for i, row in enumerate(rows_list[1:], start=2):
            # Pad short rows with None
            padded = list(row) + [None] * (len(columns) - len(row))
            # Truncate long rows
            padded = padded[:len(columns)]
            # Convert to appropriate types
            typed_row = {}
            for col, val in zip(columns, padded):
                typed_row[col] = cls._parse_value(val)
            rows.append(typed_row)

        return cls(name=name, columns=columns, rows=rows)

    def save_csv(self, filepath: str):
        """Save the table to a CSV file."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for row in self.rows:
                    writer.writerow([self._format_value(row.get(c, '')) for c in self.columns])
        except Exception as e:
            raise TableError(f"Error writing file '{filepath}': {e}")

    def insert_row(self, values: list) -> dict:
        """Insert a row into the table. Returns the new row as a dict."""
        if len(values) != len(self.columns):
            raise TableError(
                f"Expected {len(self.columns)} values for table '{self.name}', "
                f"got {len(values)}"
            )
        row = {}
        for col, val in zip(self.columns, values):
            row[col] = val.value if hasattr(val, 'value') else val
        self.rows.append(row)
        return row

    def get_column(self, col_name: str) -> list:
        """Get all values for a column."""
        return [row.get(col_name) for row in self.rows]

    @staticmethod
    def _parse_value(val):
        """Parse a value from CSV string to appropriate type."""
        if val is None or val.strip() == '':
            return None
        val = val.strip()
        # Try int
        try:
            return int(val)
        except ValueError:
            pass
        # Try float
        try:
            return float(val)
        except ValueError:
            pass
        # Return as string
        return val

    @staticmethod
    def _format_value(val):
        """Format a value for CSV output."""
        if val is None:
            return ''
        return str(val)

    def __repr__(self):
        return f"Table('{self.name}', columns={self.columns}, rows={len(self.rows)})"
