"""Lexer/Tokenizer for the bytecode interpreter language.

Tokenizes source code into tokens: numbers, strings, identifiers,
keywords, operators, and delimiters. Handles single-line comments
and Python-style indentation (INDENT/DEDENT tokens).
"""

from enum import Enum, auto
from typing import List, Any


class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()

    # Keywords
    PRINT = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    DEF = auto()
    RETURN = auto()

    # Operators
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    EQ = auto()         # =
    EQ_EQ = auto()      # ==
    NOT_EQ = auto()     # !=
    LT = auto()         # <
    GT = auto()         # >
    LT_EQ = auto()      # <=
    GT_EQ = auto()      # >=

    # Delimiters
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    COLON = auto()      # :
    COMMA = auto()      # ,
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


class Token:
    """A single token with type, optional value, and source position."""

    def __init__(self, token_type: TokenType, value: Any = None,
                 line: int = 0, col: int = 0):
        self.type = token_type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"


# Mapping from keyword strings to token types
KEYWORDS = {
    'print': TokenType.PRINT,
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'while': TokenType.WHILE,
    'def': TokenType.DEF,
    'return': TokenType.RETURN,
}


class LexerError(Exception):
    """Raised when the lexer encounters invalid syntax."""

    def __init__(self, message: str, line: int = 0, col: int = 0,
                 filename: str = '<unknown>'):
        self.line = line
        self.col = col
        self.filename = filename
        super().__init__(f"{filename}:{line}:{col}: {message}")


