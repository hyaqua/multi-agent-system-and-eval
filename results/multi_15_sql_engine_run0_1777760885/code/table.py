import csv
import os


class Table:
    """In-memory table: columns as list of strings; rows as list of dicts."""

    def __init__(self, name, columns=None, rows=None):
        self.name = name
        self.columns = columns if columns is not None else []
        self._rows = rows if rows is not None else []

    @property
    def rows(self):
        return self._rows

    def add_row(self, row_dict):
        """Append a row (dict of column->value). Missing columns get empty string."""
        full = {}
        for col in self.columns:
            full[col] = row_dict.get(col, "")
        self._rows.append(full)

    def load_csv(self, filepath):
        """Load table from CSV file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            all_rows = list(reader)
            if not all_rows:
                raise ValueError(f"CSV file is empty: {filepath}")
            self.columns = all_rows[0]
            self._rows = []
            for row in all_rows[1:]:
                d = {}
                for i, col in enumerate(self.columns):
                    d[col] = row[i] if i < len(row) else ""
                self._rows.append(d)

    def save_csv(self, filepath):
        """Save table to CSV file."""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            for row in self._rows:
                writer.writerow([row.get(col, "") for col in self.columns])

    def __repr__(self):
        return f"Table({self.name!r}, cols={self.columns!r}, rows={len(self._rows)})"
