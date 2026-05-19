"""
Storage module for loading and saving CSV tables.
"""

import csv
import os
from typing import List, Dict, Any


class Storage:
    """In-memory storage for tables loaded from CSV files."""

    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.column_order: Dict[str, List[str]] = {}

    def load_csv(self, table_name: str, filename: str):
        """Load a CSV file into a named table."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File '{filename}' not found")

        with open(filename, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = []
            for row in reader:
                converted = {k: self._convert_value(v) for k, v in row.items()}
                rows.append(converted)

            self.tables[table_name] = rows
            if rows:
                self.column_order[table_name] = list(rows[0].keys())
            else:
                # Rewind to get header even with no data rows
                f.seek(0)
                csv_reader = csv.reader(f)
                try:
                    header = next(csv_reader)
                except StopIteration:
                    header = []
                self.column_order[table_name] = header

        print(f"Loaded table '{table_name}' with {len(rows)} rows from '{filename}'")

    def save_csv(self, table_name: str, filename: str):
        """Save a table to a CSV file."""
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist")

        rows = self.tables[table_name]
        columns = self.column_order.get(table_name, [])
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

        print(f"Saved table '{table_name}' ({len(rows)} rows) to '{filename}'")

    def get_table(self, table_name: str) -> List[Dict[str, Any]]:
        """Get all rows of a table."""
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist. Use LOAD to load a CSV first.")
        return self.tables[table_name]

    def get_columns(self, table_name: str) -> List[str]:
        """Get the column names for a table, in order."""
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist.")
        return self.column_order.get(table_name, [])

    def insert_row(self, table_name: str, values: List[Any]):
        """Insert a row into an existing table."""
        if table_name not in self.tables:
            raise ValueError(f"Table '{table_name}' does not exist.")

        columns = self.column_order[table_name]
        if len(values) != len(columns):
            raise ValueError(
                f"Expected {len(columns)} values for table '{table_name}' "
                f"(columns: {', '.join(columns)}), got {len(values)}"
            )

        row = {}
        for col, val in zip(columns, values):
            row[col] = self._convert_value(val)

        self.tables[table_name].append(row)
        print(f"Inserted 1 row into '{table_name}'")

    @staticmethod
    def _convert_value(value):
        """Try to convert a string value to int or float, preserving strings otherwise."""
        if not isinstance(value, str):
            return value
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        return value
