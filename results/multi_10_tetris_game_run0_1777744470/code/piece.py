"""
Tetromino piece definitions and rotation logic.
"""

from constants import PIECE_COLORS, COLS


# Each shape is a 2D list of 1/0. Shapes are stored in their "spawn" orientation.
# Rotation: transpose the matrix then reverse each row (clockwise 90°).

SHAPES = {
    'I': {
        'shape': [
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ],
        'color': PIECE_COLORS['I'],
    },
    'O': {
        'shape': [
            [1, 1],
            [1, 1],
        ],
        'color': PIECE_COLORS['O'],
    },
    'T': {
        'shape': [
            [0, 1, 0],
            [1, 1, 1],
            [0, 0, 0],
        ],
        'color': PIECE_COLORS['T'],
    },
    'S': {
        'shape': [
            [0, 1, 1],
            [1, 1, 0],
            [0, 0, 0],
        ],
        'color': PIECE_COLORS['S'],
    },
    'Z': {
        'shape': [
            [1, 1, 0],
            [0, 1, 1],
            [0, 0, 0],
        ],
        'color': PIECE_COLORS['Z'],
    },
    'L': {
        'shape': [
            [1, 0, 0],
            [1, 1, 1],
            [0, 0, 0],
        ],
        'color': PIECE_COLORS['L'],
    },
    'J': {
        'shape': [
            [0, 0, 1],
            [1, 1, 1],
            [0, 0, 0],
        ],
        'color': PIECE_COLORS['J'],
    },
}


def rotate_shape_clockwise(shape):
    """Return a new shape rotated 90 degrees clockwise.
    Transpose then reverse each row."""
    rows = len(shape)
    cols = len(shape[0])
    # Transpose
    rotated = [[shape[r][c] for r in range(rows - 1, -1, -1)] for c in range(cols)]
    return rotated


class Piece:
    """Represents an active (falling) tetromino."""

    def __init__(self, piece_type):
        self.type = piece_type
        data = SHAPES[piece_type]
        self.shape = [row[:] for row in data['shape']]  # deep copy
        self.color = data['color']
        # Spawn position: horizontally centred, vertically at top
        self.x = (COLS - len(self.shape[0])) // 2
        self.y = -1  # start one row above the board

    @property
    def width(self):
        return len(self.shape[0])

    @property
    def height(self):
        return len(self.shape)

    def rotate(self):
        """Return a new shape matrix rotated 90° clockwise."""
        return rotate_shape_clockwise(self.shape)

    def get_cells(self):
        """Yield (col, row) board coordinates for each filled cell of the piece."""
        for r, row in enumerate(self.shape):
            for c, value in enumerate(row):
                if value:
                    yield (self.x + c, self.y + r)
