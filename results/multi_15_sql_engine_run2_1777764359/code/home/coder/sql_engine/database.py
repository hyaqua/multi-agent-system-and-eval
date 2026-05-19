"""In-memory table store; loads/saves CSV, manages rows and column metadata."""

import csv
import os
from error import QueryError


class Table:
    """Represents a table with column names and rows (tuples)."""

    def __init__(self, name: str, columns: list[str], rows: list[tuple] = None):
        self.name = name
        self.columns = list(columns)
        self.rows = list(rows) if rows else []

    def insert_row(self, row: tuple):
        """Append a row tuple to the table."""
        self.rows.append(tuple(row))

    def column_index(self, column_name: str) -> int:
        """Return the index of a column, or -1 if not found."""
        try:
            return self.columns.index(column_name)
        except ValueError:
            return -1

    def has_column(self, column_name: str) -> bool:
        return column_name in self.columns

    def row_count(self) -> int:
        return len(self.rows)

    def row_as_dict(self, row_idx: int) -> dict:
        """Return a row as a dict mapping column_name -> value."""
        return dict(zip(self.columns, self.rows[row_idx]))


class Database:
    """In-memory database holding named tables."""

    def __init__(self):
        self.tables: dict[str, Table] = {}

    def get_table(self, name: str) -> Table:
        """Retrieve a table by name, raising QueryError if not found."""
        name_lower = name.lower()
        if name_lower not in self.tables:
            raise QueryError(f"Table '{name}' does not exist.")
        return self.tables[name_lower]

    def has_table(self, name: str) -> bool:
        return name.lower() in self.tables

    def add_table(self, table: Table):
        """Add or overwrite a table."""
        self.tables[table.name.lower()] = table

    def load_csv(self, table_name: str, filepath: str):
        """Load a CSV file into a table."""
        if not os.path.isfile(filepath):
            raise QueryError(f"File '{filepath}' not found.")

        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as e:
            raise QueryError(f"Error reading CSV file '{filepath}': {e}")

        if not rows:
            raise QueryError(f"CSV file '{filepath}' is empty.")

        columns = rows[0]
        # Validate column names are non-empty
        for col in columns:
            if not col.strip():
                raise QueryError(f"Empty column name in CSV file '{filepath}'.")

        data_rows = [tuple(row) for row in rows[1:]]
        # Ensure all rows have the same number of columns
        for i, row in enumerate(data_rows, start=2):
            if len(row) != len(columns):
                raise QueryError(
                    f"Row {i} in '{filepath}' has {len(row)} values, "
                    f"expected {len(columns)}."
                )

        table = Table(table_name, columns, data_rows)
        self.add_table(table)

    def save_csv(self, table_name: str, filepath: str):
        """Save a table to a CSV file."""
        table = self.get_table(table_name)
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(table.columns)
                writer.writerows(table.rows)
        except Exception as e:
            raise QueryError(f"Error writing CSV file '{filepath}': {e}")
