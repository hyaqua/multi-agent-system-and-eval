"""Lexer: tokenizes source code into tokens with line numbers.

Handles INDENT/DEDENT for block-structured code (like Python).
"""

from dataclasses import dataclass
from typing import List, Union


@dataclass
class Token:
    """A lexical token."""
    type: str
    value: Union[str, int, float, None] = None
    line_no: int = 0

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line_no})"


# Token types
EOF = 'EOF'
NEWLINE = 'NEWLINE'
INDENT = 'INDENT'
DEDENT = 'DEDENT'
NUMBER = 'NUMBER'
STRING = 'STRING'
IDENTIFIER = 'IDENTIFIER'
# Keywords
PRINT = 'PRINT'
IF = 'IF'
ELSE = 'ELSE'
WHILE = 'WHILE'
DEF = 'DEF'
RETURN = 'RETURN'
# Operators and delimiters
PLUS = 'PLUS'
MINUS = 'MINUS'
STAR = 'STAR'
SLASH = 'SLASH'
EQ = 'EQ'           # =
EQ_EQ = 'EQ_EQ'     # ==
NOT_EQ = 'NOT_EQ'   # !=
LT = 'LT'           # <
GT = 'GT'           # >
LE = 'LE'           # <=
GE = 'GE'           # >=
LPAREN = 'LPAREN'   # (
RPAREN = 'RPAREN'   # )
COLON = 'COLON'     # :
COMMA = 'COMMA'     # ,

# Map keyword strings to token types
KEYWORDS = {
    'print': PRINT,
    'if': IF,
    'else': ELSE,
    'while': WHILE,
    'def': DEF,
    'return': RETURN,
}

# Multi-character operators (longest first)
OPERATORS = {
    '==': EQ_EQ,
    '!=': NOT_EQ,
    '<=': LE,
    '>=': GE,
    '<': LT,
    '>': GT,
    '=': EQ,
    '+': PLUS,
    '-': MINUS,
    '*': STAR,
    '/': SLASH,
}


class LexerError(Exception):
    """Raised for lexical errors."""

    def __init__(self, message: str, line_no: int):
        super().__init__(f"Lexer error at line {line_no}: {message}")
        self.line_no = line_no


