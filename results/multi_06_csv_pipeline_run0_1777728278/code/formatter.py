"""Format data as aligned text table and write CSV output."""

import csv
import os


def _column_widths(rows: list, columns: list) -> dict:
    """Compute the display width needed for each column."""
    widths = {}
    for col in columns:
        widths[col] = len(str(col))
    for row in rows:
        for col in columns:
            cell = str(row.get(col, ""))
            widths[col] = max(widths[col], len(cell))
    return widths


def format_table(rows: list, columns: list) -> str:
    """Build an aligned text table from rows (list of dicts)."""
    if not columns:
        return "(no columns)\n"

    widths = _column_widths(rows, columns)

    def _pad(val, col):
        return str(val).ljust(widths[col])

    lines = []
    # Header
    header = " | ".join(_pad(col, col) for col in columns)
    lines.append(header)
    # Separator
    sep = "-+-".join("-" * widths[col] for col in columns)
    lines.append(sep)

    # Data rows
    for row in rows:
        line = " | ".join(_pad(row.get(col, ""), col) for col in columns)
        lines.append(line)

    return "\n".join(lines) + "\n"


def format_summary(
    column_types: dict,
    missing_counts: dict,
    statistics: dict,
    text_frequencies: dict,
    warnings: list,
) -> str:
    """Produce the statistic and frequency summary sections."""
    parts = []

    # Warnings
    if warnings:
        parts.append("Warnings:")
        for w in warnings:
            parts.append(f"  - {w}")
        parts.append("")

    # Column types
    parts.append("Column Types:")
    for col, ctype in column_types.items():
        parts.append(f"  {col}: {ctype}")
    parts.append("")

    # Missing counts
    parts.append("Missing Value Counts:")
    for col, count in missing_counts.items():
        parts.append(f"  {col}: {count}")
    parts.append("")

    # Numeric statistics
    if statistics:
        parts.append("Numeric Statistics:")
        for col, stats in statistics.items():
            parts.append(f"  {col}:")
            for key, val in stats.items():
                parts.append(f"    {key}: {val}")
        parts.append("")

    # Text frequencies
    if text_frequencies:
        parts.append("Top-5 Text Frequencies:")
        for col, freq_list in text_frequencies.items():
            parts.append(f"  {col}:")
            if freq_list:
                for value, count in freq_list:
                    parts.append(f"    {value!r}: {count}")
            else:
                parts.append("    (no data)")
        parts.append("")

    return "\n".join(parts)


def write_csv(filepath: str, headers: list, rows: list):
    """Write rows (list of dicts) to a CSV file using csv.writer."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])
