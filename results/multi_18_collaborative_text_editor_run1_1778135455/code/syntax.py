"""
Python syntax highlighting using the tokenize module.

Returns colour-annotated spans for curses rendering.
"""

import tokenize
import io
import keyword

# Curses colour pair indices (will be initialised by the UI)
# These are just constants for reference; actual pairs are set in client_ui.py
COLOR_DEFAULT = 0
COLOR_KEYWORD = 1
COLOR_STRING = 2
COLOR_COMMENT = 3
COLOR_NUMBER = 4
COLOR_DECORATOR = 5
COLOR_BUILTIN = 6
COLOR_OP = 7

PYTHON_KEYWORDS = set(keyword.kwlist)
PYTHON_BUILTINS = {
    "True", "False", "None", "self", "cls",
    "int", "str", "float", "bool", "list", "dict", "tuple", "set",
    "print", "len", "range", "type", "isinstance", "hasattr", "getattr",
    "super", "object", "Exception", "ValueError", "TypeError",
    "open", "zip", "map", "filter", "iter", "next", "enumerate",
    "abs", "all", "any", "chr", "ord", "dir", "id", "hex", "oct",
    "min", "max", "sum", "round", "sorted", "reversed",
    "import", "from", "as", "class", "def", "return", "if", "else",
    "elif", "for", "while", "try", "except", "finally", "with",
    "raise", "yield", "lambda", "pass", "break", "continue",
    "and", "or", "not", "in", "is", "del", "global", "nonlocal",
    "assert", "async", "await",
}


def highlight_line(line: str) -> list[tuple[str, int]]:
    """Tokenize a single line and return list of (text_segment, color_pair).

    For multi-line constructs, only the first line is highlighted.
    Returns segments that collectively represent the line.
    """
    if not line.strip():
        return [(line, COLOR_DEFAULT)]

    # We need to handle incomplete lines. tokenize requires complete
    # statements. We'll try to tokenize and fall back gracefully.
    segments = []
    try:
        # Wrap in a complete statement context
        source = line + "\n"
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)

        prev_end = 0
        for tok in tokens:
            tok_type, tok_string, start, end, _ = tok

            # Handle any gap between tokens
            if start[1] > prev_end:
                gap = line[prev_end:start[1]]
                if gap:
                    segments.append((gap, COLOR_DEFAULT))
            prev_end = end[1]

            # Determine colour
            color = _token_color(tok_type, tok_string)

            # Get the token text from the original line
            token_text = line[start[1]:end[1]]
            if token_text:
                segments.append((token_text, color))

        # Any remaining text
        if prev_end < len(line):
            segments.append((line[prev_end:], COLOR_DEFAULT))

    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Fallback: just show as default
        segments = [(line, COLOR_DEFAULT)]

    return segments


def _token_color(tok_type: int, tok_string: str) -> int:
    """Map a token type and string to a colour pair index."""
    if tok_type == tokenize.COMMENT:
        return COLOR_COMMENT
    elif tok_type == tokenize.STRING:
        return COLOR_STRING
    elif tok_type == tokenize.NUMBER:
        return COLOR_NUMBER
    elif tok_type == tokenize.NAME:
        if tok_string in PYTHON_KEYWORDS:
            return COLOR_KEYWORD
        elif tok_string in PYTHON_BUILTINS:
            return COLOR_BUILTIN
        else:
            return COLOR_DEFAULT
    elif tok_type == tokenize.OP:
        if tok_string.startswith("@"):
            return COLOR_DECORATOR
        return COLOR_DEFAULT
    elif tok_type == tokenize.ERRORTOKEN:
        return COLOR_DEFAULT
    else:
        return COLOR_DEFAULT
