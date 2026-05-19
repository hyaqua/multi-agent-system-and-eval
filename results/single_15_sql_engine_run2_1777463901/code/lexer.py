"""SQL Lexer - Tokenizes SQL input strings."""

from enum import Enum, auto
import re


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
    GROUP = auto()
    INNER = auto()
    JOIN = auto()
    ON = auto()
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    LOAD = auto()
    SAVE = auto()
    TO = auto()
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()

    # Symbols
    STAR = auto()
    COMMA = auto()
    SEMICOLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    DOT = auto()

    # Values
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    EOF = auto()


class Token:
    def __init__(self, type_: TokenType, value: str, pos: int):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, '{self.value}', {self.pos})"


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
    'GROUP': TokenType.GROUP,
    'INNER': TokenType.INNER,
    'JOIN': TokenType.JOIN,
    'ON': TokenType.ON,
    'INSERT': TokenType.INSERT,
    'INTO': TokenType.INTO,
    'VALUES': TokenType.VALUES,
    'LOAD': TokenType.LOAD,
    'SAVE': TokenType.SAVE,
    'TO': TokenType.TO,
    'COUNT': TokenType.COUNT,
    'SUM': TokenType.SUM,
    'AVG': TokenType.AVG,
    'MIN': TokenType.MIN,
    'MAX': TokenType.MAX,
}

SYMBOLS = {
    '*': TokenType.STAR,
    ',': TokenType.COMMA,
    ';': TokenType.SEMICOLON,
    '(': TokenType.LPAREN,
    ')': TokenType.RPAREN,
    '=': TokenType.EQ,
    '.': TokenType.DOT,
}


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def _current_char(self):
        if self.pos < len(self.text):
            return self.text[self.pos]
        return None

    def _peek(self):
        if self.pos + 1 < len(self.text):
            return self.text[self.pos + 1]
        return None

    def _advance(self):
        self.pos += 1

    def _skip_whitespace(self):
        while self._current_char() and self._current_char().isspace():
            self._advance()

    def _read_identifier_or_keyword(self) -> Token:
        start = self.pos
        while self._current_char() and (self._current_char().isalnum() or self._current_char() == '_'):
            self._advance()
        value = self.text[start:self.pos]
        upper = value.upper()
        if upper in KEYWORDS:
            return Token(KEYWORDS[upper], upper, start)
        return Token(TokenType.IDENTIFIER, value, start)

    def _read_number(self) -> Token:
        start = self.pos
        if self._current_char() == '-':
            self._advance()
        while self._current_char() and self._current_char().isdigit():
            self._advance()
        if self._current_char() == '.':
            self._advance()
            while self._current_char() and self._current_char().isdigit():
                self._advance()
        value = self.text[start:self.pos]
        return Token(TokenType.NUMBER, value, start)

    def _read_string(self) -> Token:
        quote = self._current_char()
        self._advance()
        start = self.pos
        while self._current_char() and self._current_char() != quote:
            self._advance()
        value = self.text[start:self.pos]
        if self._current_char() == quote:
            self._advance()
        return Token(TokenType.STRING, value, start - 1)

    def next_token(self) -> Token:
        self._skip_whitespace()
        c = self._current_char()
        if c is None:
            return Token(TokenType.EOF, '', self.pos)

        pos = self.pos

        # Two-char operators
        if c == '!' and self._peek() == '=':
            self._advance()
            self._advance()
            return Token(TokenType.NEQ, '!=', pos)
        if c == '<' and self._peek() == '=':
            self._advance()
            self._advance()
            return Token(TokenType.LE, '<=', pos)
        if c == '>' and self._peek() == '=':
            self._advance()
            self._advance()
            return Token(TokenType.GE, '>=', pos)
        if c == '<' and self._peek() == '>':
            self._advance()
            self._advance()
            return Token(TokenType.NEQ, '<>', pos)

        # Single-char symbols
        if c in SYMBOLS:
            self._advance()
            return Token(SYMBOLS[c], c, pos)

        # Single-char operators
        if c == '<':
            self._advance()
            return Token(TokenType.LT, '<', pos)
        if c == '>':
            self._advance()
            return Token(TokenType.GT, '>', pos)

        # Strings
        if c in ("'", '"'):
            return self._read_string()

        # Numbers
        if c.isdigit() or (c == '-' and self._peek() and self._peek().isdigit()):
            return self._read_number()

        # Identifiers / keywords
        if c.isalpha() or c == '_':
            return self._read_identifier_or_keyword()

        # Unknown
        self._advance()
        return Token(TokenType.IDENTIFIER, c, pos)

    def tokenize(self) -> list[Token]:
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens
