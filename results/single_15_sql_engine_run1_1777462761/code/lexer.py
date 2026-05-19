"""
SQL Lexer/Tokenizer for the SQL query engine.
Converts SQL text into tokens for the parser.
"""

from enum import Enum, auto
from typing import List


class TokenType(Enum):
    # Keywords
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    AND = auto()
    OR = auto()
    ORDER = auto()
    BY = auto()
    ASC = auto()
    DESC = auto()
    LIMIT = auto()
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    INNER = auto()
    JOIN = auto()
    ON = auto()
    GROUP = auto()
    LOAD = auto()
    SAVE = auto()
    TO = auto()

    # Aggregate functions
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()

    # Symbols
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    STAR = auto()
    DOT = auto()
    SEMICOLON = auto()

    # Operators
    EQ = auto()   # =
    NEQ = auto()  # !=
    LT = auto()   # <
    GT = auto()   # >
    LTE = auto()  # <=
    GTE = auto()  # >=

    # Values
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()

    EOF = auto()


class Token:
    """A single token from the lexer."""

    def __init__(self, type_: TokenType, value, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, pos={self.pos})"


# Mapping of uppercase keyword strings to token types
KEYWORDS = {
    'SELECT': TokenType.SELECT,
    'FROM': TokenType.FROM,
    'WHERE': TokenType.WHERE,
    'AND': TokenType.AND,
    'OR': TokenType.OR,
    'ORDER': TokenType.ORDER,
    'BY': TokenType.BY,
    'ASC': TokenType.ASC,
    'DESC': TokenType.DESC,
    'LIMIT': TokenType.LIMIT,
    'INSERT': TokenType.INSERT,
    'INTO': TokenType.INTO,
    'VALUES': TokenType.VALUES,
    'INNER': TokenType.INNER,
    'JOIN': TokenType.JOIN,
    'ON': TokenType.ON,
    'GROUP': TokenType.GROUP,
    'LOAD': TokenType.LOAD,
    'SAVE': TokenType.SAVE,
    'TO': TokenType.TO,
    'COUNT': TokenType.COUNT,
    'SUM': TokenType.SUM,
    'AVG': TokenType.AVG,
    'MIN': TokenType.MIN,
    'MAX': TokenType.MAX,
}


class LexerError(Exception):
    """Raised when the lexer encounters invalid input."""

    def __init__(self, message: str, pos: int):
        self.pos = pos
        super().__init__(f"{message} at position {pos}")


class Lexer:
    """Tokenizes a SQL string into a list of Token objects."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def tokenize(self) -> List[Token]:
        """Convert the input text into a list of tokens."""
        tokens = []
        while self.pos < len(self.text):
            c = self.text[self.pos]

            if c.isspace():
                self.pos += 1
                continue

            if c == "'":
                tokens.append(self._read_string())
                continue

            if c.isdigit() or (c == '.' and self.pos + 1 < len(self.text)
                               and self.text[self.pos + 1].isdigit()):
                tokens.append(self._read_number())
                continue

            if c.isalpha() or c == '_':
                tokens.append(self._read_identifier_or_keyword())
                continue

            # Operators and symbols
            start_pos = self.pos
            if c == '=':
                tokens.append(Token(TokenType.EQ, '=', start_pos))
                self.pos += 1
            elif c == '!' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                tokens.append(Token(TokenType.NEQ, '!=', start_pos))
                self.pos += 2
            elif c == '<':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                    tokens.append(Token(TokenType.LTE, '<=', start_pos))
                    self.pos += 2
                else:
                    tokens.append(Token(TokenType.LT, '<', start_pos))
                    self.pos += 1
            elif c == '>':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                    tokens.append(Token(TokenType.GTE, '>=', start_pos))
                    self.pos += 2
                else:
                    tokens.append(Token(TokenType.GT, '>', start_pos))
                    self.pos += 1
            elif c == '(':
                tokens.append(Token(TokenType.LPAREN, '(', start_pos))
                self.pos += 1
            elif c == ')':
                tokens.append(Token(TokenType.RPAREN, ')', start_pos))
                self.pos += 1
            elif c == ',':
                tokens.append(Token(TokenType.COMMA, ',', start_pos))
                self.pos += 1
            elif c == '*':
                tokens.append(Token(TokenType.STAR, '*', start_pos))
                self.pos += 1
            elif c == '.':
                tokens.append(Token(TokenType.DOT, '.', start_pos))
                self.pos += 1
            elif c == ';':
                tokens.append(Token(TokenType.SEMICOLON, ';', start_pos))
                self.pos += 1
            else:
                raise LexerError(f"Unexpected character '{c}'", start_pos)

        tokens.append(Token(TokenType.EOF, None, self.pos))
        return tokens

    def _read_string(self) -> Token:
        """Read a single-quoted string literal."""
        start_pos = self.pos
        self.pos += 1  # skip opening quote
        result = []
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c == "'":
                self.pos += 1
                return Token(TokenType.STRING, ''.join(result), start_pos)
            result.append(c)
            self.pos += 1
        raise LexerError("Unterminated string literal", start_pos)

    def _read_number(self) -> Token:
        """Read an integer or float literal."""
        start_pos = self.pos
        result = []
        has_dot = False
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c.isdigit():
                result.append(c)
            elif c == '.' and not has_dot:
                has_dot = True
                result.append(c)
            else:
                break
            self.pos += 1

        num_str = ''.join(result)
        if has_dot:
            return Token(TokenType.NUMBER, float(num_str), start_pos)
        return Token(TokenType.NUMBER, int(num_str), start_pos)

    def _read_identifier_or_keyword(self) -> Token:
        """Read an identifier or keyword."""
        start_pos = self.pos
        result = []
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c.isalnum() or c == '_':
                result.append(c)
                self.pos += 1
            else:
                break

        word = ''.join(result)
        upper = word.upper()
        if upper in KEYWORDS:
            # Return keyword token with uppercase value
            return Token(KEYWORDS[upper], upper, start_pos)
        # Return identifier with original casing
        return Token(TokenType.IDENTIFIER, word, start_pos)
