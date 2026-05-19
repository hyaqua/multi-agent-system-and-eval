"""Lexer: tokenizes source code into tokens with line numbers."""

from enum import Enum, auto
from typing import List, Tuple, Optional


class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    # Operators
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    EQ = auto()         # ==
    NEQ = auto()        # !=
    LT = auto()         # <
    GT = auto()         # >
    LTE = auto()        # <=
    GTE = auto()        # >=
    ASSIGN = auto()     # =
    # Delimiters
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    COMMA = auto()      # ,
    # Keywords
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    DEF = auto()
    PRINT = auto()
    RETURN = auto()
    # Misc
    EOF = auto()


KEYWORDS = {
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "def": TokenType.DEF,
    "print": TokenType.PRINT,
    "return": TokenType.RETURN,
}


class Token:
    def __init__(self, type_: TokenType, value, line: int, col: int):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.col})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.message = message
        self.line = line
        self.col = col
        super().__init__(f"Lexer error at line {line}, col {col}: {message}")


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def _current(self) -> Optional[str]:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def _advance(self) -> Optional[str]:
        ch = self._current()
        if ch is not None:
            self.pos += 1
            self.col += 1
        return ch

    def _peek(self, offset: int = 1) -> Optional[str]:
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return None

    def _skip_whitespace(self):
        while True:
            ch = self._current()
            if ch is None:
                break
            if ch in ' \t\r':
                self._advance()
            elif ch == '\n':
                self._advance()
                self.line += 1
                self.col = 1
            else:
                break

    def _read_number(self, start_col: int) -> Token:
        line = self.line
        num_str = ""
        is_float = False
        while True:
            ch = self._current()
            if ch is None:
                break
            if ch.isdigit():
                num_str += ch
                self._advance()
            elif ch == '.':
                if is_float:
                    raise LexerError("Invalid number: multiple decimal points", line, self.col)
                # Check if next char is digit (offset 1 since '.' is current)
                nxt = self._peek(1)
                if nxt is not None and nxt.isdigit():
                    is_float = True
                    num_str += ch
                    self._advance()
                else:
                    # Trailing dot, treat as integer and let parser handle it
                    break
            else:
                break

        if is_float:
            value = float(num_str)
        else:
            value = int(num_str)
        return Token(TokenType.NUMBER, value, line, start_col)

    def _read_string(self, start_col: int) -> Token:
        line = self.line
        self._advance()  # skip opening quote
        s = ""
        while True:
            ch = self._current()
            if ch is None:
                raise LexerError("Unterminated string literal", line, start_col)
            if ch == '"':
                self._advance()  # skip closing quote
                break
            elif ch == '\\':
                self._advance()
                escape = self._current()
                if escape is None:
                    raise LexerError("Unterminated escape sequence", line, self.col)
                if escape == 'n':
                    s += '\n'
                elif escape == 't':
                    s += '\t'
                elif escape == '\\':
                    s += '\\'
                elif escape == '"':
                    s += '"'
                elif escape == 'r':
                    s += '\r'
                else:
                    raise LexerError(f"Unknown escape sequence: \\{escape}", line, self.col)
                self._advance()
            elif ch == '\n':
                raise LexerError("Unterminated string literal (newline in string)", line, start_col)
            else:
                s += ch
                self._advance()
        return Token(TokenType.STRING, s, line, start_col)

    def _read_identifier(self, start_col: int) -> Token:
        line = self.line
        ident = ""
        while True:
            ch = self._current()
            if ch is None:
                break
            if ch.isalnum() or ch == '_':
                ident += ch
                self._advance()
            else:
                break

        kw_type = KEYWORDS.get(ident)
        if kw_type is not None:
            return Token(kw_type, ident, line, start_col)
        return Token(TokenType.IDENTIFIER, ident, line, start_col)

    def _read_line_comment(self):
        while True:
            ch = self._current()
            if ch is None or ch == '\n':
                break
            self._advance()

    def tokenize(self) -> List[Token]:
        self.tokens = []
        while True:
            self._skip_whitespace()
            ch = self._current()
            if ch is None:
                break

            start_col = self.col

            # Single-line comments
            if ch == '/' and self._peek(1) == '/':
                self._read_line_comment()
                continue

            # Numbers
            if ch.isdigit():
                self.tokens.append(self._read_number(start_col))
                continue

            # Strings
            if ch == '"':
                self.tokens.append(self._read_string(start_col))
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                self.tokens.append(self._read_identifier(start_col))
                continue

            # Operators and delimiters
            if ch == '+':
                self.tokens.append(Token(TokenType.PLUS, '+', self.line, start_col))
                self._advance()
            elif ch == '-':
                self.tokens.append(Token(TokenType.MINUS, '-', self.line, start_col))
                self._advance()
            elif ch == '*':
                self.tokens.append(Token(TokenType.STAR, '*', self.line, start_col))
                self._advance()
            elif ch == '/':
                self.tokens.append(Token(TokenType.SLASH, '/', self.line, start_col))
                self._advance()
            elif ch == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', self.line, start_col))
                self._advance()
            elif ch == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', self.line, start_col))
                self._advance()
            elif ch == '{':
                self.tokens.append(Token(TokenType.LBRACE, '{', self.line, start_col))
                self._advance()
            elif ch == '}':
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, start_col))
                self._advance()
            elif ch == ',':
                self.tokens.append(Token(TokenType.COMMA, ',', self.line, start_col))
                self._advance()
            elif ch == '=':
                if self._peek(1) == '=':
                    self._advance()
                    self.tokens.append(Token(TokenType.EQ, '==', self.line, start_col))
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, '=', self.line, start_col))
                    self._advance()
            elif ch == '!':
                if self._peek(1) == '=':
                    self._advance()
                    self.tokens.append(Token(TokenType.NEQ, '!=', self.line, start_col))
                    self._advance()
                else:
                    raise LexerError(f"Unexpected character: '!' (expected '!=')", self.line, self.col)
            elif ch == '<':
                if self._peek(1) == '=':
                    self._advance()
                    self.tokens.append(Token(TokenType.LTE, '<=', self.line, start_col))
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.LT, '<', self.line, start_col))
                    self._advance()
            elif ch == '>':
                if self._peek(1) == '=':
                    self._advance()
                    self.tokens.append(Token(TokenType.GTE, '>=', self.line, start_col))
                    self._advance()
                else:
                    self.tokens.append(Token(TokenType.GT, '>', self.line, start_col))
                    self._advance()
            else:
                raise LexerError(f"Unexpected character: '{ch}'", self.line, self.col)

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return self.tokens
