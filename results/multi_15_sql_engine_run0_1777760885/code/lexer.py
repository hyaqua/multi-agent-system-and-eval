import re
from error import SQLError

# Token types
(
    TK_KEYWORD,
    TK_IDENTIFIER,
    TK_NUMBER,
    TK_STRING,
    TK_OPERATOR,
    TK_PUNCTUATION,
    TK_EOF,
) = range(7)

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
    "LOAD", "SAVE", "INNER", "JOIN", "ON",
    "ORDER", "BY", "ASC", "DESC", "LIMIT",
    "GROUP", "HAVING",
    "AND", "OR", "NOT",
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "AS", "DISTINCT",
}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type, value, line, col):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    @property
    def pos(self):
        return (self.line, self.col)

    def __repr__(self):
        type_names = {
            TK_KEYWORD: "KEYWORD",
            TK_IDENTIFIER: "IDENT",
            TK_NUMBER: "NUMBER",
            TK_STRING: "STRING",
            TK_OPERATOR: "OP",
            TK_PUNCTUATION: "PUNCT",
            TK_EOF: "EOF",
        }
        return f"Token({type_names.get(self.type, '?')}, {self.value!r}, line={self.line}, col={self.col})"


# Token patterns (ordered; first match wins)
_TOKEN_SPEC = [
    ("NUMBER",   r"\d+\.?\d*"),          # integer or float
    ("STRING",   r"'[^']*'"),            # single-quoted string
    ("OP",       r"<>|<=|>=|!=|="),       # multi-char ops first
    ("OP",       r"[<>]"),               # single-char comparison ops
    ("PUNCT",    r"[,;()\.]"),           # punctuation
    ("STAR",     r"\*"),                 # star (special)
    ("IDENT",    r"[a-zA-Z_][a-zA-Z0-9_]*"),  # identifier
]

# Compile patterns
_TOKEN_RE = [(name, re.compile(pattern)) for name, pattern in _TOKEN_SPEC]
_WHITESPACE_RE = re.compile(r"[ \t\r]+")
_NEWLINE_RE = re.compile(r"\n")


def tokenize(text):
    """Convert input text into a list of Tokens. Raises SQLError on unknown chars."""
    tokens = []
    i = 0
    line = 1
    col = 1

    def make_token(ttype, value, l, c):
        return Token(ttype, value, l, c)

    while i < len(text):
        ch = text[i]

        # Whitespace (not newline)
        m = _WHITESPACE_RE.match(text, i)
        if m:
            i = m.end()
            col += m.end() - m.start()
            continue

        # Newline
        m = _NEWLINE_RE.match(text, i)
        if m:
            i = m.end()
            line += 1
            col = 1
            continue

        # Comment: -- to end of line
        if ch == "-" and i + 1 < len(text) and text[i + 1] == "-":
            # Skip to end of line
            i += 2
            col += 2
            while i < len(text) and text[i] != "\n":
                i += 1
                col += 1
            continue

        # Try token patterns
        matched = False
        for name, pattern in _TOKEN_RE:
            m = pattern.match(text, i)
            if m:
                raw = m.group()
                start_col = col

                if name == "NUMBER":
                    tokens.append(make_token(TK_NUMBER, raw, line, start_col))
                elif name == "STRING":
                    # Strip quotes
                    tokens.append(make_token(TK_STRING, raw[1:-1], line, start_col))
                elif name == "OP":
                    tokens.append(make_token(TK_OPERATOR, raw, line, start_col))
                elif name == "PUNCT":
                    tokens.append(make_token(TK_PUNCTUATION, raw, line, start_col))
                elif name == "STAR":
                    tokens.append(make_token(TK_OPERATOR, "*", line, start_col))
                elif name == "IDENT":
                    upper = raw.upper()
                    if upper in KEYWORDS:
                        tokens.append(make_token(TK_KEYWORD, upper, line, start_col))
                    else:
                        tokens.append(make_token(TK_IDENTIFIER, raw, line, start_col))

                i = m.end()
                col += len(raw)
                matched = True
                break

        if not matched:
            raise SQLError(f"Unexpected character '{ch}'", pos=(line, col))
            # i += 1; col += 1  # Unreachable due to raise

    tokens.append(make_token(TK_EOF, "", line, col))
    return tokens
