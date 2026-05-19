class SQLError(Exception):
    """Custom SQL error with optional position for syntax/semantic errors."""

    def __init__(self, message, pos=None):
        super().__init__(message)
        self.message = message
        self.pos = pos  # (line, col) or None

    def __str__(self):
        if self.pos:
            return f"Error at line {self.pos[0]}, col {self.pos[1]}: {self.message}"
        return f"Error: {self.message}"
