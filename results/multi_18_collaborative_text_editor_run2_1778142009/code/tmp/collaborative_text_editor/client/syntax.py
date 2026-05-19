"""
Python syntax highlighting rules for curses.
"""

import re

# Token types
TOKEN_KEYWORD = 1
TOKEN_STRING = 2
TOKEN_COMMENT = 3
TOKEN_NUMBER = 4
TOKEN_NORMAL = 0

# Python keywords
KEYWORDS = {
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
    "try", "while", "with", "yield",
}

# Token specification
TOKEN_SPEC = [
    ("COMMENT", r"#.*"),
    ("STRING_SINGLE", r"'(?:[^'\\]|\\.)*'"),
    ("STRING_DOUBLE", r'"(?:[^"\\]|\\.)*"'),
    ("NUMBER", r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"),
    ("KEYWORD", r"\b(?:" + "|".join(KEYWORDS) + r")\b"),
    ("IDENTIFIER", r"[a-zA-Z_]\w*"),
    ("OPERATOR", r"[+\-*/%=<>!&|^~@]+"),
    ("PUNCTUATION", r"[(){}\[\],.:;]"),
    ("WHITESPACE", r"\s+"),
    ("MISMATCH", r"."),
]

# Compile token regex
_token_re = "|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC)
_token_re = re.compile(_token_re)


def tokenize_line(line):
    """
    Tokenize a single line of Python code.
    Returns a list of (text, token_type) tuples.
    """
    tokens = []
    for match in _token_re.finditer(line):
        kind = match.lastgroup
        text = match.group()
        if kind == "COMMENT":
            tokens.append((text, TOKEN_COMMENT))
        elif kind in ("STRING_SINGLE", "STRING_DOUBLE"):
            tokens.append((text, TOKEN_STRING))
        elif kind == "NUMBER":
            tokens.append((text, TOKEN_NUMBER))
        elif kind == "KEYWORD":
            tokens.append((text, TOKEN_KEYWORD))
        else:
            tokens.append((text, TOKEN_NORMAL))
    return tokens


def highlight_line(line):
    """
    Highlight a line of Python code.
    Returns a list of (text, color_pair_number) tuples.
    If not a Python file, returns [(line, 0)].
    """
    return tokenize_line(line)


def is_python_file(filename):
    """Check if filename indicates a Python file."""
    if not filename:
        return False
    return filename.endswith(".py")
