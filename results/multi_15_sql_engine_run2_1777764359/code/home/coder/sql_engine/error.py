"""Custom exception classes for the SQL engine."""


class SQLError(Exception):
    """Base exception for SQL engine errors."""
    pass


class ParseError(SQLError):
    """Raised when a syntax error is encountered during parsing."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        if line > 0 and column > 0:
            msg = f"{message} at line {line}, column {column}"
        elif line > 0:
            msg = f"{message} at line {line}"
        else:
            msg = message
        super().__init__(msg)
        self.line = line
        self.column = column


class QueryError(SQLError):
    """Raised when a runtime error occurs during query execution."""
    pass
