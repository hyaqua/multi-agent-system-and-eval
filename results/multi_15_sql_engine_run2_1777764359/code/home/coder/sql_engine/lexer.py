"""Lexer/Tokenizer for SQL queries.

Converts an input string into a list of tokens with line/column tracking.
"""

import re
from error import ParseError

# Token types
(
    TOK_EOF,
    TOK_IDENTIFIER,
    TOK_STRING,
    TOK_NUMBER,
    TOK_COMMA,
    TOK_SEMICOLON,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_EQ,
    TOK_NEQ,
    TOK_LT,
    TOK_GT,
    TOK_LE,
    TOK_GE,
    TOK_DOT,
    TOK_STAR,
    TOK_SLASH,
    TOK_PLUS,
    TOK_MINUS,
    # Keywords
    TOK_SELECT,
    TOK_FROM,
    TOK_WHERE,
    TOK_AND,
    TOK_OR,
    TOK_ORDER,
    TOK_BY,
    TOK_ASC,
    TOK_DESC,
    TOK_LIMIT,
    TOK_GROUP,
    TOK_INSERT,
    TOK_INTO,
    TOK_VALUES,
    TOK_INNER,
    TOK_JOIN,
    TOK_ON,
    TOK_LOAD,
    TOK_TO,
    TOK_SAVE,
    TOK_COUNT,
    TOK_SUM,
    TOK_AVG,
    TOK_MIN,
    TOK_MAX,
    TOK_AS,
) = range(40)

# Map token type to name for error messages
TOKEN_NAMES = {
    TOK_EOF: 'EOF',
    TOK_IDENTIFIER: 'identifier',
    TOK_STRING: 'string',
    TOK_NUMBER: 'number',
    TOK_COMMA: ',',
    TOK_SEMICOLON: ';',
    TOK_LPAREN: '(',
    TOK_RPAREN: ')',
    TOK_EQ: '=',
    TOK_NEQ: '!=',
    TOK_LT: '<',
    TOK_GT: '>',
    TOK_LE: '<=',
    TOK_GE: '>=',
    TOK_DOT: '.',
    TOK_STAR: '*',
    TOK_SLASH: '/',
    TOK_PLUS: '+',
    TOK_MINUS: '-',
    TOK_SELECT: 'SELECT',
    TOK_FROM: 'FROM',
    TOK_WHERE: 'WHERE',
    TOK_AND: 'AND',
    TOK_OR: 'OR',
    TOK_ORDER: 'ORDER',
    TOK_BY: 'BY',
    TOK_ASC: 'ASC',
    TOK_DESC: 'DESC',
    TOK_LIMIT: 'LIMIT',
    TOK_GROUP: 'GROUP',
    TOK_INSERT: 'INSERT',
    TOK_INTO: 'INTO',
    TOK_VALUES: 'VALUES',
    TOK_INNER: 'INNER',
    TOK_JOIN: 'JOIN',
    TOK_ON: 'ON',
    TOK_LOAD: 'LOAD',
    TOK_TO: 'TO',
    TOK_SAVE: 'SAVE',
    TOK_COUNT: 'COUNT',
    TOK_SUM: 'SUM',
    TOK_AVG: 'AVG',
    TOK_MIN: 'MIN',
    TOK_MAX: 'MAX',
    TOK_AS: 'AS',
}

# Map keyword strings to token types (uppercase)
KEYWORDS = {
    'SELECT': TOK_SELECT,
    'FROM': TOK_FROM,
    'WHERE': TOK_WHERE,
    'AND': TOK_AND,
    'OR': TOK_OR,
    'ORDER': TOK_ORDER,
    'BY': TOK_BY,
    'ASC': TOK_ASC,
    'DESC': TOK_DESC,
    'LIMIT': TOK_LIMIT,
    'GROUP': TOK_GROUP,
    'INSERT': TOK_INSERT,
    'INTO': TOK_INTO,
    'VALUES': TOK_VALUES,
    'INNER': TOK_INNER,
    'JOIN': TOK_JOIN,
    'ON': TOK_ON,
    'LOAD': TOK_LOAD,
    'TO': TOK_TO,
    'SAVE': TOK_SAVE,
    'COUNT': TOK_COUNT,
    'SUM': TOK_SUM,
    'AVG': TOK_AVG,
    'MIN': TOK_MIN,
    'MAX': TOK_MAX,
    'AS': TOK_AS,
}


class Token:
    """Represents a single token with type, value, and source position."""

    def __init__(self, tok_type: int, value: str, line: int, column: int):
        self.type = tok_type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        name = TOKEN_NAMES.get(self.type, '?')
        return f"Token({name}, {self.value!r}, line={self.line}, col={self.column})"


# Regex patterns for tokenization
_PATTERNS = [
    (r'!=', TOK_NEQ),
    (r'<=', TOK_LE),
    (r'>=', TOK_GE),
    (r'=', TOK_EQ),
    (r'<', TOK_LT),
    (r'>', TOK_GT),
    (r',', TOK_COMMA),
    (r';', TOK_SEMICOLON),
    (r'\(', TOK_LPAREN),
    (r'\)', TOK_RPAREN),
    (r'\.', TOK_DOT),
    (r'\*', TOK_STAR),
    (r'\+', TOK_PLUS),
    (r'/', TOK_SLASH),
    (r'-', TOK_MINUS),
    (r"'[^']*'", TOK_STRING),   # single-quoted string
    (r'"[^"]*"', TOK_STRING),   # double-quoted string (treated same)
    (r'\d+\.?\d*', TOK_NUMBER),
    (r'[a-zA-Z_][a-zA-Z0-9_]*', TOK_IDENTIFIER),
    (r'\s+', None),  # whitespace (skip)
]


def tokenize(source: str) -> list[Token]:
    """Tokenize the input source string into a list of Token objects."""
    tokens = []
    pos = 0
    line = 1
    col = 1

    while pos < len(source):
        remaining = source[pos:]
        matched = False

        for pattern, tok_type in _PATTERNS:
            m = re.match(pattern, remaining)
            if m:
                lexeme = m.group(0)
                if tok_type is not None:
                    # Keyword check for identifiers
                    if tok_type == TOK_IDENTIFIER:
                        upper = lexeme.upper()
                        if upper in KEYWORDS:
                            tok_type = KEYWORDS[upper]
                            tokens.append(Token(tok_type, upper, line, col))
                        else:
                            tokens.append(Token(tok_type, lexeme, line, col))
                    elif tok_type == TOK_STRING:
                        # Strip quotes
                        tokens.append(Token(tok_type, lexeme[1:-1], line, col))
                    elif tok_type == TOK_NUMBER:
                        # Convert to int or float
                        if '.' in lexeme:
                            tokens.append(Token(tok_type, float(lexeme), line, col))
                        else:
                            tokens.append(Token(tok_type, int(lexeme), line, col))
                    else:
                        tokens.append(Token(tok_type, lexeme, line, col))

                # Update line/col
                newlines = lexeme.count('\n')
                if newlines > 0:
                    line += newlines
                    col = len(lexeme) - lexeme.rfind('\n')
                else:
                    col += len(lexeme)

                pos += len(lexeme)
                matched = True
                break

        if not matched:
            raise ParseError(
                f"Unrecognized character '{source[pos]}'",
                line=line, column=col
            )

    tokens.append(Token(TOK_EOF, '', line, col))
    return tokens
