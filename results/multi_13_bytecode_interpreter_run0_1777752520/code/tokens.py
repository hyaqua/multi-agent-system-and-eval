"""Token class and token type constants for the bytecode interpreter."""

# Token types
NUMBER = "NUMBER"
STRING = "STRING"
ID = "ID"
KEYWORD = "KEYWORD"
OP = "OP"
DELIM = "DELIM"
EOF = "EOF"


class Token:
    """Represents a single token from the lexer."""

    def __init__(self, type_, value, line, column):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line}, col={self.column})"
