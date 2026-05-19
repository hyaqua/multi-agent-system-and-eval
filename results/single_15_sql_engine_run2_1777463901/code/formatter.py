"""ASCII Table Formatter - Formats result tables for display."""


def format_ascii_table(table) -> str:
    """Format a Table object as an ASCII table with headers and alignment."""
    if not table.columns:
        return "(empty result)"

    columns = table.columns
    rows = table.rows

    # Calculate column widths
    col_widths = [len(col) for col in columns]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build separator line
    sep = '+' + '+'.join('-' * (w + 2) for w in col_widths) + '+'

    # Build header
    header = '|' + '|'.join(f' {columns[i]:<{col_widths[i]}} ' for i in range(len(columns))) + '|'

    # Build data rows (right-align numbers, left-align strings)
    data_lines = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            cell_str = str(cell)
            # Right-align if numeric, left-align if string
            if _is_numeric(cell_str):
                cells.append(f' {cell_str:>{col_widths[i]}} ')
            else:
                cells.append(f' {cell_str:<{col_widths[i]}} ')
        data_lines.append('|' + '|'.join(cells) + '|')

    # Build result
    result_lines = [sep, header, sep]
    for line in data_lines:
        result_lines.append(line)
    result_lines.append(sep)

    if rows:
        result_lines.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    else:
        result_lines.append("(0 rows)")

    return '\n'.join(result_lines)


def _is_numeric(s: str) -> bool:
    """Check if a string represents a number."""
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False
