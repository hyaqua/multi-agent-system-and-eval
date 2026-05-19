"""
Tetris constants and configuration.
"""

# Grid dimensions
COLS = 10
ROWS = 20
CELL_SIZE = 30

# Window layout
BOARD_WIDTH = COLS * CELL_SIZE       # 300
BOARD_HEIGHT = ROWS * CELL_SIZE      # 600
SIDEBAR_WIDTH = 160
PADDING = 20
WINDOW_WIDTH = PADDING + BOARD_WIDTH + PADDING + SIDEBAR_WIDTH + PADDING
WINDOW_HEIGHT = PADDING + BOARD_HEIGHT + PADDING

# Board offset on screen
BOARD_X = PADDING
BOARD_Y = PADDING

# Sidebar positions
SIDEBAR_X = BOARD_X + BOARD_WIDTH + PADDING
SIDEBAR_Y = PADDING

# Colors (R, G, B)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (40, 40, 40)
LIGHT_GRAY = (180, 180, 180)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 0)
PURPLE = (160, 32, 240)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
ORANGE = (255, 165, 0)
BLUE = (0, 0, 255)

# Piece colors mapped by type
PIECE_COLORS = {
    'I': CYAN,
    'O': YELLOW,
    'T': PURPLE,
    'S': GREEN,
    'Z': RED,
    'L': ORANGE,
    'J': BLUE,
}

# Background / grid colors
BG_COLOR = (20, 20, 30)
GRID_LINE_COLOR = (50, 50, 60)
BOARD_BORDER_COLOR = (100, 100, 120)

# Timing (milliseconds)
INITIAL_DROP_INTERVAL = 800   # starting speed
MIN_DROP_INTERVAL = 80        # fastest speed cap
SPEED_DECREMENT_PER_LEVEL = 60
SOFT_DROP_INTERVAL = 50       # interval when soft-dropping

# Scoring
POINTS_PER_LINE = {1: 100, 2: 300, 3: 500, 4: 800}
LINES_PER_LEVEL = 10

# Piece spawn position (top-centre of board)
SPAWN_Y = -1  # start slightly above visible area so 2-row pieces are partially visible
