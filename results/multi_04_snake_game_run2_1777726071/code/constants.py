"""
Central configuration for the Classic Snake Game.
"""

# Grid dimensions (in cells)
GRID_WIDTH = 20
GRID_HEIGHT = 20

# Cell size in pixels
CELL_SIZE = 30

# Derived window size
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE

# Colors (R, G, B)
COLOR_BACKGROUND = (20, 20, 20)          # dark background
COLOR_GRID_LINE = (40, 40, 40)           # subtle grid lines
COLOR_SNAKE_HEAD = (80, 200, 80)         # bright green head
COLOR_SNAKE_BODY = (50, 150, 50)         # darker green body
COLOR_FOOD = (220, 50, 50)               # red food
COLOR_TEXT = (255, 255, 255)             # white text
COLOR_GAME_OVER = (255, 80, 80)          # red-ish game over text

# Timing
FPS = 60
MOVE_INTERVAL = 150  # milliseconds between snake movements

# Initial snake
INITIAL_LENGTH = 3
INITIAL_DIRECTION = (1, 0)  # moving right
