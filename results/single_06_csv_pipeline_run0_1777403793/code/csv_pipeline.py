#!/usr/bin/env python3
"""
CSV Data Pipeline and Reporting Tool
====================================
Reads CSV files, performs cleaning/transformation/analysis, and outputs reports.

Usage:
    python csv_pipeline.py file1.csv [file2.csv ...] [options]
"""

import sys
import argparse
import csv
import io
import os
import math
from collections import Counter
from datetime import datetime
from statistics import median, stdev


# ---------------------------------------------------------------------------
# 1. CSV reading
# ---------------------------------------------------------------------------

def read_csv(filepath):
    """Read a CSV file and return (headers, rows). Handles quoted fields."""
    try:
        with open(filepath, 'r', encoding='utf-8-sig', newline='') as fh:
            reader = csv.reader(fh)
            try:
                headers = next(reader)
            except StopIteration:
                print(f"Warning: '{filepath}' is empty.", file=sys.stderr)
                return [], []
            headers = [h.strip() for h in headers]
            rows = []
            for i, row in enumerate(reader, start=2):
                rows.append(row)
        return headers, rows
    except FileNotFoundError:
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Cannot read '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)


def normalize_rows(headers, rows):
    """
    Normalise rows to match header length.
    Warn about inconsistent column counts.
    """
    ncols = len(headers)
    normalised = []
    warned = False
    for i, row in enumerate(rows):
        if len(row) < ncols:
            if not warned:
                print(f"Warning: rows with fewer columns than header detected "
                      f"(padding with empty strings).", file=sys.stderr)
                warned = True
            row = row + [''] * (ncols - len(row))
        elif len(row) > ncols:
            if not warned:
                print(f"Warning: rows with more columns than header detected "
                      f"(truncating).", file=sys.stderr)
                warned = True
            row = row[:ncols]
        normalised.append(row)
    return normalised


# ---------------------------------------------------------------------------
# 2. Type detection
# ---------------------------------------------------------------------------

DATE_FORMATS = [
    '%Y-%m-%d',
    '%Y/%m/%d',
    '%m/%d/%Y',
    '%m/%d/%y',
    '%d/%m/%Y',
    '%d-%m-%Y',
    '%Y%m%d',
    '%d-%b-%Y',
    '%d %b %Y',
    '%B %d, %Y',
    '%Y-%m-%d %H:%M:%S',
    '%Y/%m/%d %H:%M:%S',
    '%m/%d/%Y %H:%M',
]


def _try_parse_numeric(val):
    """Try parsing as int, then float. Return (value, type_str) or (None, None)."""
    if val is None or val.strip() == '':
        return None, None
    v = val.strip()
    # Try int
    try:
        intval = int(v)
        # Check it round-trips (avoid float-like ints like "1.0" being int)
        if str(intval) == v:
            return intval, 'integer'
    except ValueError:
        pass
    # Try float
    try:
        floatval = float(v)
        return floatval, 'float'
    except ValueError:
        pass
    return None, None


def _try_parse_date(val):
    """Try parsing as date. Return (datetime, 'date') or (None, None)."""
    if val is None or val.strip() == '':
        return None, None
    v = val.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(v, fmt)
            return dt, 'date'
        except ValueError:
            continue
    return None, None


def detect_types(headers, rows):
    """
    Detect column types: 'numeric' (int/float), 'date', 'text'.
    Uses a sampling approach (first 200 rows).
    Returns dict: column_name -> type string.
    """
    ncols = len(headers)
    # gather non-empty values per column
    col_values = {col: [] for col in headers}
    for row in rows[:200]:
        for j, val in enumerate(row):
            if j < ncols:
                stripped = val.strip() if val else ''
                if stripped:
                    col_values[headers[j]].append(stripped)

    types = {}
    for col in headers:
        vals = col_values[col]
        if not vals:
            types[col] = 'text'   # no data → default text
            continue

        num_count = 0
        date_count = 0
        for v in vals:
            num_val, _ = _try_parse_numeric(v)
            if num_val is not None:
                num_count += 1
            else:
                dt_val, _ = _try_parse_date(v)
                if dt_val is not None:
                    date_count += 1

        total = len(vals)
        if num_count / total >= 0.7:
            types[col] = 'numeric'
        elif date_count / total >= 0.7:
            types[col] = 'date'
        else:
            types[col] = 'text'

    return types


