"""
Platformer Game - Camera module
Horizontal viewport tracking that follows the player.
"""
from constants import *


class Camera:
    def __init__(self, level_width):
        self.camera_x = 0
        self.level_width = level_width

    def update(self, player_rect):
        """Center camera on player, clamped to level bounds."""
        target_x = player_rect.centerx - WIDTH // 2
        # Clamp so camera doesn't show beyond level edges
        self.camera_x = max(0, min(target_x, self.level_width - WIDTH))
        # Allow negative only if level is smaller than screen
        if self.level_width < WIDTH:
            self.camera_x = 0

    def set_level_width(self, level_width):
        """Update level width (when loading new level)."""
        self.level_width = level_width
        self.camera_x = 0
