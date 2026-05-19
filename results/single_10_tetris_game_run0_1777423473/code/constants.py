# Tetris Constants

# Screen dimensions
SCREEN_WIDTH = 550
SCREEN_HEIGHT = 700

# Grid dimensions
GRID_COLS = 10
GRID_ROWS = 20
HIDDEN_ROWS = 2  # rows above visible area for spawning

# Cell size in pixels
CELL_SIZE = 30

# Board position (top-left of visible grid)
BOARD_X = 40
BOARD_Y = 50

# Preview panel position
PREVIEW_X = 380
PREVIEW_Y = 120
PREVIEW_CELL_SIZE = 25

# Colors (RGB)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
DARK_GRAY = (30, 30, 30)
LIGHT_GRAY = (100, 100, 100)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
PURPLE = (160, 32, 240)
RED = (255, 0, 0)

# Tetromino definitions: shape matrices for each rotation state
# Using standard SRS-inspired shapes
TETROMINOES = {
    'I': {
        'shape': [
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ],
        'color': CYAN
    },
    'O': {
        'shape': [
            [1, 1],
            [1, 1]
        ],
        'color': YELLOW
    },
    'T': {
        'shape': [
            [0, 1, 0],
            [1, 1, 1],
            [0, 0, 0]
        ],
        'color': PURPLE
    },
    'S': {
        'shape': [
            [0, 1, 1],
            [1, 1, 0],
            [0, 0, 0]
        ],
        'color': GREEN
    },
    'Z': {
        'shape': [
            [1, 1, 0],
            [0, 1, 1],
            [0, 0, 0]
        ],
        'color': RED
    },
    'L': {
        'shape': [
            [1, 0, 0],
            [1, 1, 1],
            [0, 0, 0]
        ],
        'color': ORANGE
    },
    'J': {
        'shape': [
            [0, 0, 1],
            [1, 1, 1],
            [0, 0, 0]
        ],
        'color': BLUE
    }
}

# Initial fall speed (milliseconds per automatic drop)
INITIAL_SPEED = 800
# Minimum fall speed
MIN_SPEED = 100
# Speed decrement per level
SPEED_DECREMENT = 60
# Lines needed per level
LINES_PER_LEVEL = 10

# Score values
SCORE_TABLE = {
    1: 100,   # single
    2: 300,   # double
    3: 500,   # triple
    4: 800    # tetris
}

# Soft drop score bonus per cell
SOFT_DROP_BONUS = 1
