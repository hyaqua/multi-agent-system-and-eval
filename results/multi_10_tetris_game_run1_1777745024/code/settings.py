# Game constants

# Grid dimensions
GRID_WIDTH = 10
GRID_HEIGHT = 20
CELL_SIZE = 32

# Window layout
PREVIEW_CELL_SIZE = 24
PREVIEW_AREA_WIDTH = 160
SIDEBAR_PADDING = 20
GRID_OFFSET_X = 30
GRID_OFFSET_Y = 30

# Window size
WINDOW_WIDTH = GRID_OFFSET_X * 2 + GRID_WIDTH * CELL_SIZE + SIDEBAR_PADDING + PREVIEW_AREA_WIDTH
WINDOW_HEIGHT = GRID_OFFSET_Y * 2 + GRID_HEIGHT * CELL_SIZE

# Colors
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
DARK_GRAY = (30, 30, 30)
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 200)
GRID_BORDER = (100, 100, 100)
GRID_BG = (20, 20, 20)

# Piece colors (RGB)
PIECE_COLORS = {
    'I': (0, 255, 255),      # Cyan
    'O': (255, 255, 0),      # Yellow
    'T': (128, 0, 128),      # Purple
    'S': (0, 255, 0),        # Green
    'Z': (255, 0, 0),        # Red
    'L': (255, 165, 0),      # Orange
    'J': (0, 0, 255),        # Blue
}

# Fall speed (milliseconds per drop)
BASE_DROP_INTERVAL = 800       # Level 0: 800ms
SPEED_DECREASE = 70            # Subtract 70ms per level
MIN_DROP_INTERVAL = 50         # Fastest fall
SOFT_DROP_INTERVAL = 50        # When holding down arrow

# Score table: lines cleared -> points
SCORE_TABLE = {
    1: 100,
    2: 300,
    3: 500,
    4: 800,
}

# Level up every N lines cleared
LINES_PER_LEVEL = 10

# FPS
FPS = 60
