"""
Tetris game constants and configuration.
All cross-module settings live here as the single source of truth.
"""
SCALE = 2.5
# Grid dimensions (cells)
COLS = 10
ROWS = 20

# Cell size in pixels
CELL_SIZE = 30*SCALE

# Layout offsets
BOARD_X = 40   # top-left x of the playing field
BOARD_Y = 40   # top-left y of the playing field

# The board is drawn with a 1-pixel grid line so real board pixel size:
BOARD_PIXEL_W = COLS * CELL_SIZE
BOARD_PIXEL_H = ROWS * CELL_SIZE

# Next-piece preview area
PREVIEW_X = BOARD_X + BOARD_PIXEL_W + 30
PREVIEW_Y = BOARD_Y + 10
PREVIEW_CELL = 25*SCALE

# Screen dimensions
SCREEN_W = PREVIEW_X + 4 * PREVIEW_CELL + 40
SCREEN_H = BOARD_Y + BOARD_PIXEL_H + 40

# Colors (R, G, B)
BLACK       = (0, 0, 0)
DARK_GRAY   = (30, 30, 30)
GRAY        = (60, 60, 60)
LIGHT_GRAY  = (180, 180, 180)
WHITE       = (255, 255, 255)
CYAN        = (0, 255, 255)   # I
YELLOW      = (255, 255, 0)   # O
PURPLE      = (160, 32, 240)  # T
GREEN       = (0, 255, 0)     # S
RED         = (255, 0, 0)     # Z
ORANGE      = (255, 165, 0)   # L
BLUE        = (0, 0, 255)     # J

BG_COLOR    = (20, 20, 40)
BOARD_BG    = (15, 15, 30)
BORDER_COLOR = (100, 100, 140)
GHOST_COLOR = (255, 255, 255, 40)  # RGBA, alpha ignored in software surfaces
TEXT_COLOR  = (220, 220, 220)

# Timing (milliseconds)
INITIAL_SPEED = 800      # ms between automatic drops at level 1
SPEED_DECREMENT = 55     # ms faster per level
MIN_SPEED = 100          # fastest drop interval
FPS = 60

# Scoring
POINTS_PER_LINE = {1: 100, 2: 300, 3: 500, 4: 800}
LINES_PER_LEVEL = 10

# Key repeat settings (delay, interval) in ms
KEY_REPEAT_DELAY = 150
KEY_REPEAT_INTERVAL = 50