# ---------------------------------------------------------------------------
# 3. Missing value reporting
# ---------------------------------------------------------------------------

def count_missing(headers, rows):
    """Return dict: column_name -> count of missing/empty values."""
    missing = {col: 0 for col in headers}
    ncols = len(headers)
    for row in rows:
        for j in range(ncols):
            val = row[j] if j < len(row) else ''
            if val is None or val.strip() == '':
                missing[headers[j]] += 1
    return missing


# ---------------------------------------------------------------------------
# 4. Numeric statistics
# ---------------------------------------------------------------------------

def numeric_stats(headers, rows, types):
    """Compute stats for numeric columns. Returns dict keyed by column."""
    ncols = len(headers)
    col_numbers = {col: [] for col in headers if types.get(col) == 'numeric'}

    for row in rows:
        for j in range(ncols):
            col = headers[j]
            if col in col_numbers:
                val = row[j] if j < len(row) else ''
                num_val, _ = _try_parse_numeric(val)
                if num_val is not None:
                    col_numbers[col].append(float(num_val))

    stats = {}
    for col, nums in col_numbers.items():
        if not nums:
            stats[col] = {
                'count': 0, 'mean': None, 'median': None,
                'min': None, 'max': None, 'stddev': None
            }
            continue
        n = len(nums)
        try:
            m = sum(nums) / n
        except Exception:
            m = None
        try:
            med = median(nums)
        except Exception:
            med = None
        try:
            sdev = stdev(nums) if n >= 2 else 0.0
        except Exception:
            sdev = None

        stats[col] = {
            'count': n,
            'mean': m,
            'median': med,
            'min': min(nums),
            'max': max(nums),
            'stddev': sdev,
        }
    return stats


# ---------------------------------------------------------------------------
# 5. Text frequency
# ---------------------------------------------------------------------------

def text_frequencies(headers, rows, types, top_n=5):
    """Return {col: [(value, count), ...]} for text columns."""
    ncols = len(headers)
    text_cols = [col for col in headers if types.get(col) == 'text']
    counters = {col: Counter() for col in text_cols}

    for row in rows:
        for j in range(ncols):
            col = headers[j]
            if col in counters:
                val = row[j] if j < len(row) else ''
                if val is not None and val.strip() != '':
                    counters[col][val.strip()] += 1

    freq = {}
    for col, counter in counters.items():
        freq[col] = counter.most_common(top_n)
    return freq


# ---------------------------------------------------------------------------
# 6. Filtering
# ---------------------------------------------------------------------------

def parse_filter_expression(expr):
    """
    Parse a filter expression like 'age>30', 'name=John', 'price<=9.99'.
    Supports operators: =, !=, >, >=, <, <=, contains=
    Returns (column, op, value).
    """
    # Order matters: longer / more-specific patterns first
    # '=' must come after 'contains=' to avoid matching inside 'contains='
    ops = [('contains=', 'contains'), ('!=', '!='), ('>=', '>='), ('<=', '<='),
           ('=', '='), ('>', '>'), ('<', '<')]
    for op_str, op_name in ops:
        if op_str in expr:
            idx = expr.find(op_str)
            col = expr[:idx].strip()
            val = expr[idx + len(op_str):].strip()
            return col, op_name, val
    raise ValueError(f"Cannot parse filter expression: {expr}")


