"""Lexer/Tokenizer for SQL queries."""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


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
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    JOIN = auto()
    INNER = auto()
    ON = auto()
    LOAD = auto()
    SAVE = auto()
    AS = auto()
    # Aggregate functions
    COUNT = auto()
    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()
    # Symbols
    STAR = auto()       # *
    COMMA = auto()      # ,
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    SEMICOLON = auto()  # ;
    DOT = auto()        # .
    # Operators
    EQ = auto()         # =
    NE = auto()         # !=
    LT = auto()         # <
    GT = auto()         # >
    LE = auto()         # <=
    GE = auto()         # >=
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    # Special
    EOF = auto()


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
    'INSERT': TokenType.INSERT,
    'INTO': TokenType.INTO,
    'VALUES': TokenType.VALUES,
    'JOIN': TokenType.JOIN,
    'INNER': TokenType.INNER,
    'ON': TokenType.ON,
    'LOAD': TokenType.LOAD,
    'SAVE': TokenType.SAVE,
    'AS': TokenType.AS,
    'COUNT': TokenType.COUNT,
    'SUM': TokenType.SUM,
    'AVG': TokenType.AVG,
    'MIN': TokenType.MIN,
    'MAX': TokenType.MAX,
}

AGGREGATE_FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'}


@dataclass
class Token:
    """A lexical token with type, value, and position."""
    type: TokenType
    value: str
    line: int = 1
    col: int = 1

    def __repr__(self):
        return f"Token({self.type.name}, '{self.value}', pos={self.line}:{self.col})"


class LexerError(Exception):
    """Error raised during lexing."""
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Lexer error at line {line}, col {col}: {message}")


class Lexer:
    """SQL lexer that tokenizes input strings."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        """Tokenize the entire input and return a list of tokens."""
        self.tokens = []
        while self.pos < len(self.text):
            c = self.text[self.pos]

            # Whitespace
            if c in ' \t\r':
                self._advance()
                continue

            # Newline
            if c == '\n':
                self.line += 1
                self.col = 1
                self.pos += 1
                continue

            # Single-line comment
            if c == '-' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '-':
                while self.pos < len(self.text) and self.text[self.pos] != '\n':
                    self.pos += 1
                continue

            # Numbers
            if c.isdigit():
                self.tokens.append(self._read_number())
                continue

            # Identifiers and keywords
            if c.isalpha() or c == '_':
                self.tokens.append(self._read_identifier())
                continue

            # Strings (single-quoted)
            if c == "'":
                self.tokens.append(self._read_string())
                continue

            # Symbols and operators
            if c == '*':
                self.tokens.append(Token(TokenType.STAR, '*', self.line, self.col))
                self._advance()
                continue

            if c == ',':
                self.tokens.append(Token(TokenType.COMMA, ',', self.line, self.col))
                self._advance()
                continue

            if c == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', self.line, self.col))
                self._advance()
                continue

            if c == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', self.line, self.col))
                self._advance()
                continue

            if c == ';':
                self.tokens.append(Token(TokenType.SEMICOLON, ';', self.line, self.col))
                self._advance()
                continue

            if c == '.':
                self.tokens.append(Token(TokenType.DOT, '.', self.line, self.col))
                self._advance()
                continue

            if c == '=':
                self.tokens.append(Token(TokenType.EQ, '=', self.line, self.col))
                self._advance()
                continue

            if c == '!':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.NE, '!=', self.line, self.col))
                    self.pos += 2
                    self.col += 2
                    continue
                else:
                    raise LexerError(f"Unexpected character '!' (did you mean '!='?)", self.line, self.col)

            if c == '<':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.LE, '<=', self.line, self.col))
                    self.pos += 2
                    self.col += 2
                    continue
                else:
                    self.tokens.append(Token(TokenType.LT, '<', self.line, self.col))
                    self._advance()
                    continue

            if c == '>':
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.GE, '>=', self.line, self.col))
                    self.pos += 2
                    self.col += 2
                    continue
                else:
                    self.tokens.append(Token(TokenType.GT, '>', self.line, self.col))
                    self._advance()
                    continue

            raise LexerError(f"Unexpected character '{c}'", self.line, self.col)

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens

    def _advance(self):
        """Move forward one character."""
        self.pos += 1
        self.col += 1

    def _read_number(self) -> Token:
        """Read a numeric literal."""
        start_line, start_col = self.line, self.col
        num_str = ''
        has_dot = False

        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c.isdigit():
                num_str += c
                self._advance()
            elif c == '.' and not has_dot:
                has_dot = True
                num_str += c
                self._advance()
            else:
                break

        value = float(num_str) if has_dot else int(num_str)
        return Token(TokenType.NUMBER, num_str, start_line, start_col)

    def _read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        start_line, start_col = self.line, self.col
        ident = ''

        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c.isalnum() or c == '_':
                ident += c
                self._advance()
            else:
                break

        upper = ident.upper()
        if upper in KEYWORDS:
            return Token(KEYWORDS[upper], ident, start_line, start_col)
        return Token(TokenType.IDENTIFIER, ident, start_line, start_col)

    def _read_string(self) -> Token:
        """Read a single-quoted string literal."""
        start_line, start_col = self.line, self.col
        # Skip opening quote
        self._advance()
        value = ''

        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c == "'":
                # Check for escaped quote ''
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == "'":
                    value += "'"
                    self.pos += 2
                    self.col += 2
                else:
                    self._advance()  # skip closing quote
                    return Token(TokenType.STRING, value, start_line, start_col)
            else:
                if c == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                value += c
                self.pos += 1

        raise LexerError("Unterminated string literal", start_line, start_col)
