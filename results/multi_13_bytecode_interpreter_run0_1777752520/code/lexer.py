"""Lexer: tokenizes source code into a list of Token objects."""

from tokens import Token, NUMBER, STRING, ID, KEYWORD, OP, DELIM, EOF

KEYWORDS = {
    "if", "else", "while", "def", "return", "print",
    "true", "false",
}

# Multi-character operators, longest first
MULTI_OPS = [
    ("==", "=="),
    ("!=", "!="),
    ("<=", "<="),
    (">=", ">="),
]

SINGLE_OPS = {
    "+", "-", "*", "/", "<", ">", "=",
}

DELIMITERS = {"(", ")", "{", "}", ",", ":", ";"}


class Lexer:
    """Tokenizes source text into a list of Tokens."""

    def __init__(self, source):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1

    def current_char(self):
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def advance(self):
        ch = self.current_char()
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
        return ch

    def skip_whitespace(self):
        while self.current_char() is not None and self.current_char() in " \t\r\n":
            self.advance()

    def skip_comment(self):
        # Assumes current char is '#'
        self.advance()
        while self.current_char() is not None and self.current_char() != "\n":
            self.advance()

    def read_number(self):
        start_line = self.line
        start_col = self.column
        num_str = ""
        is_float = False
        while self.current_char() is not None and self.current_char().isdigit():
            num_str += self.advance()
        if self.current_char() == ".":
            # Peek ahead to see if next char is digit
            if self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                is_float = True
                num_str += self.advance()  # the dot
                while self.current_char() is not None and self.current_char().isdigit():
                    num_str += self.advance()

        if is_float:
            value = float(num_str)
        else:
            value = int(num_str)
        return Token(NUMBER, value, start_line, start_col)

    def read_string(self):
        # Assumes current char is '"'
        start_line = self.line
        start_col = self.column
        self.advance()  # opening quote
        s = ""
        while self.current_char() is not None and self.current_char() != '"':
            ch = self.current_char()
            if ch == "\\":
                self.advance()
                nxt = self.current_char()
                if nxt is None:
                    break
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    '"': '"',
                    "\\": "\\",
                }
                s += escape_map.get(nxt, nxt)
                self.advance()
            elif ch == "\n":
                # Unterminated string
                break
            else:
                s += ch
                self.advance()
        if self.current_char() == '"':
            self.advance()  # closing quote
        return Token(STRING, s, start_line, start_col)

    def read_identifier_or_keyword(self):
        start_line = self.line
        start_col = self.column
        name = ""
        ch = self.current_char()
        while ch is not None and (ch.isalnum() or ch == "_"):
            name += ch
            self.advance()
            ch = self.current_char()

        if name in KEYWORDS:
            return Token(KEYWORD, name, start_line, start_col)
        else:
            return Token(ID, name, start_line, start_col)

    def tokenize(self):
        tokens = []
        while self.pos < len(self.source):
            self.skip_whitespace()
            ch = self.current_char()
            if ch is None:
                break

            if ch == "#":
                self.skip_comment()
                continue

            if ch.isdigit():
                tokens.append(self.read_number())
                continue

            if ch == '"':
                tokens.append(self.read_string())
                continue

            if ch.isalpha() or ch == "_":
                tokens.append(self.read_identifier_or_keyword())
                continue

            # Check multi-character operators
            matched = False
            for op_str, op_val in MULTI_OPS:
                if self.source[self.pos:self.pos + len(op_str)] == op_str:
                    start_line = self.line
                    start_col = self.column
                    for _ in range(len(op_str)):
                        self.advance()
                    tokens.append(Token(OP, op_val, start_line, start_col))
                    matched = True
                    break
            if matched:
                continue

            # Single-character operators
            if ch in SINGLE_OPS:
                start_line = self.line
                start_col = self.column
                self.advance()
                tokens.append(Token(OP, ch, start_line, start_col))
                continue

            # Delimiters
            if ch in DELIMITERS:
                start_line = self.line
                start_col = self.column
                self.advance()
                tokens.append(Token(DELIM, ch, start_line, start_col))
                continue

            # Unknown character
            start_line = self.line
            start_col = self.column
            raise SyntaxError(f"Unexpected character: {ch!r} at line {start_line}, column {start_col}")

        tokens.append(Token(EOF, None, self.line, self.column))
        return tokens
