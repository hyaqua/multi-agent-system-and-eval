"""Lexer (tokenizer) for SQL queries."""

import re


class Token:
    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, line={self.line}, col={self.col})"


# Token kinds
EOF = 'EOF'
KEYWORD = 'KEYWORD'
IDENTIFIER = 'IDENTIFIER'
NUMBER = 'NUMBER'
STRING = 'STRING'
STAR = 'STAR'
COMMA = 'COMMA'
SEMICOLON = 'SEMICOLON'
LPAREN = 'LPAREN'
RPAREN = 'RPAREN'
EQUALS = 'EQUALS'
NOT_EQUALS = 'NOT_EQUALS'
LESS = 'LESS'
GREATER = 'GREATER'
LESS_EQ = 'LESS_EQ'
GREATER_EQ = 'GREATER_EQ'
DOT = 'DOT'

KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'INSERT', 'INTO', 'VALUES',
    'LOAD', 'SAVE', 'TO', 'ORDER', 'BY', 'ASC', 'DESC', 'LIMIT',
    'GROUP', 'JOIN', 'INNER', 'ON', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
    'NOT', 'IN', 'LIKE', 'IS', 'NULL', 'TRUE', 'FALSE',
}

# Token patterns ordered for matching
TOKEN_PATTERNS = [
    ('STAR', r'\*'),
    ('NUMBER', r'\d+\.?\d*|\.\d+'),
    ('STRING', r"'[^']*'"),
    ('COMMA', r','),
    ('SEMICOLON', r';'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('NOT_EQUALS', r'!='),
    ('EQUALS', r'='),
    ('LESS_EQ', r'<='),
    ('GREATER_EQ', r'>='),
    ('LESS', r'<'),
    ('GREATER', r'>'),
    ('DOT', r'\.'),
    ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
]


def tokenize(text):
    """Convert raw SQL text into a list of Token objects."""
    tokens = []
    line = 1
    col = 1
    pos = 0

    while pos < len(text):
        # Skip whitespace
        if text[pos] in ' \t\r\n':
            if text[pos] == '\n':
                line += 1
                col = 1
            else:
                col += 1
            pos += 1
            continue

        # Try to match token patterns
        matched = False
        for kind, pattern in TOKEN_PATTERNS:
            m = re.match(pattern, text[pos:])
            if m:
                value = m.group(0)
                if kind == 'IDENTIFIER' and value.upper() in KEYWORDS:
                    kind = 'KEYWORD'
                    value = value.upper()

                tokens.append(Token(kind, value, line, col))
                col += len(value)
                pos += len(value)
                matched = True
                break

        if not matched:
            # Unknown character
            raise LexerError(f"Unexpected character '{text[pos]}' at line {line}, column {col}",
                             line, col)

    tokens.append(Token(EOF, '', line, col))
    return tokens


class LexerError(Exception):
    def __init__(self, message, line=None, col=None):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(message)
