#!/usr/bin/env python3
"""CSV Pipeline Tool – CLI entry point.

Usage examples:
    python main.py data.csv
    python main.py data.csv --filter 'age>30' --sort name --output out.csv
    python main.py left.csv right.csv --join id --filter 'score>50' --sort name
"""

import argparse
import sys
import os

from pipeline import Pipeline


def file_exists(path: str) -> str:
    """Argparse type checker that validates a file path exists."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"File not found: '{path}'")
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"Not a file: '{path}'")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process CSV files: filter, sort, join, and report.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=file_exists,
        help="One or more CSV file paths.",
    )
    parser.add_argument(
        "--filter",
        dest="filter_expr",
        metavar="EXPR",
        default=None,
        help="Filter rows by condition, e.g. 'age>30'.",
    )
    parser.add_argument(
        "--sort",
        dest="sort_col",
        metavar="COLUMN",
        default=None,
        help="Sort rows by the given column.",
    )
    parser.add_argument(
        "--sort-reverse",
        action="store_true",
        default=False,
        help="Sort in descending order.",
    )
    parser.add_argument(
        "--join",
        dest="join_key",
        metavar="KEY",
        default=None,
        help="Merge two CSV files on a shared key column (inner join).",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        metavar="PATH",
        default=None,
        help="Write processed CSV to this file.",
    )
    return parser


def run_pipeline(
    filepath: str,
    filter_expr=None,
    sort_col=None,
    sort_reverse=False,
    output_path=None,
) -> Pipeline:
    """Process a single CSV file through the pipeline and return it."""
    p = Pipeline()
    p.read_csv(filepath)

    if not p.headers:
        print(f"File '{filepath}' is empty. Skipping.", file=sys.stderr)
        return p

    p.infer_types()

    if filter_expr:
        p.filter_rows(filter_expr)

    if sort_col:
        p.sort_rows(sort_col, reverse=sort_reverse)

    p.missing_counts_calc()
    p.compute_statistics()

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    files = args.files

    # If join is requested we need at least two files
    if args.join_key:
        if len(files) < 2:
            print(
                "Error: --join requires at least two CSV files.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Process first two files for join
        p1 = Pipeline()
        p1.read_csv(files[0])
        if not p1.headers:
            print(f"Error: '{files[0]}' is empty.", file=sys.stderr)
            sys.exit(1)

        p2 = Pipeline()
        p2.read_csv(files[1])
        if not p2.headers:
            print(f"Error: '{files[1]}' is empty.", file=sys.stderr)
            sys.exit(1)

        p1.infer_types()
        p2.infer_types()

        # Perform join
        p1.join(p2, args.join_key)

        # Apply filter and sort on joined result
        if args.filter_expr:
            p1.filter_rows(args.filter_expr)
        if args.sort_col:
            p1.sort_rows(args.sort_col, reverse=args.sort_reverse)

        p1.missing_counts_calc()
        p1.compute_statistics()

        # Output
        if args.output_path:
            p1.write_output(args.output_path)
            print(f"Output written to '{args.output_path}'")
        p1.display_report()

        # Process remaining files independently
        for fpath in files[2:]:
            print(f"\n{'='*60}")
            print(f"File: {fpath}")
            print("=" * 60)
            p = run_pipeline(
                fpath,
                filter_expr=args.filter_expr,
                sort_col=args.sort_col,
                sort_reverse=args.sort_reverse,
                output_path=None,  # only one --output, used for join result
            )
            p.display_report()
    else:
        # No join – process each file independently
        for i, fpath in enumerate(files):
            if len(files) > 1:
                print(f"\n{'='*60}")
                print(f"File: {fpath}")
                print("=" * 60)

            output = args.output_path if i == 0 else None
            p = run_pipeline(
                fpath,
                filter_expr=args.filter_expr,
                sort_col=args.sort_col,
                sort_reverse=args.sort_reverse,
                output_path=output,
            )

            if output:
                p.write_output(output)
                print(f"Output written to '{output}'")

            p.display_report()


if __name__ == "__main__":
    main()
