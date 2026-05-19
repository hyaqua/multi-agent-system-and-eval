"""
Tetromino piece definitions: shapes, rotations, and colors.

Each piece is stored as a list of rotation states; each state is a 4x4
(or smaller) matrix where 1 means filled and 0 means empty.

The shape list uses row-major order: shape[row][col].
"""

import random
from constants import CYAN, YELLOW, PURPLE, GREEN, RED, ORANGE, BLUE

# ---------------------------------------------------------------------------
# All rotation states derived from the standard Super Rotation System (SRS)
# simplified: we store 4 rotation states for I, 4 for T, S, Z, L, J and 1 for O.
# ---------------------------------------------------------------------------

PIECES = {
    "I": {
        "color": CYAN,
        "shapes": [
            # 0° – horizontal
            [[0, 0, 0, 0],
             [1, 1, 1, 1],
             [0, 0, 0, 0],
             [0, 0, 0, 0]],
            # 90° – vertical
            [[0, 0, 1, 0],
             [0, 0, 1, 0],
             [0, 0, 1, 0],
             [0, 0, 1, 0]],
            # 180°
            [[0, 0, 0, 0],
             [0, 0, 0, 0],
             [1, 1, 1, 1],
             [0, 0, 0, 0]],
            # 270°
            [[0, 1, 0, 0],
             [0, 1, 0, 0],
             [0, 1, 0, 0],
             [0, 1, 0, 0]],
        ],
    },
    "O": {
        "color": YELLOW,
        "shapes": [
            [[1, 1],
             [1, 1]],
        ],
    },
    "T": {
        "color": PURPLE,
        "shapes": [
            # 0°
            [[0, 1, 0],
             [1, 1, 1],
             [0, 0, 0]],
            # 90°
            [[0, 1, 0],
             [0, 1, 1],
             [0, 1, 0]],
            # 180°
            [[0, 0, 0],
             [1, 1, 1],
             [0, 1, 0]],
            # 270°
            [[0, 1, 0],
             [1, 1, 0],
             [0, 1, 0]],
        ],
    },
    "S": {
        "color": GREEN,
        "shapes": [
            # 0°
            [[0, 1, 1],
             [1, 1, 0],
             [0, 0, 0]],
            # 90°
            [[0, 1, 0],
             [0, 1, 1],
             [0, 0, 1]],
            # 180°
            [[0, 0, 0],
             [0, 1, 1],
             [1, 1, 0]],
            # 270°
            [[1, 0, 0],
             [1, 1, 0],
             [0, 1, 0]],
        ],
    },
    "Z": {
        "color": RED,
        "shapes": [
            # 0°
            [[1, 1, 0],
             [0, 1, 1],
             [0, 0, 0]],
            # 90°
            [[0, 0, 1],
             [0, 1, 1],
             [0, 1, 0]],
            # 180°
            [[0, 0, 0],
             [1, 1, 0],
             [0, 1, 1]],
            # 270°
            [[0, 1, 0],
             [1, 1, 0],
             [1, 0, 0]],
        ],
    },
    "L": {
        "color": ORANGE,
        "shapes": [
            # 0°
            [[0, 0, 1],
             [1, 1, 1],
             [0, 0, 0]],
            # 90°
            [[0, 1, 0],
             [0, 1, 0],
             [0, 1, 1]],
            # 180°
            [[0, 0, 0],
             [1, 1, 1],
             [1, 0, 0]],
            # 270°
            [[1, 1, 0],
             [0, 1, 0],
             [0, 1, 0]],
        ],
    },
    "J": {
        "color": BLUE,
        "shapes": [
            # 0°
            [[1, 0, 0],
             [1, 1, 1],
             [0, 0, 0]],
            # 90°
            [[0, 1, 1],
             [0, 1, 0],
             [0, 1, 0]],
            # 180°
            [[0, 0, 0],
             [1, 1, 1],
             [0, 0, 1]],
            # 270°
            [[0, 1, 0],
             [0, 1, 0],
             [1, 1, 0]],
        ],
    },
}

# All piece type names
PIECE_NAMES = list(PIECES.keys())


def random_piece() -> dict:
    """Return a fresh piece dict ready to spawn (rotation 0, no position)."""
    name = random.choice(PIECE_NAMES)
    info = PIECES[name]
    return {
        "type": name,
        "color": info["color"],
        "shapes": info["shapes"],
        "rotation": 0,
        "x": 0,
        "y": 0,
    }