class Lexer:
    """Converts source code into a list of tokens."""

    def __init__(self, source: str, filename: str = '<unknown>'):
        self.source = source
        self.filename = filename
        self.tokens: List[Token] = []
        self._tokenize()

    def _tokenize(self):
        """Main tokenization driver. Splits into lines, handles
        indentation, then tokenizes each line's content."""
        raw_lines = self.source.split('\n')

        # Process lines: strip comments, compute indentation, skip blanks
        processed = []  # (indent_level, content, line_number)

        for i, raw_line in enumerate(raw_lines):
            line_number = i + 1

            # Remove comment (but not inside strings — simplified:
            # we strip from first # outside a string)
            comment_pos = self._find_comment(raw_line)
            if comment_pos != -1:
                line = raw_line[:comment_pos]
            else:
                line = raw_line

            # If the line is blank (only whitespace), skip it
            stripped = line.strip()
            if not stripped:
                continue

            # Compute indentation (spaces=1, tabs=4)
            indent = 0
            for ch in line:
                if ch == ' ':
                    indent += 1
                elif ch == '\t':
                    indent += 4
                else:
                    break

            processed.append((indent, stripped, line_number))

        # Emit INDENT / DEDENT tokens and tokenize each line
        indent_stack = [0]

        for indent, content, line_number in processed:
            # Handle indentation changes
            if indent > indent_stack[-1]:
                indent_stack.append(indent)
                self.tokens.append(Token(TokenType.INDENT, '', line_number, 0))
            elif indent < indent_stack[-1]:
                while indent < indent_stack[-1]:
                    indent_stack.pop()
                    self.tokens.append(Token(TokenType.DEDENT, '', line_number, 0))
                if indent != indent_stack[-1]:
                    raise LexerError(
                        f"Indentation error: expected {indent_stack[-1]} spaces, "
                        f"got {indent}",
                        line=line_number, col=0, filename=self.filename)

            # Tokenize the content of this line
            self._tokenize_line(content, line_number)

            # End each logical line with NEWLINE
            self.tokens.append(Token(TokenType.NEWLINE, '\n', line_number, 0))

        # Close any remaining indentation levels
        while len(indent_stack) > 1:
            indent_stack.pop()
            self.tokens.append(
                Token(TokenType.DEDENT, '', len(raw_lines), 0))

        # EOF marker
        self.tokens.append(Token(TokenType.EOF, None, len(raw_lines), 0))

    def _find_comment(self, line: str) -> int:
        """Find the position of a comment character (#) that is not
        inside a string literal. Returns -1 if none found."""
        in_string = False
        string_char = None
        for i, ch in enumerate(line):
            if in_string:
                if ch == '\\' and i + 1 < len(line):
                    # Skip escape sequence
                    pass  # just continue; we'll skip next char below
                elif ch == string_char:
                    in_string = False
            else:
                if ch in ('"', "'"):
                    in_string = True
                    string_char = ch
                elif ch == '#':
                    return i
        return -1

    def _tokenize_line(self, content: str, line_number: int):
        """Tokenize the content of a single logical line."""
        pos = 0
        while pos < len(content):
            c = content[pos]

            if c.isspace():
                pos += 1
                continue

            elif c.isdigit():
                pos = self._read_number(content, pos, line_number)

            elif c in ('"', "'"):
                pos = self._read_string(content, pos, line_number, c)

            elif c.isalpha() or c == '_':
                pos = self._read_ident_or_keyword(content, pos, line_number)

            elif c in '=!<>':
                pos = self._read_comparison_operator(content, pos, line_number)

            elif c in '+-*/() :,':
                type_map = {
                    '+': TokenType.PLUS, '-': TokenType.MINUS,
                    '*': TokenType.STAR, '/': TokenType.SLASH,
                    '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                    ':': TokenType.COLON, ',': TokenType.COMMA,
                }
                self.tokens.append(
                    Token(type_map[c], c, line_number, pos))
                pos += 1

            else:
                raise LexerError(
                    f"Unexpected character '{c}'",
                    line=line_number, col=pos, filename=self.filename)

    def _read_number(self, content: str, pos: int, line: int) -> int:
        """Read a numeric literal (int or float). Returns new position."""
        start = pos
        is_float = False
        while pos < len(content) and (content[pos].isdigit() or content[pos] == '.'):
            if content[pos] == '.':
                if is_float:
                    raise LexerError(
                        "Invalid number: multiple decimal points",
                        line=line, col=pos, filename=self.filename)
                is_float = True
            pos += 1

        num_str = content[start:pos]
        if is_float:
            value = float(num_str)
        else:
            value = int(num_str)

        self.tokens.append(Token(TokenType.NUMBER, value, line, start))
        return pos

    def _read_string(self, content: str, pos: int, line: int,
                     quote: str) -> int:
        """Read a string literal. Returns new position."""
        pos += 1  # Skip opening quote
        s = ''
        while pos < len(content) and content[pos] != quote:
            if content[pos] == '\\' and pos + 1 < len(content):
                pos += 1
                ec = content[pos]
                escape_map = {'n': '\n', 't': '\t', '\\': '\\',
                              '"': '"', "'": "'"}
                if ec in escape_map:
                    s += escape_map[ec]
                else:
                    s += '\\' + ec
            else:
                s += content[pos]
            pos += 1

        if pos >= len(content):
            raise LexerError(
                "Unterminated string literal",
                line=line, col=pos, filename=self.filename)

        pos += 1  # Skip closing quote
        self.tokens.append(Token(TokenType.STRING, s, line, pos))
        return pos

    def _read_ident_or_keyword(self, content: str, pos: int,
                                line: int) -> int:
        """Read an identifier or keyword. Returns new position."""
        start = pos
        while pos < len(content) and (content[pos].isalnum() or content[pos] == '_'):
            pos += 1

        word = content[start:pos]
        if word in KEYWORDS:
            self.tokens.append(Token(KEYWORDS[word], word, line, start))
        else:
            self.tokens.append(Token(TokenType.IDENT, word, line, start))
        return pos

    def _read_comparison_operator(self, content: str, pos: int,
                                   line: int) -> int:
        """Read =, ==, !=, <, <=, >, >=. Returns new position."""
        c = content[pos]
        if pos + 1 < len(content) and content[pos + 1] == '=':
            op = content[pos:pos + 2]
            type_map = {
                '==': TokenType.EQ_EQ, '!=': TokenType.NOT_EQ,
                '<=': TokenType.LT_EQ, '>=': TokenType.GT_EQ,
            }
            self.tokens.append(Token(type_map[op], op, line, pos))
            return pos + 2
        else:
            type_map = {
                '=': TokenType.EQ, '<': TokenType.LT, '>': TokenType.GT,
            }
            if c == '!':
                raise LexerError(
                    "Unexpected character '!' (did you mean '!='?)",
                    line=line, col=pos, filename=self.filename)
            self.tokens.append(Token(type_map[c], c, line, pos))
            return pos + 1
