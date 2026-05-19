"""Token definitions for the bytecode interpreter."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Types of tokens the lexer can produce."""
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    KEYWORD = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    """A single token from the lexer."""
    type: TokenType
    value: str
    line: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line})"


# Keyword set
KEYWORDS = {
    'if', 'else', 'while', 'def', 'print', 'return', 'end',
}
