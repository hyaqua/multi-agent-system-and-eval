"""
Reporter module – generates formatted text tables and writes CSV output.
"""

import csv
import sys
from typing import Any


def _col_widths(header: list, rows: list) -> dict:
    """Calculate the maximum display width for each column."""
    widths = {col: len(col) for col in header}
    for row in rows:
        for col in header:
            val = row.get(col)
            display = str(val) if val is not None else 'N/A'
            widths[col] = max(widths[col], len(display))
    return widths


def print_formatted_table(header: list, rows: list, title: str = None) -> None:
    """
    Print a formatted text table to stdout.

    Args:
        header: List of column names.
        rows: List of row dicts.
        title: Optional title to print above the table.
    """
    if not header:
        print("(No data)")
        return

    widths = _col_widths(header, rows)
    total_width = sum(widths.values()) + (3 * len(header)) + 1

    # Print title
    if title:
        print()
        print("=" * total_width)
        print(f"  {title}")
        print("=" * total_width)

    # Top border
    print("+" + "+".join("-" * (widths[col] + 2) for col in header) + "+")

    # Header row
    header_cells = "|".join(f" {col:<{widths[col]}} " for col in header)
    print(f"|{header_cells}|")

    # Separator
    print("+" + "+".join("-" * (widths[col] + 2) for col in header) + "+")

    # Data rows
    for row in rows:
        cells = []
        for col in header:
            val = row.get(col)
            display = str(val) if val is not None else 'N/A'
            cells.append(f" {display:<{widths[col]}} ")
        print(f"|{'|'.join(cells)}|")

    # Bottom border
    print("+" + "+".join("-" * (widths[col] + 2) for col in header) + "+")
    print(f"({len(rows)} row(s))")


def print_statistics(stats: dict, type_map: dict, missing_counts: dict = None) -> None:
    """
    Print summary statistics to stdout.

    Args:
        stats: Stats dict from statistics.compute_all_statistics().
        type_map: Dict mapping column_name -> type_string.
        missing_counts: Dict mapping column_name -> missing_count.
    """
    print()
    print("=" * 60)
    print("  SUMMARY STATISTICS")
    print("=" * 60)

    # Missing values
    if missing_counts:
        print()
        print("--- Missing Value Counts ---")
        for col, count in missing_counts.items():
            print(f"  {col}: {count} missing")

    # Numeric statistics
    numeric_stats = stats.get('numeric_stats', {})
    if numeric_stats:
        print()
        print("--- Numeric Columns ---")
        for col, s in numeric_stats.items():
            print(f"  [{col}] (type: {type_map.get(col, '?')})")
            print(f"    Count : {s['count']}")
            print(f"    Mean  : {s['mean']}")
            print(f"    Median: {s['median']}")
            print(f"    Min   : {s['min']}")
            print(f"    Max   : {s['max']}")
            print(f"    Stdev : {s['stdev']}")
            print()

    # Date statistics
    date_stats = stats.get('date_stats', {})
    if date_stats:
        print("--- Date Columns ---")
        for col, s in date_stats.items():
            print(f"  [{col}] (type: date)")
            print(f"    Count: {s['count']}")
            print(f"    Min  : {s['min']}")
            print(f"    Max  : {s['max']}")
            print()

    # Text frequencies
    text_freqs = stats.get('text_frequencies', {})
    if text_freqs:
        print("--- Text Columns (Top 5 Values) ---")
        for col, freqs in text_freqs.items():
            print(f"  [{col}] (type: {type_map.get(col, 'text')})")
            if not freqs:
                print("    (no data)")
            else:
                for val, count in freqs:
                    display = val if val is not None else 'N/A'
                    print(f"    {display:<30} : {count}")
            print()


def print_type_summary(type_map: dict) -> None:
    """Print a summary of detected column types."""
    print()
    print("--- Detected Column Types ---")
    for col, ctype in type_map.items():
        print(f"  {col}: {ctype}")


def write_csv_output(filepath: str, header: list, rows: list) -> None:
    """
    Write processed rows to a CSV file.

    Args:
        filepath: Output CSV file path.
        header: List of column names.
        rows: List of row dicts.
    """
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            # Convert values back to strings for CSV writing
            string_row = {}
            for col in header:
                val = row.get(col)
                if val is None:
                    string_row[col] = ''
                else:
                    string_row[col] = str(val)
            writer.writerow(string_row)

    print(f"\nOutput written to: {filepath}")
