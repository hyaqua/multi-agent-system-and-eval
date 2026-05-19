"""Command-line interface for csv_pipeline."""

import argparse
import sys

from . import reader, analyzer, operations, reporter


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all flags."""
    parser = argparse.ArgumentParser(
        prog="csv_pipeline",
        description="Read, analyze, filter, sort, join, and output CSV files.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more CSV file paths to process.",
    )
    parser.add_argument(
        "--filter",
        dest="filter_expr",
        metavar="EXPR",
        default=None,
        help="Filter rows by condition (e.g. 'age>30').",
    )
    parser.add_argument(
        "--sort",
        dest="sort_col",
        metavar="COLUMN",
        default=None,
        help="Sort rows by the given column name.",
    )
    parser.add_argument(
        "--join",
        dest="join_spec",
        metavar="KEY:FILE",
        default=None,
        help="Inner join with another CSV file on a shared key column "
             "(format: key_column:path/to/file.csv).",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output_path",
        metavar="PATH",
        default=None,
        help="Write processed result to a CSV file instead of stdout table.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 1. Read all input files and concatenate
    all_rows: list[dict] = []
    columns: list[str] = []

    for filepath in args.files:
        rows = reader.read_csv(filepath)
        if not rows:
            continue
        # Ensure all rows share the same column set as the first file
        if not all_rows:
            columns = list(rows[0].keys())
        else:
            # Normalize columns: all rows should have the same keys
            file_cols = list(rows[0].keys())
            # Make union of columns
            all_cols = list(dict.fromkeys(columns + file_cols))  # preserve order, unique
            # Re-normalize existing rows
            for r in all_rows:
                for c in all_cols:
                    if c not in r:
                        r[c] = ""
            columns = all_cols
            # Normalize new rows
            for r in rows:
                for c in all_cols:
                    if c not in r:
                        r[c] = ""
        all_rows.extend(rows)

    if not all_rows:
        print("No data loaded from input files.", file=sys.stderr)
        sys.exit(0)

    # Update columns after potential normalization
    columns = list(all_rows[0].keys())

    # 2. Join if requested
    if args.join_spec:
        if ":" not in args.join_spec:
            print("Error: --join argument must be in format 'key:file.csv'", file=sys.stderr)
            sys.exit(1)
        key_col, _, join_path = args.join_spec.partition(":")
        join_col = key_col.strip()
        join_file = join_path.strip()
        if not join_col or not join_file:
            print("Error: --join argument must be in format 'key:file.csv'", file=sys.stderr)
            sys.exit(1)
        right_rows = reader.read_csv(join_file)
        if not right_rows:
            print(f"Warning: Join file '{join_file}' is empty. Keeping original rows.", file=sys.stderr)
        else:
            all_rows = operations.join_datasets(all_rows, right_rows, join_col)
            if all_rows:
                columns = list(all_rows[0].keys())
            else:
                print("Warning: Join produced no matching rows.", file=sys.stderr)

    if not all_rows:
        print("No rows remain after processing.", file=sys.stderr)
        sys.exit(0)

    # 3. Filter
    if args.filter_expr:
        all_rows = operations.filter_rows(all_rows, args.filter_expr)
        if not all_rows:
            print("No rows match the filter condition.", file=sys.stderr)
            sys.exit(0)

    # 4. Analyze (detect types before sort so sort can use types)
    analysis = analyzer.analyze(all_rows)
    columns = analysis["columns"]  # ensure consistent column order
    column_types = analysis["types"]

    # 5. Sort
    if args.sort_col:
        if args.sort_col not in columns:
            print(f"Warning: Sort column '{args.sort_col}' not found in dataset. Skipping sort.", file=sys.stderr)
        else:
            all_rows = operations.sort_rows(all_rows, args.sort_col, column_types)

    # 6. Re-analyze after sort (types shouldn't change, but let's be safe)
    # Actually, types won't change and we already have stats. Good.

    # 7. Output
    if args.output_path:
        reporter.write_csv(args.output_path, columns, all_rows)
    else:
        reporter.format_table(
            columns, all_rows, column_types,
            analysis["stats"], analysis["frequencies"], analysis["missing"],
        )


if __name__ == "__main__":
    main()
