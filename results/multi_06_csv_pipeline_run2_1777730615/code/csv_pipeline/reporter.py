"""Formatted table display and CSV output."""

import csv
import sys


def _col_widths(columns: list[str], rows: list[dict], min_width: int = 5, max_width: int = 50) -> dict:
    """Calculate display widths for each column."""
    widths = {}
    for col in columns:
        w = len(col)
        for row in rows:
            v = str(row.get(col, ""))
            w = max(w, len(v))
        widths[col] = max(min_width, min(w, max_width))
    return widths


def _truncate(value: str, width: int) -> str:
    """Truncate a string to fit within width."""
    s = str(value)
    if len(s) > width:
        return s[:width - 1] + "…"
    return s


def _format_value(v: str, width: int) -> str:
    """Left-justify a string value to the given width."""
    return _truncate(v, width).ljust(width)


def format_table(columns: list[str], rows: list[dict], column_types: dict,
                 stats: dict, frequencies: dict, missing: dict) -> None:
    """Print a formatted text table to stdout with analysis summary."""
    if not columns:
        print("No data to display.")
        return

    widths = _col_widths(columns, rows)
    total_width = sum(widths.values()) + (3 * (len(columns) - 1)) + 2  # for separators/borders

    # Header
    header_parts = []
    for col in columns:
        header_parts.append(_format_value(col, widths[col]))
    header = " | ".join(header_parts)
    print(header)
    print("-" * len(header))

    # Data rows (limit to 50 for display)
    display_rows = rows[:50]
    for row in display_rows:
        parts = []
        for col in columns:
            v = row.get(col, "")
            parts.append(_format_value(v, widths[col]))
        print(" | ".join(parts))

    if len(rows) > 50:
        print(f"... ({len(rows) - 50} more rows not shown)")

    # Summary section
    print()
    print("=" * total_width)
    print("SUMMARY")
    print("=" * total_width)

    for col in columns:
        col_type = column_types.get(col, "text")
        miss = missing.get(col, 0)
        print(f"\n--- {col} ({col_type}) ---")
        print(f"  Missing values: {miss}")

        # Numeric stats
        if col_type in ("int", "float") and stats.get(col):
            s = stats[col]
            print(f"  Count: {s['count']}")
            print(f"  Mean:  {s['mean']:.4f}")
            print(f"  Median: {s['median']:.4f}")
            print(f"  Min:   {s['min']:.4f}")
            print(f"  Max:   {s['max']:.4f}")
            print(f"  Stdev: {s['stdev']:.4f}")

        # Top frequencies (only for text columns)
        if col_type == "text":
            freqs = frequencies.get(col, [])
            if freqs:
                print("  Top values:")
                for val, cnt in freqs[:5]:
                    display_val = val if len(val) <= 40 else val[:37] + "..."
                    print(f"    {display_val}: {cnt}")


def write_csv(path: str, columns: list[str], rows: list[dict]) -> None:
    """Write processed rows to a CSV file."""
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                # Ensure all columns present
                out_row = {col: row.get(col, "") for col in columns}
                writer.writerow(out_row)
        print(f"Output written to '{path}' ({len(rows)} rows).", file=sys.stderr)
    except OSError as e:
        print(f"Error: Could not write to '{path}': {e}", file=sys.stderr)
        sys.exit(1)
