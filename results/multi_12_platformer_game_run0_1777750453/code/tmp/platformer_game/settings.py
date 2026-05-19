# settings.py - All constants for the platformer game

# Screen
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 100, 255)
YELLOW = (255, 255, 0)
SKY_BLUE = (135, 206, 235)
BROWN = (139, 90, 43)
ORANGE = (255, 165, 0)
DARK_GREEN = (0, 150, 0)
DARK_RED = (180, 0, 0)
GRAY = (128, 128, 128)

# Player
PLAYER_WIDTH = 30
PLAYER_HEIGHT = 40
PLAYER_SPEED = 5
JUMP_STRENGTH = -13
GRAVITY = 0.7
MAX_HEALTH = 5
INVINCIBILITY_TIME = 60  # frames (~1 second at 60fps)

# Enemy
ENEMY_WIDTH = 30
ENEMY_HEIGHT = 30
ENEMY_SPEED = 2

# Coin
COIN_RADIUS = 10

# Goal
GOAL_COLOR = (255, 215, 0)  # Gold

# Platform default
PLATFORM_COLOR = GREEN
