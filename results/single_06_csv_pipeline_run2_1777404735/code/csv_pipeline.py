#!/usr/bin/env python3
"""
CSV Data Pipeline and Reporting Tool
====================================
Reads one or more CSV files, performs data cleaning and transformation,
computes statistical summaries, and outputs formatted reports.

Uses only Python standard library.
"""

import argparse
import csv
import sys
import os
import math
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Common date formats to try when detecting date columns
DATE_FORMATS = [
    '%Y-%m-%d',
    '%Y/%m/%d',
    '%m/%d/%Y',
    '%d/%m/%Y',
    '%m-%d-%Y',
    '%d-%m-%Y',
    '%Y%m%d',
    '%b %d, %Y',
    '%d %b %Y',
    '%B %d, %Y',
    '%d %B %Y',
    '%Y-%m-%d %H:%M:%S',
    '%Y/%m/%d %H:%M:%S',
    '%m/%d/%Y %H:%M:%S',
    '%d/%m/%Y %H:%M:%S',
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def try_parse_numeric(value):
    """Try to parse value as int or float. Returns the number or None."""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    try:
        v = float(value)
        # Check if it's actually an int stored as float
        if v == int(v) and '.' not in str(value).lower():
            return int(v)
        return v
    except (ValueError, TypeError):
        return None


def try_parse_date(value):
    """Try to parse value as a date. Returns date object or None."""
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def is_missing(value):
    """Check if a value is missing/empty."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == '':
        return True
    return False


# ---------------------------------------------------------------------------
# CSV Reading
# ---------------------------------------------------------------------------

def read_csv_file(filepath):
    """
    Read and parse a CSV file.
    Returns (headers, rows, warnings) where:
      - headers: list of column name strings
      - rows: list of lists (each row is a list of string values)
      - warnings: list of warning strings

    Handles quoted fields, commas within fields, and inconsistent column
    counts gracefully.
    """
    warnings = []

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Input file not found: '{filepath}'")

    with open(filepath, 'r', newline='', encoding='utf-8-sig') as f:
        # Detect dialect
        sample = f.read(8192)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel  # default comma-separated

        reader = csv.reader(f, dialect)

        # Read header
        try:
            headers = next(reader)
        except StopIteration:
            warnings.append(f"File '{filepath}' is empty (no header row).")
            return [], [], warnings

        headers = [h.strip() for h in headers]
        if not headers or all(h == '' for h in headers):
            warnings.append(f"File '{filepath}' has empty headers.")
            return [], [], warnings

        # Deduplicate header names
        seen = {}
        deduped = []
        for h in headers:
            if h == '':
                h = 'unnamed'
            if h in seen:
                seen[h] += 1
                deduped.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                deduped.append(h)
        headers = deduped

        expected_cols = len(headers)
        rows = []
        row_num = 1  # header was row 1

        for row in reader:
            row_num += 1
            # Handle inconsistent column counts
            if len(row) < expected_cols:
                warnings.append(
                    f"Row {row_num} in '{filepath}' has {len(row)} fields "
                    f"(expected {expected_cols}). Padding with empty values."
                )
                row = list(row) + [''] * (expected_cols - len(row))
            elif len(row) > expected_cols:
                warnings.append(
                    f"Row {row_num} in '{filepath}' has {len(row)} fields "
                    f"(expected {expected_cols}). Extra fields truncated."
                )
                row = row[:expected_cols]
            rows.append(row)

    return headers, rows, warnings


# ---------------------------------------------------------------------------
# Type Detection
# ---------------------------------------------------------------------------

def detect_column_types(headers, rows, sample_size=200):
    """
    Auto-detect column data types: 'numeric', 'date', or 'text'.

    Returns a dict mapping column name -> type string.
    """
    if not headers or not rows:
        return {h: 'text' for h in headers}

    col_types = {}
    for col_idx, col_name in enumerate(headers):
        values = []
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx]
                if not is_missing(val):
                    values.append(val)
                    if len(values) >= sample_size:
                        break

        if not values:
            col_types[col_name] = 'text'
            continue

        # Check numeric
        numeric_count = 0
        for v in values:
            if try_parse_numeric(v) is not None:
                numeric_count += 1

        if numeric_count == len(values):
            col_types[col_name] = 'numeric'
            continue

        # Check date
        date_count = 0
        for v in values:
            if try_parse_date(v) is not None:
                date_count += 1

        if date_count >= len(values) * 0.8:  # 80% threshold for date
            col_types[col_name] = 'date'
            continue

        col_types[col_name] = 'text'

    return col_types


# ---------------------------------------------------------------------------
# Missing value analysis
# ---------------------------------------------------------------------------

def count_missing(headers, rows):
    """Count missing/empty values per column. Returns dict column->count."""
    counts = {h: 0 for h in headers}
    for row in rows:
        for col_idx, col_name in enumerate(headers):
            if col_idx >= len(row) or is_missing(row[col_idx]):
                counts[col_name] += 1
    return counts


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_numeric_stats(values):
    """
    Compute summary statistics for a list of numeric values.
    Returns dict with count, mean, median, min, max, std_dev.
    Values that fail to parse are skipped.
    """
    nums = []
    for v in values:
        n = try_parse_numeric(v)
        if n is not None:
            nums.append(float(n))

    if not nums:
        return {
            'count': 0,
            'mean': None,
            'median': None,
            'min': None,
            'max': None,
            'std_dev': None,
        }

    n = len(nums)
    mean_val = sum(nums) / n
    sorted_nums = sorted(nums)

    # Median
    if n % 2 == 1:
        median_val = sorted_nums[n // 2]
    else:
        median_val = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2

    # Sample standard deviation
    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in nums) / (n - 1)
        std_val = math.sqrt(variance)
    else:
        std_val = 0.0

    return {
        'count': n,
        'mean': mean_val,
        'median': median_val,
        'min': sorted_nums[0],
        'max': sorted_nums[-1],
        'std_dev': std_val,
    }


def compute_text_frequencies(values, top_n=5):
    """
    Compute the top N most frequent non-empty values.
    Returns list of (value, count) tuples.
    """
    counter = Counter()
    for v in values:
        if not is_missing(v):
            counter[str(v).strip()] += 1
    return counter.most_common(top_n)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def parse_filter_condition(condition_str):
    """
    Parse a filter condition string like 'age>30' or 'name==John'.

    Returns (column, operator, value) tuple.
    Supported operators: >=, <=, !=, ==, >, <
    """
    # Try longest operators first
    match = re.match(
        r'^([a-zA-Z_][a-zA-Z0-9_ ]*?)\s*(>=|<=|!=|==|>|<)\s*(.+)$',
        condition_str
    )
    if not match:
        raise ValueError(
            f"Invalid filter condition: '{condition_str}'. "
            f"Expected format: column>=value (operators: >=, <=, !=, ==, >, <)"
        )
    column = match.group(1).strip()
    operator = match.group(2)
    value = match.group(3).strip()
    return column, operator, value


def apply_filter(rows, headers, col_types, condition_str):
    """
    Filter rows based on a condition string.

    Returns filtered list of rows.
    """
    column, operator, value_str = parse_filter_condition(condition_str)

    if column not in headers:
        raise ValueError(
            f"Column '{column}' not found for filtering. "
            f"Available columns: {', '.join(headers)}"
        )

    col_idx = headers.index(column)
    col_type = col_types.get(column, 'text')

    filtered = []
    for row in rows:
        cell = row[col_idx] if col_idx < len(row) else ''
        if is_missing(cell):
            # Missing values fail all comparisons except !=
            if operator == '!=':
                filtered.append(row)
            continue

        try:
            if col_type == 'numeric':
                cell_num = float(cell)
                val_num = float(value_str)
                if _compare(cell_num, val_num, operator):
                    filtered.append(row)
            else:
                # Text comparison
                if _compare(str(cell).strip(), value_str, operator):
                    filtered.append(row)
        except (ValueError, TypeError):
            # If conversion fails, do string comparison
            if _compare(str(cell).strip(), value_str, operator):
                filtered.append(row)

    return filtered


def _compare(a, b, operator):
    """Compare two values with the given operator."""
    if operator == '>':
        return a > b
    elif operator == '<':
        return a < b
    elif operator == '>=':
        return a >= b
    elif operator == '<=':
        return a <= b
    elif operator == '==':
        return a == b
    elif operator == '!=':
        return a != b
    return False


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def apply_sort(rows, headers, col_types, sort_column):
    """
    Sort rows by a specified column. Handles numeric vs text sorting.
    Returns sorted list of rows.
    """
    if sort_column not in headers:
        raise ValueError(
            f"Sort column '{sort_column}' not found. "
            f"Available columns: {', '.join(headers)}"
        )

    col_idx = headers.index(sort_column)
    col_type = col_types.get(sort_column, 'text')

    def sort_key(row):
        cell = row[col_idx] if col_idx < len(row) else ''
        if is_missing(cell):
            # Missing values sort last
            if col_type == 'numeric':
                return (1, float('inf'), '')
            return (1, '', '')
        if col_type == 'numeric':
            n = try_parse_numeric(cell)
            if n is not None:
                return (0, float(n), '')
            return (0, float('-inf'), str(cell))
        return (0, str(cell).strip().lower(), '')

    return sorted(rows, key=sort_key)


# ---------------------------------------------------------------------------
# Joining / Merging
# ---------------------------------------------------------------------------

def apply_join(rows_left, headers_left, rows_right, headers_right, key_column):
    """
    Perform an inner join on a shared key column.

    Returns (combined_headers, combined_rows).

    Columns from the right side that also appear on the left (except the key)
    get a '_right' suffix to avoid name collisions.
    """
    if key_column not in headers_left:
        raise ValueError(
            f"Join key '{key_column}' not found in left/primary file. "
            f"Columns: {', '.join(headers_left)}"
        )
    if key_column not in headers_right:
        raise ValueError(
            f"Join key '{key_column}' not found in right/secondary file. "
            f"Columns: {', '.join(headers_right)}"
        )

    key_idx_left = headers_left.index(key_column)
    key_idx_right = headers_right.index(key_column)

    # Build combined headers
    combined_headers = list(headers_left)
    for h in headers_right:
        if h == key_column:
            continue  # key column already present
        if h in combined_headers:
            combined_headers.append(h + '_right')
        else:
            combined_headers.append(h)

    # Index right rows by key
    right_index = defaultdict(list)
    for row in rows_right:
        key_val = row[key_idx_right].strip().lower() if key_idx_right < len(row) else ''
        right_index[key_val].append(row)

    # Perform join
    combined_rows = []
    for left_row in rows_left:
        key_val = left_row[key_idx_left].strip().lower() if key_idx_left < len(left_row) else ''

        matching_rights = right_index.get(key_val, [])
        if not matching_rights:
            continue  # inner join: skip non-matching

        for right_row in matching_rights:
            new_row = list(left_row)
            for idx_r, h_r in enumerate(headers_right):
                if h_r == key_column:
                    continue
                new_row.append(right_row[idx_r] if idx_r < len(right_row) else '')
            combined_rows.append(new_row)

    return combined_headers, combined_rows


# ---------------------------------------------------------------------------
# Output / Reporting
# ---------------------------------------------------------------------------

def output_csv(filepath, headers, rows):
    """Write headers and rows to a CSV file."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def format_number(value, precision=2):
    """Format a number for display, handling None."""
    if value is None:
        return 'N/A'
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    return str(value)


def generate_report(filepaths, headers, rows, col_types, missing_counts, warnings):
    """
    Generate a formatted text report string.
    """
    lines = []
    sep = '=' * 60

    lines.append(sep)
    lines.append("CSV DATA PIPELINE - ANALYSIS REPORT")
    lines.append(sep)
    lines.append(f"File(s): {', '.join(filepaths)}")
    lines.append(f"Rows: {len(rows)}")
    lines.append(f"Columns: {len(headers)}")
    lines.append(sep)
    lines.append("")

    if warnings:
        lines.append("WARNINGS:")
        for w in warnings:
            lines.append(f"  [!] {w}")
        lines.append("")
        lines.append(sep)
        lines.append("")

    if not headers:
        lines.append("No columns to analyze.")
        return '\n'.join(lines)

    if not rows:
        lines.append("No data rows to analyze.")
        return '\n'.join(lines)

    for col_idx, col_name in enumerate(headers):
        col_type = col_types.get(col_name, 'text')
        missing = missing_counts.get(col_name, 0)
        missing_pct = (missing / len(rows) * 100) if rows else 0

        lines.append(f"Column: {col_name}  ({col_type})")
        lines.append(f"  Missing: {missing} ({missing_pct:.1f}%)")

        col_values = []
        for row in rows:
            if col_idx < len(row):
                col_values.append(row[col_idx])
            else:
                col_values.append('')

        if col_type == 'numeric':
            stats = compute_numeric_stats(col_values)
            lines.append(
                f"  Count: {stats['count']}, "
                f"Mean: {format_number(stats['mean'])}, "
                f"Median: {format_number(stats['median'])}, "
                f"Min: {format_number(stats['min'])}, "
                f"Max: {format_number(stats['max'])}, "
                f"StdDev: {format_number(stats['std_dev'])}"
            )
        elif col_type == 'date':
            # For dates, show range
            dates = []
            for v in col_values:
                d = try_parse_date(v)
                if d is not None:
                    dates.append(d)
            if dates:
                lines.append(f"  Earliest: {min(dates)}, Latest: {max(dates)}")
                lines.append(f"  Distinct dates: {len(set(dates))}")
            else:
                lines.append(f"  No parseable dates found.")
        else:
            # Text column
            freqs = compute_text_frequencies(col_values, top_n=5)
            if freqs:
                lines.append(f"  Top {len(freqs)} most frequent values:")
                for val, count in freqs:
                    display_val = val if len(val) <= 40 else val[:37] + '...'
                    lines.append(f"    \"{display_val}\": {count}")
            else:
                lines.append(f"  (all values missing)")
        lines.append("")

    lines.append(sep)
    lines.append("END OF REPORT")
    lines.append(sep)

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='CSV Data Pipeline and Reporting Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_pipeline.py data.csv
  python csv_pipeline.py data.csv --filter "age>30" --sort name
  python csv_pipeline.py data.csv --join other.csv --key id --output merged.csv
  python csv_pipeline.py file1.csv file2.csv --sort date --output combined.csv
        """
    )
    parser.add_argument(
        'files', nargs='+',
        help='One or more CSV file paths to process'
    )
    parser.add_argument(
        '--filter', '-f', dest='filter_condition', default=None,
        help='Filter rows by condition (e.g., "age>30", "name==John")'
    )
    parser.add_argument(
        '--sort', '-s', dest='sort_column', default=None,
        help='Sort output by the specified column name'
    )
    parser.add_argument(
        '--join', '-j', dest='join_file', default=None,
        help='Merge with another CSV file on a shared key column'
    )
    parser.add_argument(
        '--key', '-k', dest='key_column', default=None,
        help='Key column for join (required when --join is used)'
    )
    parser.add_argument(
        '--output', '-o', dest='output_file', default=None,
        help='Output the processed result to a CSV file'
    )
    parser.add_argument(
        '--no-report', dest='no_report', action='store_true',
        help='Suppress the formatted text report on stdout'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    all_warnings = []

    # ------------------------------------------------------------------
    # 1. Read primary input files
    # ------------------------------------------------------------------
    primary_headers = None
    primary_rows = []

    for filepath in args.files:
        try:
            hdrs, rows, warns = read_csv_file(filepath)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        all_warnings.extend(warns)

        if not hdrs and not rows:
            all_warnings.append(f"File '{filepath}' is empty, skipping.")
            continue

        if primary_headers is None:
            primary_headers = hdrs
            primary_rows = rows
        else:
            # Concatenate: check column compatibility
            if hdrs != primary_headers:
                all_warnings.append(
                    f"File '{filepath}' has different columns than previous file(s). "
                    f"Expected: {primary_headers}, Got: {hdrs}. "
                    f"Rows will be appended with alignment by position."
                )
                # Align by position: use union of headers
                # For simplicity, keep the first file's headers and truncate/pad
                # rows from subsequent files
                aligned_rows = []
                for row in rows:
                    if len(row) < len(primary_headers):
                        aligned_rows.append(
                            list(row) + [''] * (len(primary_headers) - len(row))
                        )
                    elif len(row) > len(primary_headers):
                        aligned_rows.append(row[:len(primary_headers)])
                    else:
                        aligned_rows.append(row)
                primary_rows.extend(aligned_rows)
            else:
                primary_rows.extend(rows)

    if primary_headers is None:
        print("ERROR: No valid data read from input files.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Handle --join
    # ------------------------------------------------------------------
    if args.join_file:
        if not args.key_column:
            print(
                "ERROR: --key is required when using --join.",
                file=sys.stderr
            )
            sys.exit(1)

        try:
            join_hdrs, join_rows, join_warns = read_csv_file(args.join_file)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        all_warnings.extend(join_warns)

        if not join_hdrs:
            print(
                f"ERROR: Join file '{args.join_file}' has no valid data.",
                file=sys.stderr
            )
            sys.exit(1)

        try:
            primary_headers, primary_rows = apply_join(
                primary_rows, primary_headers,
                join_rows, join_hdrs,
                args.key_column
            )
        except ValueError as e:
            print(f"ERROR: Join failed: {e}", file=sys.stderr)
            sys.exit(1)

        if not primary_rows:
            all_warnings.append(
                f"Join on '{args.key_column}' produced zero matching rows."
            )

    # ------------------------------------------------------------------
    # 3. Detect column types (on current data)
    # ------------------------------------------------------------------
    col_types = detect_column_types(primary_headers, primary_rows)

    # ------------------------------------------------------------------
    # 4. Apply --filter
    # ------------------------------------------------------------------
    if args.filter_condition:
        try:
            before = len(primary_rows)
            primary_rows = apply_filter(
                primary_rows, primary_headers, col_types, args.filter_condition
            )
            after = len(primary_rows)
            if before != after:
                all_warnings.append(
                    f"Filter '{args.filter_condition}' matched {after} of {before} rows."
                )
        except ValueError as e:
            print(f"ERROR: Filter failed: {e}", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # 5. Apply --sort
    # ------------------------------------------------------------------
    if args.sort_column:
        try:
            primary_rows = apply_sort(
                primary_rows, primary_headers, col_types, args.sort_column
            )
        except ValueError as e:
            print(f"ERROR: Sort failed: {e}", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # 6. Recompute types (data may have changed after join)
    # ------------------------------------------------------------------
    col_types = detect_column_types(primary_headers, primary_rows)
    missing_counts = count_missing(primary_headers, primary_rows)

    # ------------------------------------------------------------------
    # 7. Output to CSV if requested
    # ------------------------------------------------------------------
    if args.output_file:
        try:
            output_csv(args.output_file, primary_headers, primary_rows)
            print(f"Output written to: {args.output_file}")
        except OSError as e:
            print(f"ERROR: Could not write output file: {e}", file=sys.stderr)
            sys.exit(1)

    # ------------------------------------------------------------------
    # 8. Generate and display report
    # ------------------------------------------------------------------
    if not args.no_report:
        report = generate_report(
            filepaths=args.files,
            headers=primary_headers,
            rows=primary_rows,
            col_types=col_types,
            missing_counts=missing_counts,
            warnings=all_warnings,
        )
        print(report)


if __name__ == '__main__':
    main()
