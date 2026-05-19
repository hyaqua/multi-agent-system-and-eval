#!/usr/bin/env python3
"""
CSV Data Pipeline and Reporting Tool

Reads one or more CSV files, performs data cleaning and transformation,
computes statistical summaries, and outputs formatted reports.

Usage:
    python csv_pipeline.py file.csv [file2.csv ...] [options]

Options:
    --filter COND    Filter rows by condition (e.g. 'age>30', 'name=John')
    --sort COL       Sort output by column name
    --join FILE,KEY  Join with another CSV file on a shared key column
    --output FILE    Write processed result to CSV file
"""

import sys
import csv
import os
import math
import argparse
import io
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Date detection helpers
# ---------------------------------------------------------------------------
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
]


def is_date(value: str) -> bool:
    """Return True if the string can be parsed as a date."""
    if not value or not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return False
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def is_numeric(value: str) -> bool:
    """Return True if the string can be parsed as a float."""
    if not value or not isinstance(value, str):
        return False
    value = value.strip()
    if not value:
        return False
    # Remove currency symbols, commas
    cleaned = value.replace("$", "").replace(",", "").replace(" ", "")
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def try_parse_numeric(value: str) -> Optional[float]:
    """Try to parse a string as a float, return None on failure."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def try_parse_date(value: str) -> Optional[datetime]:
    """Try to parse a string as a date, return None on failure."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Column type detection
# ---------------------------------------------------------------------------
def detect_column_type(values: list[str]) -> str:
    """
    Detect the type of a column given a list of string values.
    Returns 'numeric', 'date', or 'text'.
    """
    non_empty = [v for v in values if v is not None and v.strip() != ""]
    if not non_empty:
        return "text"

    numeric_count = 0
    date_count = 0
    total = len(non_empty)

    for v in non_empty:
        if is_numeric(v):
            numeric_count += 1
        if is_date(v):
            date_count += 1

    # Require > 70% of non-empty values to match for numeric or date
    if total > 0 and numeric_count / total >= 0.7:
        return "numeric"
    if total > 0 and date_count / total >= 0.7:
        return "date"
    return "text"


