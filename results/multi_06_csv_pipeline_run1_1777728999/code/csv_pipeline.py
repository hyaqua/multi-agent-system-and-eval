#!/usr/bin/env python3
"""
CSV Data Pipeline and Reporting Tool

Reads one or more CSV files, detects data types, computes statistics,
and supports filtering, sorting, joining, and output to CSV or formatted console report.
"""

import argparse
import os
import sys
import warnings
from typing import Optional

import reader
import type_detector
import operations
import stats_calc as stats_mod
import reporter


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="CSV Data Pipeline – read, filter, sort, join, and report on CSV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_pipeline.py data.csv
  python csv_pipeline.py data.csv --filter "age>30" --sort name
  python csv_pipeline.py data.csv --join id:other.csv --output merged.csv
  python csv_pipeline.py data.csv --sort age --filter "dept=Sales"
        """
    )

    parser.add_argument(
        'files',
        nargs='+',
        help='One or more CSV file paths to process.'
    )
    parser.add_argument(
        '--filter', '-f',
        dest='filter_condition',
        default=None,
        help='Filter rows by condition, e.g. "age>30", "name=Alice".'
    )
    parser.add_argument(
        '--sort', '-s',
        dest='sort_column',
        default=None,
        help='Sort rows by the specified column name.'
    )
    parser.add_argument(
        '--sort-desc', '-d',
        dest='sort_desc',
        action='store_true',
        default=False,
        help='Sort in descending order (default: ascending).'
    )
    parser.add_argument(
        '--join', '-j',
        dest='join_spec',
        default=None,
        help='Merge with another CSV using format: key:file.csv or key1:key2:file.csv'
    )
    parser.add_argument(
        '--output', '-o',
        dest='output_file',
        default=None,
        help='Write processed data to a CSV file instead of stdout.'
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the CSV pipeline."""
    args = parse_args()

    # Validate input files exist
    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"ERROR: Input file not found: {filepath}", file=sys.stderr)
            sys.exit(1)

    # Read primary file (first file)
    primary_file = args.files[0]
    try:
        header, rows, missing_counts = reader.read_csv(primary_file)
    except Exception as e:
        print(f"ERROR: Failed to read '{primary_file}': {e}", file=sys.stderr)
        sys.exit(1)

    if not header:
        print("WARNING: No data found (empty file or no header).", file=sys.stderr)
        sys.exit(0)

    # For multiple files, just concatenate rows (with same schema expected)
    for extra_file in args.files[1:]:
        try:
            extra_header, extra_rows, extra_missing = reader.read_csv(extra_file)
        except Exception as e:
            print(f"ERROR: Failed to read '{extra_file}': {e}", file=sys.stderr)
            sys.exit(1)
        if extra_header == header:
            rows.extend(extra_rows)
            for col in header:
                missing_counts[col] += extra_missing.get(col, 0)
        else:
            print(
                f"WARNING: '{extra_file}' has different columns; "
                f"skipping for concatenation.",
                file=sys.stderr
            )

    # Detect types
    type_map = type_detector.detect_all_types(header, rows)

    # Print type summary
    reporter.print_type_summary(type_map)

    # Convert rows to typed values
    typed_rows = type_detector.convert_rows(header, rows, type_map)

    # Apply filter
    if args.filter_condition:
        try:
            typed_rows = operations.filter_rows(
                typed_rows, header, args.filter_condition, type_map
            )
            print(f"\nAfter filter '{args.filter_condition}': {len(typed_rows)} row(s)")
        except ValueError as e:
            print(f"ERROR: Filter failed - {e}", file=sys.stderr)
            sys.exit(1)

    # Apply join
    if args.join_spec:
        parts = args.join_spec.split(':')
        if len(parts) == 2:
            primary_key, secondary_file = parts
            secondary_key = primary_key
        elif len(parts) == 3:
            primary_key, secondary_key, secondary_file = parts
        else:
            print(
                "ERROR: --join format should be 'key:file.csv' or 'key1:key2:file.csv'",
                file=sys.stderr
            )
            sys.exit(1)

        if not os.path.isfile(secondary_file):
            print(f"ERROR: Join file not found: {secondary_file}", file=sys.stderr)
            sys.exit(1)

        try:
            header, typed_rows = operations.join_csvs(
                typed_rows, header, primary_key, secondary_file, secondary_key
            )
            # Re-detect types for joined data
            type_map = type_detector.detect_all_types(header, typed_rows)
            print(f"\nAfter join: {len(typed_rows)} row(s), {len(header)} column(s)")
        except ValueError as e:
            print(f"ERROR: Join failed - {e}", file=sys.stderr)
            sys.exit(1)

    # Apply sort
    if args.sort_column:
        try:
            typed_rows = operations.sort_rows(
                typed_rows, header, args.sort_column, descending=args.sort_desc
            )
            direction = "descending" if args.sort_desc else "ascending"
            print(f"\nSorted by '{args.sort_column}' ({direction})")
        except ValueError as e:
            print(f"ERROR: Sort failed - {e}", file=sys.stderr)
            sys.exit(1)

    # Compute statistics
    all_stats = stats_mod.compute_all_statistics(header, typed_rows, type_map)

    # Output
    if args.output_file:
        reporter.write_csv_output(args.output_file, header, typed_rows)
    else:
        # Print formatted table
        reporter.print_formatted_table(header, typed_rows, title="Data Preview")

    # Print statistics
    reporter.print_statistics(all_stats, type_map, missing_counts)


if __name__ == '__main__':
    main()
