"""ASCII table formatter for displaying query results."""


def format_table(columns: list[str], rows: list[list], max_width: int = 40) -> str:
    """Format results as an ASCII table with borders.

    Args:
        columns: Column header names
        rows: List of row values (each row is a list of values)
        max_width: Maximum column width before truncation

    Returns:
        Formatted ASCII table string
    """
    if not columns:
        return "(empty result set)"

    # Convert all values to strings
    str_cols = [str(c) for c in columns]
    str_rows = []
    for row in rows:
        str_rows.append([str(v) if v is not None else 'NULL' for v in row])

    # Calculate column widths
    col_widths = []
    for i, col in enumerate(str_cols):
        max_w = len(col)
        for row in str_rows:
            if i < len(row):
                max_w = max(max_w, len(row[i]))
        # Cap at max_width
        col_widths.append(min(max_w, max_width))

    # Helper to truncate
    def truncate(s, w):
        if len(s) > w:
            return s[:w - 1] + '…'
        return s

    # Build separator line
    def separator():
        return '+' + '+'.join('-' * (w + 2) for w in col_widths) + '+'

    # Build a data row
    def format_row(values):
        parts = []
        for i, w in enumerate(col_widths):
            val = truncate(values[i], w) if i < len(values) else ''
            parts.append(f' {val:<{w}} ')
        return '|' + '|'.join(parts) + '|'

    lines = []
    lines.append(separator())
    lines.append(format_row(str_cols))
    lines.append(separator())
    for row in str_rows:
        lines.append(format_row(row))
    lines.append(separator())
    if len(str_rows) == 0:
        lines.append("(0 rows)")
    else:
        lines.append(f"({len(str_rows)} row{'s' if len(str_rows) != 1 else ''})")

    return '\n'.join(lines)