# ---------------------------------------------------------------------------
# CSV reading with robust parsing
# ---------------------------------------------------------------------------
def read_csv_file(filepath: str) -> tuple[list[str], list[list[str]], list[int]]:
    """
    Read a CSV file and return (headers, rows, empty_counts_per_column).

    Handles quoted fields and commas within fields correctly (uses csv module).
    Detects and warns about inconsistent column counts.

    Returns:
        headers: list of column names
        rows: list of rows, each row is a list of string values
        empty_counts: count of empty/missing values per column
    """
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    rows = []
    headers = []
    max_cols = 0
    inconsistent = False

    try:
        with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
            # Try to sniff the dialect
            sample = f.read(8192)
            f.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = "excel"

            reader = csv.reader(f, dialect)

            # Read header
            try:
                headers = next(reader)
            except StopIteration:
                print(f"WARNING: {filepath} is empty.", file=sys.stderr)
                return [], [], []

            headers = [h.strip() for h in headers]
            max_cols = len(headers)

            for row in reader:
                if not any(cell.strip() for cell in row):
                    # Skip completely empty rows
                    continue
                if len(row) != max_cols:
                    inconsistent = True
                    # Pad or truncate
                    if len(row) < max_cols:
                        row = row + [""] * (max_cols - len(row))
                    else:
                        row = row[:max_cols]
                rows.append(row)

    except Exception as e:
        print(f"ERROR: Could not read {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    if inconsistent:
        print(
            f"WARNING: {filepath} has inconsistent column counts. "
            f"Rows were padded or truncated to match header ({max_cols} columns).",
            file=sys.stderr,
        )

    # Count empty values per column
    empty_counts = [0] * len(headers)
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(empty_counts) and (cell is None or cell.strip() == ""):
                empty_counts[i] += 1

    return headers, rows, empty_counts


# ---------------------------------------------------------------------------
# Column type analysis
# ---------------------------------------------------------------------------
def analyze_columns(
    headers: list[str], rows: list[list[str]]
) -> dict[str, dict]:
    """
    Analyze each column: detect type, count empties, compute stats.
    Returns a dict keyed by column name.
    """
    if not headers:
        return {}

    n_cols = len(headers)
    columns = {h: [] for h in headers}
    for row in rows:
        for i, cell in enumerate(row):
            if i < n_cols:
                columns[headers[i]].append(cell if cell is not None else "")

    result = {}
    for col_name, values in columns.items():
        col_type = detect_column_type(values)
        empty_count = sum(1 for v in values if v is None or v.strip() == "")
        info = {
            "type": col_type,
            "empty_count": empty_count,
            "total_count": len(values),
            "non_empty_count": len(values) - empty_count,
        }

        if col_type == "numeric":
            nums = []
            for v in values:
                n = try_parse_numeric(v)
                if n is not None:
                    nums.append(n)
            if nums:
                n = len(nums)
                mean = sum(nums) / n
                sorted_nums = sorted(nums)
                if n % 2 == 1:
                    median = sorted_nums[n // 2]
                else:
                    median = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
                variance = sum((x - mean) ** 2 for x in nums) / (n - 1) if n > 1 else 0.0
                std_dev = math.sqrt(variance)
                info.update(
                    {
                        "count": n,
                        "mean": mean,
                        "median": median,
                        "min": min(nums),
                        "max": max(nums),
                        "std_dev": std_dev,
                    }
                )
        elif col_type == "text":
            non_empty = [v.strip() for v in values if v and v.strip()]
            counter = Counter(non_empty)
            info["top_5"] = counter.most_common(5)

        result[col_name] = info

    return result


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def parse_filter_condition(condition: str) -> tuple[str, str, str]:
    """
    Parse a filter condition like 'age>30', 'name=John', 'salary>=50000', 'status!=active'.

    Returns (column, operator, value).
    Supported operators: >=, <=, !=, >, <, =
    """
    # Order matters: check multi-char operators first
    for op in [">=", "<=", "!=", ">", "<", "="]:
        if op in condition:
            parts = condition.split(op, 1)
            if len(parts) == 2:
                col = parts[0].strip()
                val = parts[1].strip()
                return col, op, val
    raise ValueError(f"Could not parse filter condition: {condition}")


def apply_filter(
    rows: list[list[str]],
    headers: list[str],
    condition: str,
    column_types: dict[str, dict],
) -> list[list[str]]:
    """Filter rows based on a condition string."""
    if not condition or not rows:
        return rows

    try:
        col_name, op, val = parse_filter_condition(condition)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if col_name not in headers:
        print(
            f"ERROR: Column '{col_name}' not found for --filter. "
            f"Available columns: {headers}",
            file=sys.stderr,
        )
        sys.exit(1)

    col_idx = headers.index(col_name)
    col_type = column_types.get(col_name, {}).get("type", "text")

    filtered = []
    for row in rows:
        cell = row[col_idx] if col_idx < len(row) else ""
        cell = cell.strip() if cell else ""

        if col_type == "numeric":
            cell_val = try_parse_numeric(cell)
            filter_val = try_parse_numeric(val)
        elif col_type == "date":
            cell_val = try_parse_date(cell)
            filter_val = try_parse_date(val)
        else:
            cell_val = cell
            filter_val = val

        # If either is None for numeric/date, skip the row (can't compare)
        if cell_val is None:
            continue

        try:
            if op == ">" and cell_val > filter_val:
                filtered.append(row)
            elif op == "<" and cell_val < filter_val:
                filtered.append(row)
            elif op == ">=" and cell_val >= filter_val:
                filtered.append(row)
            elif op == "<=" and cell_val <= filter_val:
                filtered.append(row)
            elif op == "=" and cell_val == filter_val:
                filtered.append(row)
            elif op == "!=" and cell_val != filter_val:
                filtered.append(row)
        except TypeError:
            # Can't compare, skip
            continue

    return filtered


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------
def apply_sort(
    rows: list[list[str]],
    headers: list[str],
    sort_col: str,
    column_types: dict[str, dict],
) -> list[list[str]]:
    """Sort rows by the specified column."""
    if not sort_col or not rows:
        return rows

    if sort_col not in headers:
        print(
            f"ERROR: Column '{sort_col}' not found for --sort. "
            f"Available columns: {headers}",
            file=sys.stderr,
        )
        sys.exit(1)

    col_idx = headers.index(sort_col)
    col_type = column_types.get(sort_col, {}).get("type", "text")

    def sort_key(row):
        cell = row[col_idx] if col_idx < len(row) else ""
        cell = cell.strip() if cell else ""

        if col_type == "numeric":
            n = try_parse_numeric(cell)
            return (0, n if n is not None else float("-inf"))
        elif col_type == "date":
            d = try_parse_date(cell)
            return (0, d if d is not None else datetime.min)
        else:
            return (1, cell.lower())

    return sorted(rows, key=sort_key)


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------
def apply_join(
    left_headers: list[str],
    left_rows: list[list[str]],
    join_spec: str,
) -> tuple[list[str], list[list[str]]]:
    """
    Join with another CSV file on a shared key column.

    join_spec format: 'file.csv,key_column'
    Returns (merged_headers, merged_rows). Left join.
    """
    if not join_spec:
        return left_headers, left_rows

    parts = join_spec.split(",")
    if len(parts) < 2:
        print(
            "ERROR: --join requires format 'file.csv,key_column'",
            file=sys.stderr,
        )
        sys.exit(1)

    join_file = parts[0].strip()
    key_col = parts[1].strip()

    if not os.path.exists(join_file):
        print(f"ERROR: Join file not found: {join_file}", file=sys.stderr)
        sys.exit(1)

    right_headers, right_rows, _ = read_csv_file(join_file)

    if key_col not in left_headers:
        print(
            f"ERROR: Key column '{key_col}' not found in left file. "
            f"Columns: {left_headers}",
            file=sys.stderr,
        )
        sys.exit(1)
    if key_col not in right_headers:
        print(
            f"ERROR: Key column '{key_col}' not found in right file. "
            f"Columns: {right_headers}",
            file=sys.stderr,
        )
        sys.exit(1)

    left_key_idx = left_headers.index(key_col)
    right_key_idx = right_headers.index(key_col)

    # Build lookup from right table, keyed by the join column value
    right_lookup = defaultdict(list)
    for row in right_rows:
        key = row[right_key_idx].strip() if right_key_idx < len(row) else ""
        right_lookup[key].append(row)

    # Build merged headers (left columns + right columns except the key)
    right_cols_to_add = [
        (i, h) for i, h in enumerate(right_headers) if i != right_key_idx
    ]
    merged_headers = left_headers + [h for _, h in right_cols_to_add]

    merged_rows = []
    for left_row in left_rows:
        key = (
            left_row[left_key_idx].strip()
            if left_key_idx < len(left_row)
            else ""
        )
        if key in right_lookup:
            for right_row in right_lookup[key]:
                merged_row = list(left_row)
                for i, _ in right_cols_to_add:
                    merged_row.append(right_row[i] if i < len(right_row) else "")
                merged_rows.append(merged_row)
        else:
            # Left join: keep left row, fill right with empty
            merged_row = list(left_row)
            for _, _ in right_cols_to_add:
                merged_row.append("")
            merged_rows.append(merged_row)

    return merged_headers, merged_rows


# ---------------------------------------------------------------------------
# Formatted text table
# ---------------------------------------------------------------------------
def print_text_table(headers: list[str], rows: list[list[str]], max_width: int = 30):
    """Print a formatted text table to stdout."""
    if not headers:
        print("No data to display.")
        return

    n_cols = len(headers)
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < n_cols:
                col_widths[i] = max(col_widths[i], len(str(cell)))

    # Cap at max_width
    col_widths = [min(w, max_width) for w in col_widths]

    def fmt_cell(val, width):
        s = str(val) if val is not None else ""
        if len(s) > width:
            s = s[: width - 3] + "..."
        return s.ljust(width)

    # Separator
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    def print_row(vals):
        parts = []
        for i, v in enumerate(vals):
            if i < n_cols:
                parts.append(" " + fmt_cell(v, col_widths[i]) + " ")
            else:
                parts.append(" " + " " * col_widths[i] + " ")
        print("|" + "|".join(parts) + "|")

    print(sep)
    print_row(headers)
    print(sep)
    for row in rows:
        print_row(row)
    print(sep)
    print(f"({len(rows)} row(s))")


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def print_summary_report(
    headers: list[str],
    rows: list[list[str]],
    column_analysis: dict[str, dict],
):
    """Print a detailed summary report with stats and top values."""
    print()
    print("=" * 70)
    print("  COLUMN SUMMARY REPORT")
    print("=" * 70)

    for col_name in headers:
        info = column_analysis.get(col_name, {})
        col_type = info.get("type", "text")
        empty_count = info.get("empty_count", 0)
        total = info.get("total_count", 0)

        print(f"\n  Column: '{col_name}'")
        print(f"    Type:        {col_type}")
        print(f"    Total rows:  {total}")
        print(f"    Empty/Missing: {empty_count}")

        if col_type == "numeric":
            print(f"    Count:       {info.get('count', 'N/A')}")
            print(f"    Mean:        {info.get('mean', 'N/A'):.4f}" if isinstance(info.get('mean'), float) else f"    Mean:        {info.get('mean', 'N/A')}")
            print(f"    Median:      {info.get('median', 'N/A'):.4f}" if isinstance(info.get('median'), float) else f"    Median:      {info.get('median', 'N/A')}")
            print(f"    Min:         {info.get('min', 'N/A'):.4f}" if isinstance(info.get('min'), float) else f"    Min:         {info.get('min', 'N/A')}")
            print(f"    Max:         {info.get('max', 'N/A'):.4f}" if isinstance(info.get('max'), float) else f"    Max:         {info.get('max', 'N/A')}")
            print(f"    Std Dev:     {info.get('std_dev', 'N/A'):.4f}" if isinstance(info.get('std_dev'), float) else f"    Std Dev:     {info.get('std_dev', 'N/A')}")
        elif col_type == "text":
            top5 = info.get("top_5", [])
            if top5:
                print(f"    Top 5 values:")
                for val, count in top5:
                    display = val if len(val) <= 40 else val[:37] + "..."
                    print(f"      '{display}' → {count}")

    print("\n" + "=" * 70)


def format_numeric(value, decimal_places=4):
    """Format a numeric value for display."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{decimal_places}f}"
    return str(value)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------
def write_csv_output(
    filepath: str, headers: list[str], rows: list[list[str]]
):
    """Write headers and rows to a CSV file."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"\nOutput written to: {filepath}")
    except Exception as e:
        print(f"ERROR: Could not write to {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CSV Data Pipeline and Reporting Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_pipeline.py data.csv
  python csv_pipeline.py data.csv --filter 'age>30' --sort name
  python csv_pipeline.py data.csv --join other.csv,id --output merged.csv
  python csv_pipeline.py file1.csv file2.csv --filter 'salary>=50000'
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="One or more CSV files to process. If multiple, rows are concatenated.",
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Filter rows by condition (e.g. 'age>30', 'name=John')",
    )
    parser.add_argument(
        "--sort",
        default=None,
        help="Sort output by a column name",
    )
    parser.add_argument(
        "--join",
        default=None,
        help="Join with another CSV on a key column. Format: 'file.csv,key_column'",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write processed result to a CSV file",
    )

    args = parser.parse_args()

    # Validate all input files exist
    all_input_files = list(args.files)
    if args.join:
        join_file = args.join.split(",")[0].strip()
        all_input_files.append(join_file)

    for f in all_input_files:
        if not os.path.exists(f):
            print(f"ERROR: File not found: {f}", file=sys.stderr)
            sys.exit(1)

    # Read all input files and concatenate
    all_headers = None
    all_rows = []
    all_empty_counts = None

    for i, filepath in enumerate(args.files):
        headers, rows, empty_counts = read_csv_file(filepath)
        if not headers:
            continue

        if all_headers is None:
            all_headers = headers
            all_empty_counts = empty_counts
        else:
            # Check header compatibility
            if headers != all_headers:
                print(
                    f"WARNING: Headers in {filepath} differ from previous files. "
                    f"Using first file's headers. Column mismatch may cause issues.",
                    file=sys.stderr,
                )
                # For concatenation, we align by position
                # Pad/truncate to match
                for row in rows:
                    if len(row) < len(all_headers):
                        row = row + [""] * (len(all_headers) - len(row))
                    elif len(row) > len(all_headers):
                        row = row[: len(all_headers)]
            else:
                # Same headers, update empty counts
                for j in range(min(len(all_empty_counts), len(empty_counts))):
                    all_empty_counts[j] += empty_counts[j]

        all_rows.extend(rows)

    if all_headers is None:
        print("ERROR: No valid data found in input files.", file=sys.stderr)
        sys.exit(1)

    # Join if requested
    if args.join:
        all_headers, all_rows = apply_join(all_headers, all_rows, args.join)

    # Analyze columns after reading but before filtering
    # (analysis is for the full dataset; we re-analyze after filtering for the report)

    # Analyze columns (type detection based on all rows)
    column_analysis = analyze_columns(all_headers, all_rows)

    # Apply filter
    if args.filter:
        before_count = len(all_rows)
        all_rows = apply_filter(all_rows, all_headers, args.filter, column_analysis)
        after_count = len(all_rows)
        print(
            f"\n[Filter: {args.filter}]  {before_count} rows → {after_count} rows"
        )

    # Apply sort
    if args.sort:
        all_rows = apply_sort(all_rows, all_headers, args.sort, column_analysis)

    # Re-analyze after filtering for accurate report (on displayed data)
    displayed_analysis = analyze_columns(all_headers, all_rows)

    # Write CSV output if requested
    if args.output:
        write_csv_output(args.output, all_headers, all_rows)

    # Print text table to stdout (default)
    if all_rows:
        print_text_table(all_headers, all_rows)
    else:
        print("\nNo rows to display after processing.")

    # Print summary report
    print_summary_report(all_headers, all_rows, displayed_analysis)


if __name__ == "__main__":
    main()