class Lexer:
    """Converts source text into a list of tokens."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line_no = 1
        self.paren_depth = 0
        # Indentation tracking
        self.indent_stack = [0]  # Stack of indentation levels
        self.at_line_start = True  # True after a newline (or at start)
        self.pending_tokens: List[Token] = []  # Tokens to be emitted before next real token

    def tokenize(self) -> List[Token]:
        """Tokenize the source and return a list of tokens."""
        tokens: List[Token] = []

        # Compute indentation of first line if not empty
        if self.source:
            self.handle_line_start()

        while self.pos < len(self.source):
            # Emit any pending INDENT/DEDENT tokens
            if self.pending_tokens:
                tokens.extend(self.pending_tokens)
                self.pending_tokens = []

            ch = self.current_char()
            if ch is None:
                break

            # Skip spaces and tabs (but track for indentation)
            if self.at_line_start and ch in (' ', '\t'):
                # Will be handled by handle_line_start
                self.compute_line_indent()
                continue

            # Skip whitespace (but not newlines) when not at line start
            if ch in (' ', '\t', '\r'):
                self.advance()
                continue

            # Newline handling
            if ch == '\n':
                self.advance()
                self.line_no += 1
                self.at_line_start = True
                if self.paren_depth == 0:
                    # Emit NEWLINE (but after processing any pending indent/dedent)
                    if self.pending_tokens:
                        tokens.extend(self.pending_tokens)
                        self.pending_tokens = []
                    tokens.append(Token(NEWLINE, '\n', self.line_no - 1))
                    # Compute indentation of next line
                    self.handle_line_start()
                continue

            self.at_line_start = False

            # Comments
            if ch == '#':
                while self.pos < len(self.source) and self.current_char() != '\n':
                    self.advance()
                continue

            # Strings
            if ch == '"':
                tokens.append(self.read_string())
                continue

            # Numbers
            if ch.isdigit():
                tokens.append(self.read_number())
                continue

            # Identifiers and keywords
            if ch.isalpha() or ch == '_':
                tokens.append(self.read_identifier())
                continue

            # Operators and delimiters
            token = self.read_operator()
            if token:
                tokens.append(token)
                # Track paren depth
                if token.type == LPAREN:
                    self.paren_depth += 1
                elif token.type == RPAREN:
                    self.paren_depth -= 1
                    if self.paren_depth < 0:
                        raise LexerError("Unmatched closing parenthesis", self.line_no)
                continue

            raise LexerError(f"Unexpected character: {ch!r}", self.line_no)

        # Check paren balance
        if self.paren_depth != 0:
            raise LexerError("Unclosed parenthesis", self.line_no)

        # Emit any pending tokens
        if self.pending_tokens:
            tokens.extend(self.pending_tokens)
            self.pending_tokens = []

        # Emit dedents at end to close all indentation levels
        while len(self.indent_stack) > 1:
            tokens.append(Token(NEWLINE, '\n', self.line_no))
            tokens.append(Token(DEDENT, None, self.line_no))
            self.indent_stack.pop()

        # Emit final NEWLINE if needed
        if tokens and tokens[-1].type not in (NEWLINE, DEDENT):
            tokens.append(Token(NEWLINE, '\n', self.line_no))

        tokens.append(Token(EOF, None, self.line_no))
        return tokens

    def compute_line_indent(self) -> int:
        """Compute the indentation of the current line (number of leading spaces)."""
        indent = 0
        save_pos = self.pos
        while self.pos < len(self.source) and self.source[self.pos] in (' ', '\t'):
            if self.source[self.pos] == ' ':
                indent += 1
            elif self.source[self.pos] == '\t':
                indent += 4  # Treat tab as 4 spaces
            self.pos += 1
        # If the line is empty or a comment, don't count its indentation
        if self.pos < len(self.source) and self.source[self.pos] in ('\n', '\r', '#'):
            indent = -1  # signal: blank/comment line
        self.pos = save_pos
        return indent

    def handle_line_start(self) -> None:
        """Called at the start of a line to compute INDENT/DEDENT."""
        indent = self.compute_line_indent()
        if indent < 0:
            # Blank or comment line — skip indentation tracking
            return

        current_indent = self.indent_stack[-1]
        if indent > current_indent:
            self.indent_stack.append(indent)
            self.pending_tokens.append(Token(INDENT, None, self.line_no))
        elif indent < current_indent:
            # Pop indentation levels and emit DEDENT tokens
            while len(self.indent_stack) > 1 and indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.pending_tokens.append(Token(DEDENT, None, self.line_no))
            if indent != self.indent_stack[-1]:
                raise LexerError(
                    f"Inconsistent indentation (expected {self.indent_stack[-1]} spaces, got {indent})",
                    self.line_no
                )

    def current_char(self) -> Union[str, None]:
        """Return the current character or None if at end."""
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def advance(self) -> None:
        """Move to the next character."""
        self.pos += 1

    def peek(self) -> Union[str, None]:
        """Return the next character without consuming it."""
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return None

    def read_string(self) -> Token:
        """Read a double-quoted string literal."""
        start_line = self.line_no
        self.advance()  # consume opening quote
        value_chars = []
        while self.pos < len(self.source):
            ch = self.current_char()
            if ch is None:
                raise LexerError("Unterminated string literal", start_line)
            if ch == '\n':
                self.line_no += 1
                value_chars.append(ch)
                self.advance()
                continue
            if ch == '"':
                self.advance()  # consume closing quote
                return Token(STRING, ''.join(value_chars), start_line)
            if ch == '\\':
                self.advance()
                escaped = self.current_char()
                if escaped == 'n':
                    value_chars.append('\n')
                elif escaped == 't':
                    value_chars.append('\t')
                elif escaped == '"':
                    value_chars.append('"')
                elif escaped == '\\':
                    value_chars.append('\\')
                else:
                    value_chars.append(escaped)
                self.advance()
            else:
                value_chars.append(ch)
                self.advance()
        raise LexerError("Unterminated string literal", start_line)

    def read_number(self) -> Token:
        """Read an integer or float literal."""
        start_line = self.line_no
        chars = []
        is_float = False
        while self.pos < len(self.source):
            ch = self.current_char()
            if ch.isdigit():
                chars.append(ch)
                self.advance()
            elif ch == '.' and not is_float:
                # Check if next char is a digit
                nxt = self.peek()
                if nxt is not None and nxt.isdigit():
                    is_float = True
                    chars.append(ch)
                    self.advance()
                else:
                    break
            else:
                break

        raw = ''.join(chars)
        if is_float:
            return Token(NUMBER, float(raw), start_line)
        return Token(NUMBER, int(raw), start_line)

    def read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        start_line = self.line_no
        chars = []
        while self.pos < len(self.source):
            ch = self.current_char()
            if ch.isalnum() or ch == '_':
                chars.append(ch)
                self.advance()
            else:
                break
        name = ''.join(chars)
        if name in KEYWORDS:
            return Token(KEYWORDS[name], name, start_line)
        return Token(IDENTIFIER, name, start_line)

    def read_operator(self) -> Union[Token, None]:
        """Read an operator or delimiter."""
        start_line = self.line_no
        # Try longest matches first
        for op_str in ('==', '!=', '<=', '>='):
            if self.pos + len(op_str) <= len(self.source):
                if self.source[self.pos:self.pos + len(op_str)] == op_str:
                    for _ in range(len(op_str)):
                        self.advance()
                    return Token(OPERATORS[op_str], op_str, start_line)

        ch = self.current_char()
        if ch in OPERATORS:
            self.advance()
            return Token(OPERATORS[ch], ch, start_line)
        if ch == '(':
            self.advance()
            return Token(LPAREN, '(', start_line)
        if ch == ')':
            self.advance()
            return Token(RPAREN, ')', start_line)
        if ch == ':':
            self.advance()
            return Token(COLON, ':', start_line)
        if ch == ',':
            self.advance()
            return Token(COMMA, ',', start_line)
        return None
