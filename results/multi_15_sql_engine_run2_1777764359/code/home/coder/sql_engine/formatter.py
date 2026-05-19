"""Formatted ASCII table renderer for query results."""


def format_table(columns: list[str], rows: list[tuple]) -> str:
    """Render query results as an ASCII table with aligned columns.

    Args:
        columns: List of column header strings.
        rows: List of row tuples.

    Returns:
        A string containing the formatted ASCII table.
    """
    if not columns:
        return "(empty result set)"

    # Determine column widths
    col_widths = []
    for i, col_name in enumerate(columns):
        max_width = len(str(col_name))
        for row in rows:
            if i < len(row):
                cell = str(row[i]) if row[i] is not None else 'NULL'
                max_width = max(max_width, len(cell))
        col_widths.append(max_width)

    def format_row(values, widths, is_header=False):
        """Format a single row of the table."""
        parts = []
        for i, (val, w) in enumerate(zip(values, widths)):
            if isinstance(val, (int, float)) and not is_header:
                # Right-align numbers
                parts.append(f" {str(val):>{w}} ")
            else:
                # Left-align strings and headers
                s = str(val) if val is not None else 'NULL'
                parts.append(f" {s:<{w}} ")
        return "|" + "|".join(parts) + "|"

    def separator(widths):
        """Build a horizontal separator line."""
        return "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    lines = []
    lines.append(separator(col_widths))
    lines.append(format_row(columns, col_widths, is_header=True))
    lines.append(separator(col_widths))

    for row in rows:
        lines.append(format_row(row, col_widths))

    lines.append(separator(col_widths))

    if not rows:
        lines.append(f"({len(rows)} rows)")

    return "\n".join(lines)
