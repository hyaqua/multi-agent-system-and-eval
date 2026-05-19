"""Core processing logic: CSV reading, type inference, statistics,
transformations, output generation."""

import csv
import statistics as stats_module
from collections import Counter
from formatter import format_table, format_summary, write_csv
from utils import (
    try_parse_numeric,
    try_parse_date,
    parse_condition,
    matches_condition,
)


class Pipeline:
    """Encapsulates CSV data and transformation operations."""

    def __init__(self):
        self.headers: list = []
        self.rows: list = []          # list of dicts (keyed by header name)
        self.column_types: dict = {}
        self.missing_counts: dict = {}
        self.statistics: dict = {}    # numeric stats per column
        self.text_frequencies: dict = {}  # top-5 text frequencies per column
        self.warnings: list = []

    # ------------------------------------------------------------------
    #  Reading
    # ------------------------------------------------------------------
    def read_csv(self, filepath: str):
        """Read a CSV file, store headers and rows (as dicts).
        Handles quoting, inconsistent column counts, and empty files."""
        self.headers = []
        self.rows = []
        self.warnings = []

        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f, skipinitialspace=True)
            # Read header
            try:
                self.headers = next(reader)
            except StopIteration:
                self.warnings.append(f"File '{filepath}' is empty.")
                return

            self.headers = [h.strip() for h in self.headers]
            ncols = len(self.headers)

            for line_no, raw_row in enumerate(reader, start=2):
                if len(raw_row) < ncols:
                    # Pad with empty strings
                    raw_row = raw_row + [""] * (ncols - len(raw_row))
                    self.warnings.append(
                        f"Line {line_no} in '{filepath}': expected {ncols} "
                        f"columns, got {len(raw_row)}. Padded."
                    )
                elif len(raw_row) > ncols:
                    self.warnings.append(
                        f"Line {line_no} in '{filepath}': expected {ncols} "
                        f"columns, got {len(raw_row)}. Truncated."
                    )
                    raw_row = raw_row[:ncols]

                row_dict = {h: v for h, v in zip(self.headers, raw_row)}
                self.rows.append(row_dict)

    # ------------------------------------------------------------------
    #  Type inference
    # ------------------------------------------------------------------
    def infer_types(self):
        """Classify each column as numeric, date, or text by sampling
        up to 100 non-empty rows."""
        self.column_types = {}
        if not self.headers:
            return

        sample_size = min(100, len(self.rows))

        for col in self.headers:
            values = []
            for row in self.rows[:sample_size]:
                v = row.get(col, "").strip()
                if v:
                    values.append(v)

            if not values:
                self.column_types[col] = "text"
                continue

            # Check numeric
            numeric_count = sum(1 for v in values if try_parse_numeric(v) is not None)
            if numeric_count == len(values):
                self.column_types[col] = "numeric"
                continue

            # Check date
            date_count = sum(1 for v in values if try_parse_date(v) is not None)
            if date_count == len(values):
                self.column_types[col] = "date"
                continue

            # Fallback
            self.column_types[col] = "text"

    # ------------------------------------------------------------------
    #  Missing value counts
    # ------------------------------------------------------------------
    def missing_counts_calc(self):
        """Count empty / missing values per column."""
        self.missing_counts = {}
        for col in self.headers:
            count = 0
            for row in self.rows:
                v = row.get(col)
                if v is None or v.strip() == "":
                    count += 1
            self.missing_counts[col] = count

    # ------------------------------------------------------------------
    #  Statistics
    # ------------------------------------------------------------------
    def compute_statistics(self):
        """Compute numeric stats and top-5 text frequencies."""
        self.statistics = {}
        self.text_frequencies = {}

        if not self.headers:
            return

        for col in self.headers:
            ctype = self.column_types.get(col, "text")

            if ctype == "numeric":
                nums = []
                for row in self.rows:
                    v = row.get(col, "").strip()
                    if v:
                        n = try_parse_numeric(v)
                        if n is not None:
                            nums.append(float(n))

                if nums:
                    self.statistics[col] = {
                        "count": len(nums),
                        "mean": round(stats_module.mean(nums), 4),
                        "median": round(stats_module.median(nums), 4),
                        "min": round(min(nums), 4),
                        "max": round(max(nums), 4),
                        "stdev": (
                            round(stats_module.stdev(nums), 4)
                            if len(nums) >= 2
                            else "N/A"
                        ),
                    }
                else:
                    self.statistics[col] = {
                        "count": 0,
                        "mean": "N/A",
                        "median": "N/A",
                        "min": "N/A",
                        "max": "N/A",
                        "stdev": "N/A",
                    }

            elif ctype == "text" or ctype == "date":
                counter = Counter()
                for row in self.rows:
                    v = row.get(col, "").strip()
                    if v:
                        counter[v] += 1
                self.text_frequencies[col] = counter.most_common(5)

    # ------------------------------------------------------------------
    #  Filtering
    # ------------------------------------------------------------------
    def filter_rows(self, condition_str: str):
        """Filter rows using a condition string like 'age>30'.
        Silently ignores conditions on non-existent columns."""
        if not condition_str or not condition_str.strip():
            return

        try:
            cond = parse_condition(condition_str)
        except ValueError as e:
            self.warnings.append(str(e))
            return

        col = cond[0]
        if col not in self.headers:
            self.warnings.append(
                f"Filter column '{col}' not found. Filter skipped."
            )
            return

        self.rows = [
            r for r in self.rows if matches_condition(r, self.headers, cond)
        ]

    # ------------------------------------------------------------------
    #  Sorting
    # ------------------------------------------------------------------
    def sort_rows(self, column: str, reverse: bool = False):
        """Sort rows by the given column. Numeric columns sorted by float
        value; otherwise lexicographically."""
        if column not in self.headers:
            self.warnings.append(
                f"Sort column '{column}' not found. Skipping sort."
            )
            return

        ctype = self.column_types.get(column, "text")

        def sort_key(row):
            v = row.get(column, "").strip()
            if ctype == "numeric":
                n = try_parse_numeric(v)
                return (0, n if n is not None else float("-inf"))
            return (1, v.lower())

        self.rows.sort(key=sort_key, reverse=reverse)

    # ------------------------------------------------------------------
    #  Joining
    # ------------------------------------------------------------------
    def join(self, other: "Pipeline", key: str):
        """Perform an inner join on a shared key column.
        Merges fields from *other* into *self*. Conflicting columns
        (besides the key) are prefixed with the file name."""
        if key not in self.headers:
            self.warnings.append(
                f"Join key '{key}' not found in first file. Aborting join."
            )
            return

        if key not in other.headers:
            self.warnings.append(
                f"Join key '{key}' not found in second file. Aborting join."
            )
            return

        # Build index from other rows
        other_index = {}
        for row in other.rows:
            k = row.get(key, "").strip()
            other_index.setdefault(k, []).append(row)

        # Build new headers
        # Prefix conflicting columns (except the key)
        new_headers = list(self.headers)
        for col in other.headers:
            if col == key:
                continue
            if col in new_headers:
                new_name = f"right_{col}"
            else:
                new_name = col
            new_headers.append(new_name)

        # Perform join
        joined_rows = []
        for left_row in self.rows:
            k = left_row.get(key, "").strip()
            if k in other_index:
                for right_row in other_index[k]:
                    merged = dict(left_row)
                    for col in other.headers:
                        if col == key:
                            continue
                        if col in self.headers:
                            new_name = f"right_{col}"
                        else:
                            new_name = col
                        merged[new_name] = right_row.get(col, "")
                    joined_rows.append(merged)

        self.headers = new_headers
        self.rows = joined_rows

        # Recompute types after join (stats will be done later by caller)
        self.infer_types()

    # ------------------------------------------------------------------
    #  Report data
    # ------------------------------------------------------------------
    def get_report_data(self) -> dict:
        """Return a dictionary of headers, rows, column types, missing
        counts, statistics, and warnings."""
        return {
            "headers": list(self.headers),
            "rows": list(self.rows),
            "column_types": dict(self.column_types),
            "missing_counts": dict(self.missing_counts),
            "statistics": dict(self.statistics),
            "text_frequencies": dict(self.text_frequencies),
            "warnings": list(self.warnings),
        }

    # ------------------------------------------------------------------
    #  Output
    # ------------------------------------------------------------------
    def write_output(self, filepath: str):
        """Write processed rows to CSV."""
        write_csv(filepath, self.headers, self.rows)

    # ------------------------------------------------------------------
    #  Display
    # ------------------------------------------------------------------
    def display_report(self, max_rows: int = 50):
        """Print formatted table and summary to stdout."""
        report = self.get_report_data()

        # Print warnings to stderr
        import sys
        for w in report["warnings"]:
            print(f"WARNING: {w}", file=sys.stderr)

        # Table
        display_rows = report["rows"][:max_rows]
        table = format_table(display_rows, report["headers"])
        print(table)

        if len(report["rows"]) > max_rows:
            print(
                f"... showing {max_rows} of {len(report['rows'])} rows\n"
            )

        # Summary
        summary = format_summary(
            report["column_types"],
            report["missing_counts"],
            report["statistics"],
            report["text_frequencies"],
            [],  # warnings already printed to stderr
        )
        print(summary)
