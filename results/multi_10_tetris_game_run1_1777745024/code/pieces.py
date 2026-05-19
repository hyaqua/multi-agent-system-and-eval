"""Tetromino piece definitions and Piece class."""

# Each piece has 4 rotation states (0°, 90°, 180°, 270°).
# Each state is a list of (dx, dy) offsets relative to the piece's pivot point.
# The pivot is the piece's (row, col) position on the grid.

SHAPES = {
    'I': [
        # Rotation 0 (horizontal)
        [(0, 0), (0, 1), (0, 2), (0, 3)],
        # Rotation 1 (vertical)
        [(-1, 0), (0, 0), (1, 0), (2, 0)],
        # Rotation 2 (horizontal, flipped)
        [(0, 0), (0, 1), (0, 2), (0, 3)],
        # Rotation 3 (vertical, flipped)
        [(-1, 0), (0, 0), (1, 0), (2, 0)],
    ],
    'O': [
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
        [(0, 0), (0, 1), (1, 0), (1, 1)],
    ],
    'T': [
        # Rotation 0 (flat side down)
        [(-1, 0), (0, -1), (0, 0), (0, 1)],
        # Rotation 1 (flat side left)
        [(-1, 0), (0, 0), (1, 0), (0, 1)],
        # Rotation 2 (flat side up)
        [(0, -1), (0, 0), (0, 1), (1, 0)],
        # Rotation 3 (flat side right)
        [(0, -1), (-1, 0), (0, 0), (1, 0)],
    ],
    'S': [
        # Rotation 0
        [(-1, 1), (-1, 0), (0, 0), (0, -1)],
        # Rotation 1
        [(-1, 0), (0, 0), (0, 1), (1, 1)],
        # Rotation 2
        [(-1, 1), (-1, 0), (0, 0), (0, -1)],
        # Rotation 3
        [(-1, 0), (0, 0), (0, 1), (1, 1)],
    ],
    'Z': [
        # Rotation 0
        [(0, -1), (0, 0), (-1, 0), (-1, 1)],
        # Rotation 1
        [(-1, -1), (0, -1), (0, 0), (1, 0)],
        # Rotation 2
        [(0, -1), (0, 0), (-1, 0), (-1, 1)],
        # Rotation 3
        [(-1, -1), (0, -1), (0, 0), (1, 0)],
    ],
    'L': [
        # Rotation 0
        [(-1, 0), (0, 0), (1, 0), (1, 1)],
        # Rotation 1
        [(0, -1), (0, 0), (0, 1), (1, -1)],
        # Rotation 2
        [(-1, -1), (-1, 0), (0, 0), (1, 0)],
        # Rotation 3
        [(-1, 1), (0, -1), (0, 0), (0, 1)],
    ],
    'J': [
        # Rotation 0
        [(-1, 0), (0, 0), (1, 0), (1, -1)],
        # Rotation 1
        [(-1, -1), (0, -1), (0, 0), (0, 1)],
        # Rotation 2
        [(-1, 0), (-1, 1), (0, 0), (1, 0)],
        # Rotation 3
        [(0, -1), (0, 0), (0, 1), (1, 1)],
    ],
}

PIECE_TYPES = list(SHAPES.keys())


class Piece:
    """Represents an active tetromino piece."""

    def __init__(self, piece_type: str, row: int = 0, col: int = 0, rotation: int = 0):
        self.type = piece_type
        self.row = row  # pivot row
        self.col = col  # pivot column
        self.rotation = rotation  # 0-3

    def cells(self):
        """Return list of (row, col) world coordinates for the piece."""
        offsets = SHAPES[self.type][self.rotation]
        return [(self.row + dr, self.col + dc) for dr, dc in offsets]

    def move(self, dr: int, dc: int):
        """Move piece by (dr, dc). Returns new Piece (does not mutate)."""
        return Piece(self.type, self.row + dr, self.col + dc, self.rotation)

    def rotated(self, direction: int = 1):
        """Return new Piece rotated clockwise (direction=1) or counter-clockwise (-1)."""
        new_rotation = (self.rotation + direction) % 4
        return Piece(self.type, self.row, self.col, new_rotation)

    def clone(self):
        """Return a copy of this piece."""
        return Piece(self.type, self.row, self.col, self.rotation)
