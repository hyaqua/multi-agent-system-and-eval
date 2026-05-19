"""ASCII table formatter for query results."""


def _is_numeric_column(column, rows):
    """Check if all non-empty values in a column are numeric."""
    if not rows:
        return False
    for r in rows:
        v = r.get(column, "")
        if v != "" and v is not None:
            try:
                float(str(v))
            except (ValueError, TypeError):
                return False
    return True


def format_table(columns, rows):
    """
    Format a list of dicts as an ASCII table.
    Returns a string suitable for printing.
    """
    if not columns or not rows:
        # Handle empty result set
        if columns:
            widths = [len(str(c)) for c in columns]
            sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
            header = "|" + "|".join(
                f" {str(c).ljust(w)} " for c, w in zip(columns, widths)
            ) + "|"
            return f"{sep}\n{header}\n{sep}\n(0 rows)\n"
        return "(empty result)"

    # Compute column widths
    widths = []
    for col in columns:
        max_width = len(str(col))
        for r in rows:
            val = str(r.get(col, ""))
            max_width = max(max_width, len(val))
        widths.append(max_width)

    # Check numeric alignment
    numeric_flags = [_is_numeric_column(col, rows) for col in columns]

    # Build table
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    lines = [sep]

    # Header
    header_cells = []
    for col, w in zip(columns, widths):
        header_cells.append(f" {str(col).ljust(w)} ")
    lines.append("|" + "|".join(header_cells) + "|")
    lines.append(sep)

    # Rows
    for r in rows:
        row_cells = []
        for col, w, numeric in zip(columns, widths, numeric_flags):
            val = str(r.get(col, ""))
            if numeric and val:
                # Right-align numbers
                cell = f" {val.rjust(w)} "
            else:
                cell = f" {val.ljust(w)} "
            row_cells.append(cell)
        lines.append("|" + "|".join(row_cells) + "|")
    lines.append(sep)

    # Row count
    if len(rows) == 1:
        lines.append(f"({len(rows)} row)")
    else:
        lines.append(f"({len(rows)} rows)")

    return "\n".join(lines)


def format_message(msg):
    """Format a simple message string."""
    return msg