def apply_filter(headers, rows, filter_expr):
    """Filter rows based on a condition. Returns filtered rows."""
    col, op, val = parse_filter_expression(filter_expr)

    if col not in headers:
        print(f"Warning: filter column '{col}' not found. No filtering applied.", file=sys.stderr)
        return rows

    col_idx = headers.index(col)
    filtered = []

    # Determine comparison type from the column's detected type
    types = detect_types(headers, rows)

    for row in rows:
        cell = row[col_idx] if col_idx < len(row) else ''
        cell_stripped = cell.strip() if cell else ''

        if types.get(col) == 'numeric':
            # Try numeric comparison
            num_val, _ = _try_parse_numeric(cell_stripped)
            val_num, _ = _try_parse_numeric(val)
            if num_val is None or val_num is None:
                # Fall back to text
                if _text_compare(cell_stripped, val, op):
                    filtered.append(row)
                continue
            if _num_compare(float(num_val), float(val_num), op):
                filtered.append(row)
        elif types.get(col) == 'date':
            dt_val, _ = _try_parse_date(cell_stripped)
            dt_target, _ = _try_parse_date(val)
            if dt_val is None or dt_target is None:
                if _text_compare(cell_stripped, val, op):
                    filtered.append(row)
                continue
            if _num_compare(dt_val.timestamp(), dt_target.timestamp(), op):
                filtered.append(row)
        else:
            if _text_compare(cell_stripped, val, op):
                filtered.append(row)

    return filtered


def _num_compare(a, b, op):
    if op == '=':
        return a == b
    elif op == '!=':
        return a != b
    elif op == '>':
        return a > b
    elif op == '>=':
        return a >= b
    elif op == '<':
        return a < b
    elif op == '<=':
        return a <= b
    return False


def _text_compare(a, b, op):
    if op == '=':
        return a == b
    elif op == '!=':
        return a != b
    elif op == 'contains':
        return b in a
    elif op == '>':
        return a > b
    elif op == '>=':
        return a >= b
    elif op == '<':
        return a < b
    elif op == '<=':
        return a <= b
    return False


# ---------------------------------------------------------------------------
# 7. Sorting
# ---------------------------------------------------------------------------

def apply_sort(headers, rows, sort_col, reverse=False):
    """Sort rows by a column. Natural sort: tries numeric, then text."""
    if sort_col not in headers:
        print(f"Warning: sort column '{sort_col}' not found. No sorting applied.", file=sys.stderr)
        return rows

    col_idx = headers.index(sort_col)
    types = detect_types(headers, rows)

    def sort_key(row):
        cell = row[col_idx] if col_idx < len(row) else ''
        cell = cell.strip() if cell else ''
        if types.get(sort_col) == 'numeric':
            num_val, _ = _try_parse_numeric(cell)
            if num_val is not None:
                return (0, float(num_val), cell)
        # Try date
        dt_val, _ = _try_parse_date(cell)
        if dt_val is not None:
            return (1, dt_val.timestamp(), cell)
        return (2, 0, cell.lower())

    return sorted(rows, key=sort_key, reverse=reverse)


# ---------------------------------------------------------------------------
# 8. Joining
# ---------------------------------------------------------------------------

def apply_join(headers1, rows1, headers2, rows2, key_col):
    """
    Perform an inner join of two datasets on key_col.
    Returns (joined_headers, joined_rows).
    """
    if key_col not in headers1:
        print(f"Error: join key '{key_col}' not found in first file.", file=sys.stderr)
        sys.exit(1)
    if key_col not in headers2:
        print(f"Error: join key '{key_col}' not found in second file.", file=sys.stderr)
        sys.exit(1)

    idx1 = headers1.index(key_col)
    idx2 = headers2.index(key_col)

    # Build index for second file
    idx_map2 = {}
    for row in rows2:
        key = row[idx2].strip() if idx2 < len(row) else ''
        if key:
            idx_map2.setdefault(key, []).append(row)

    # Build joined headers
    # Prefix duplicate columns from file2 with file2 header name or 'file2_'
    joined_headers = list(headers1)
    for h in headers2:
        if h == key_col:
            continue  # key column appears once
        if h in joined_headers:
            joined_headers.append(f'file2_{h}')
        else:
            joined_headers.append(h)

    joined_rows = []
    for row1 in rows1:
        key = row1[idx1].strip() if idx1 < len(row1) else ''
        if key in idx_map2:
            for row2 in idx_map2[key]:
                new_row = list(row1)
                for j, h in enumerate(headers2):
                    if h == key_col:
                        continue
                    new_row.append(row2[j] if j < len(row2) else '')
                joined_rows.append(new_row)

    return joined_headers, joined_rows


