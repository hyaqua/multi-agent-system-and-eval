"""
ASCII table formatter for query results.
"""

from typing import List, Dict, Any


def is_number(val) -> bool:
    """Check if a value is numeric (int or float, not bool)."""
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def format_table(rows: List[Dict[str, Any]]) -> str:
    """
    Format a list of dicts as an ASCII table with aligned columns.
    Numbers are right-aligned, strings and other values are left-aligned.
    """
    if not rows:
        return "No results."

    # Determine column order from the first row
    columns = list(rows[0].keys())

    # Calculate column widths (header vs data)
    col_widths = {}
    for col in columns:
        max_width = len(str(col))
        for row in rows:
            val = str(row.get(col, 'NULL') if row.get(col) is not None else 'NULL')
            max_width = max(max_width, len(val))
        col_widths[col] = max_width

    # Build separator line
    sep = '+' + '+'.join('-' * (col_widths[col] + 2) for col in columns) + '+'

    # Build header row
    header_cells = []
    for col in columns:
        header_cells.append(f" {str(col).ljust(col_widths[col])} ")
    header = '|' + '|'.join(header_cells) + '|'

    # Build data rows
    result_lines = [sep, header, sep]
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col, 'NULL')
            if val is None:
                display = 'NULL'
            else:
                display = str(val)

            if is_number(row.get(col)):
                # Right-align numbers
                cells.append(f" {display.rjust(col_widths[col])} ")
            else:
                # Left-align everything else
                cells.append(f" {display.ljust(col_widths[col])} ")
        line = '|' + '|'.join(cells) + '|'
        result_lines.append(line)

    result_lines.append(sep)
    return '\n'.join(result_lines)
