"""
settings.py – Constants and configuration for the platformer game.
"""

# Display
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
TITLE = "Platformer Game"

# Physics
GRAVITY = 0.8
PLAYER_SPEED = 5
PLAYER_JUMP_VELOCITY = -14
MAX_FALL_SPEED = 15

# Player dimensions
PLAYER_WIDTH = 30
PLAYER_HEIGHT = 40

# Enemy
ENEMY_WIDTH = 30
ENEMY_HEIGHT = 30
ENEMY_SPEED = 2

# Coin
COIN_RADIUS = 10

# Goal
GOAL_WIDTH = 30
GOAL_HEIGHT = 50

# Health
PLAYER_MAX_HEALTH = 5
INVULNERABILITY_FRAMES = 60  # ~1 second at 60fps

# Colors
SKY_BLUE = (135, 206, 235)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 50, 50)
GREEN = (50, 200, 50)
BLUE = (50, 100, 255)
YELLOW = (255, 220, 0)
BROWN = (139, 90, 43)
DARK_BROWN = (100, 60, 20)
GRAY = (120, 120, 120)
DARK_GRAY = (60, 60, 60)
ORANGE = (255, 150, 0)
PURPLE = (180, 0, 220)
GOLD = (255, 215, 0)
CYAN = (0, 200, 200)
