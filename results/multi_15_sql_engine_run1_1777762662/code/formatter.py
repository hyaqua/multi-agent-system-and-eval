"""ASCII table formatter for query results."""


def format_table(columns, rows):
    """Format columns and rows as an ASCII table string."""
    if not columns:
        return "(empty result set)\n"

    # Compute column widths
    widths = []
    for col in columns:
        max_w = len(str(col))
        for row in rows:
            val = row.get(col, '')
            max_w = max(max_w, len(str(val)))
        widths.append(max_w)

    def make_separator(char='-'):
        parts = ['+']
        for w in widths:
            parts.append(char * (w + 2))
            parts.append('+')
        return ''.join(parts)

    lines = []

    # Top border
    lines.append(make_separator('-'))

    # Header
    header_parts = ['|']
    for i, col in enumerate(columns):
        header_parts.append(f' {str(col):<{widths[i]}} ')
        header_parts.append('|')
    lines.append(''.join(header_parts))

    # Separator
    lines.append(make_separator('-'))

    # Rows
    for row in rows:
        row_parts = ['|']
        for i, col in enumerate(columns):
            val = row.get(col, '')
            row_parts.append(f' {str(val):<{widths[i]}} ')
            row_parts.append('|')
        lines.append(''.join(row_parts))

    # Bottom border
    lines.append(make_separator('-'))

    return '\n'.join(lines) + '\n'