# ---------------------------------------------------------------------------
# 9. Report formatting
# ---------------------------------------------------------------------------

def format_table(headers, rows, max_width=40):
    """Format data as a text table, returning a multi-line string."""
    if not headers:
        return "(empty dataset)"

    # Determine column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for j, cell in enumerate(row):
            if j < len(widths):
                cell_str = str(cell) if cell is not None else ''
                widths[j] = max(widths[j], min(len(cell_str), max_width))

    def fmt_row(vals, is_header=False):
        parts = []
        for j, v in enumerate(vals):
            s = str(v) if v is not None else ''
            if len(s) > max_width:
                s = s[:max_width - 3] + '...'
            parts.append(f" {s:<{widths[j]}} ")
        line = '|' + '|'.join(parts) + '|'
        return line

    sep = '+' + '+'.join('-' * (w + 2) for w in widths) + '+'

    lines = [sep, fmt_row(headers, True), sep]
    # Show up to 50 data rows; summarise if more
    display_rows = rows
    if len(rows) > 50:
        display_rows = rows[:25] + rows[-25:]
        truncated = True
    else:
        truncated = False

    for row in display_rows:
        lines.append(fmt_row(row))

    if truncated:
        lines.insert(len(lines) - 25, f"... ({len(rows) - 50} rows omitted) ...")

    lines.append(sep)
    return '\n'.join(lines)


def print_report(headers, rows, types, missing, stats, freq):
    """Print a full analysis report to stdout."""
    print()
    print("=" * 60)
    print("  CSV DATA PIPELINE – ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nTotal rows: {len(rows)}")
    print(f"Total columns: {len(headers)}\n")

    # Column type summary
    print("─" * 60)
    print("COLUMN TYPES")
    print("─" * 60)
    for col in headers:
        print(f"  {col:<25s} : {types.get(col, 'unknown')}")
    print()

    # Missing values
    print("─" * 60)
    print("MISSING VALUES")
    print("─" * 60)
    for col in headers:
        m = missing.get(col, 0)
        pct = (m / max(len(rows), 1)) * 100
        print(f"  {col:<25s} : {m:5d}  ({pct:5.1f}%)")
    print()

    # Numeric statistics
    if stats:
        print("─" * 60)
        print("NUMERIC STATISTICS")
        print("─" * 60)
        for col, s in stats.items():
            print(f"\n  [{col}]")
            print(f"    Count     : {s['count']}")
            if s['mean'] is not None:
                print(f"    Mean      : {s['mean']:.4f}")
                print(f"    Median    : {s['median']:.4f}")
                print(f"    Min       : {s['min']:.4f}")
                print(f"    Max       : {s['max']:.4f}")
                print(f"    Std Dev   : {s['stddev']:.4f}")
            else:
                print("    (no numeric data)")
        print()

    # Text frequencies
    if freq:
        print("─" * 60)
        print("TOP 5 FREQUENT VALUES (text columns)")
        print("─" * 60)
        for col, top_list in freq.items():
            if not top_list:
                continue
            print(f"\n  [{col}]")
            for val, count in top_list:
                print(f"    {val[:50]:<50s} : {count}")
        print()

    # Data preview
    print("─" * 60)
    print("DATA PREVIEW (first 10 rows)")
    print("─" * 60)
    print(format_table(headers, rows[:10]))
    print()


# ---------------------------------------------------------------------------
# 10. Output
# ---------------------------------------------------------------------------

