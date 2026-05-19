"""Lexer: converts source code into a stream of tokens."""

from tokens import Token, TokenType, KEYWORDS


class LexError(Exception):
    """Raised when the lexer encounters an unexpected character."""
    def __init__(self, message: str, line: int):
        super().__init__(f"Lex error at line {line}: {message}")
        self.line = line


class Lexer:
    """Tokenizes source code into a list of Token objects."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1

    def _current(self) -> str | None:
        """Return the current character, or None if at end."""
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def _advance(self) -> str | None:
        """Return the current character and move forward one position."""
        ch = self._current()
        if ch is not None:
            self.pos += 1
        return ch

    def _peek_next(self) -> str | None:
        """Look ahead one character without consuming."""
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return None

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return a list of tokens."""
        tokens: list[Token] = []

        while self.pos < len(self.source):
            ch = self._current()

            # Whitespace (not newline)
            if ch in (' ', '\t', '\r'):
                self._advance()
                continue

            # Newline
            if ch == '\n':
                self._advance()
                tokens.append(Token(TokenType.NEWLINE, '\n', self.line))
                self.line += 1
                continue

            # Comments: // until end of line
            if ch == '/' and self._peek_next() == '/':
                self._advance()  # skip first /
                self._advance()  # skip second /
                while self._current() is not None and self._current() != '\n':
                    self._advance()
                continue

            # Strings
            if ch == '"':
                tokens.append(self._read_string())
                continue

            # Numbers
            if ch.isdigit() or (ch == '.' and self._peek_next() is not None
                                and self._peek_next().isdigit()):
                tokens.append(self._read_number())
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                tokens.append(self._read_identifier_or_keyword())
                continue

            # Operators and delimiters
            if ch in '+-*/=!<>(),:':
                tokens.append(self._read_operator_or_delimiter())
                continue

            # Unknown character
            raise LexError(f"Unexpected character: {ch!r}", self.line)

        tokens.append(Token(TokenType.EOF, '', self.line))
        return tokens

    def _read_string(self) -> Token:
        """Read a double-quoted string literal."""
        line = self.line
        self._advance()  # skip opening quote
        result = []
        while self._current() is not None:
            ch = self._current()
            if ch == '"':
                self._advance()  # skip closing quote
                return Token(TokenType.STRING, ''.join(result), line)
            if ch == '\\' and self._peek_next() == '"':
                self._advance()  # skip backslash
                self._advance()  # skip quote
                result.append('"')
                continue
            if ch == '\n':
                raise LexError("Unterminated string literal", line)
            result.append(ch)
            self._advance()
        raise LexError("Unterminated string literal", line)

    def _read_number(self) -> Token:
        """Read an integer or float literal."""
        line = self.line
        result = []
        is_float = False
        while self._current() is not None:
            ch = self._current()
            if ch.isdigit():
                result.append(ch)
                self._advance()
            elif ch == '.' and not is_float:
                # Check if next char is a digit (to distinguish from method calls)
                if (self._peek_next() is not None
                        and self._peek_next().isdigit()):
                    is_float = True
                    result.append(ch)
                    self._advance()
                else:
                    break
            else:
                break

        value_str = ''.join(result)
        if is_float:
            return Token(TokenType.NUMBER, value_str, line)
        return Token(TokenType.NUMBER, value_str, line)

    def _read_identifier_or_keyword(self) -> Token:
        """Read an identifier; classify as KEYWORD if it's a known keyword."""
        line = self.line
        result = []
        while self._current() is not None:
            ch = self._current()
            if ch.isalnum() or ch == '_':
                result.append(ch)
                self._advance()
            else:
                break
        name = ''.join(result)
        if name in KEYWORDS:
            return Token(TokenType.KEYWORD, name, line)
        return Token(TokenType.IDENTIFIER, name, line)

    def _read_operator_or_delimiter(self) -> Token:
        """Read an operator or delimiter token."""
        line = self.line
        ch = self._advance()

        # Multi-character operators
        if ch == '=' and self._current() == '=':
            self._advance()
            return Token(TokenType.OPERATOR, '==', line)
        if ch == '!' and self._current() == '=':
            self._advance()
            return Token(TokenType.OPERATOR, '!=', line)
        if ch == '<' and self._current() == '=':
            self._advance()
            return Token(TokenType.OPERATOR, '<=', line)
        if ch == '>' and self._current() == '=':
            self._advance()
            return Token(TokenType.OPERATOR, '>=', line)

        # Single-character operators and delimiters
        if ch in '+-*/':
            return Token(TokenType.OPERATOR, ch, line)
        if ch == '=':
            return Token(TokenType.OPERATOR, '=', line)
        if ch in '<>':
            return Token(TokenType.OPERATOR, ch, line)
        if ch in '(),:':
            return Token(TokenType.DELIMITER, ch, line)
        if ch == '!':
            # '!' alone is not valid; only '!=' is valid
            raise LexError(f"Unexpected character: '!' (did you mean '!='?)", line)

        raise LexError(f"Unexpected character: {ch!r}", line)
