# Game grid constants
CELL_SIZE = 20
GRID_WIDTH = 30   # 30 cells wide
GRID_HEIGHT = 20  # 20 cells tall

# Window dimensions
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE   # 600
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE  # 400

# Colors (R, G, B)
COLOR_BG = (20, 20, 20)
COLOR_GRID = (35, 35, 35)
COLOR_SNAKE_HEAD = (0, 200, 0)
COLOR_SNAKE_BODY = (0, 160, 0)
COLOR_FOOD = (220, 30, 30)
COLOR_WHITE = (255, 255, 255)
COLOR_OVERLAY = (0, 0, 0, 140)  # RGBA for game-over overlay

# Directions as (dx, dy) tuples
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Timing
FPS = 60
MOVE_DELAY = 150  # milliseconds between moves