def write_csv(filepath, headers, rows):
    """Write data to a CSV file."""
    try:
        with open(filepath, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"Output written to '{filepath}' ({len(rows)} rows, {len(headers)} columns).")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 11. Main CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description='CSV Data Pipeline – read, clean, transform, and report on CSV files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_pipeline.py data.csv
  python csv_pipeline.py data.csv --filter 'age>30' --sort name
  python csv_pipeline.py data.csv --output cleaned.csv
  python csv_pipeline.py a.csv --join b.csv --key id --output merged.csv
        """
    )
    parser.add_argument(
        'files', nargs='+', metavar='FILE',
        help='One or more CSV files to process.'
    )
    parser.add_argument(
        '--filter', '-f', dest='filter_expr', default=None,
        help='Filter rows by condition (e.g. "age>30", "name=John", "price<9.99").'
    )
    parser.add_argument(
        '--sort', '-s', dest='sort_col', default=None,
        help='Sort output by column name.'
    )
    parser.add_argument(
        '--sort-desc', action='store_true', default=False,
        help='Sort in descending order.'
    )
    parser.add_argument(
        '--join', '-j', dest='join_file', default=None,
        help='Join with another CSV file (inner join).'
    )
    parser.add_argument(
        '--key', '-k', dest='join_key', default=None,
        help='Column name to use as join key.'
    )
    parser.add_argument(
        '--output', '-o', dest='output_file', default=None,
        help='Write processed data to CSV file.'
    )
    parser.add_argument(
        '--no-report', action='store_true', default=False,
        help='Suppress the text report (only write output file).'
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Read primary file(s)
    all_headers = None
    all_rows = []

    for fpath in args.files:
        headers, rows = read_csv(fpath)
        if not headers:
            continue

        rows = normalize_rows(headers, rows)

        if all_headers is None:
            all_headers = headers
            all_rows = rows
        else:
            # Combine: align columns
            if headers != all_headers:
                # Merge columns: union of all columns
                new_headers = list(all_headers)
                for h in headers:
                    if h not in new_headers:
                        new_headers.append(h)
                # Re-align existing rows
                old_header_set = set(all_headers)
                new_all_rows = []
                for row in all_rows:
                    new_row = []
                    for h in new_headers:
                        if h in old_header_set:
                            idx = all_headers.index(h)
                            new_row.append(row[idx] if idx < len(row) else '')
                        else:
                            new_row.append('')
                    new_all_rows.append(new_row)
                all_rows = new_all_rows

                # Add new rows
                for row in rows:
                    new_row = []
                    for h in new_headers:
                        if h in headers:
                            idx = headers.index(h)
                            new_row.append(row[idx] if idx < len(row) else '')
                        else:
                            new_row.append('')
                    all_rows.append(new_row)
                all_headers = new_headers
            else:
                all_rows.extend(rows)

    if all_headers is None:
        print("Error: No data loaded.", file=sys.stderr)
        sys.exit(1)

    # Join if requested
    if args.join_file:
        if not args.join_key:
            print("Error: --key is required when using --join.", file=sys.stderr)
            sys.exit(1)
        join_headers, join_rows = read_csv(args.join_file)
        join_rows = normalize_rows(join_headers, join_rows)
        all_headers, all_rows = apply_join(
            all_headers, all_rows, join_headers, join_rows, args.join_key
        )

    # Filter
    if args.filter_expr:
        try:
            all_rows = apply_filter(all_headers, all_rows, args.filter_expr)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Sort
    if args.sort_col:
        all_rows = apply_sort(all_headers, all_rows, args.sort_col, reverse=args.sort_desc)

    # Analyses
    types = detect_types(all_headers, all_rows)
    missing = count_missing(all_headers, all_rows)
    stats = numeric_stats(all_headers, all_rows, types)
    freq = text_frequencies(all_headers, all_rows, types)

    # Output CSV
    if args.output_file:
        write_csv(args.output_file, all_headers, all_rows)

    # Report
    if not args.no_report:
        print_report(all_headers, all_rows, types, missing, stats, freq)


if __name__ == '__main__':
    main()
