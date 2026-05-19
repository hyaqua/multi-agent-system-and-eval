# camera.py - Camera class for horizontal scrolling

import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT


class Camera:
    """Camera that follows the player horizontally, clamped to world bounds."""

    def __init__(self, world_width, world_height):
        self.offset_x = 0
        self.offset_y = 0
        self.world_width = world_width
        self.world_height = world_height

    def update(self, target):
        """Center camera on target (player)."""
        # Center the target
        self.offset_x = target.rect.centerx - SCREEN_WIDTH // 2
        self.offset_y = target.rect.centery - SCREEN_HEIGHT // 2

        # Clamp to world bounds
        self.offset_x = max(0, min(self.offset_x, self.world_width - SCREEN_WIDTH))
        self.offset_y = max(0, min(self.offset_y, self.world_height - SCREEN_HEIGHT))

    def apply(self, rect):
        """Return a new rect shifted by camera offset (for drawing)."""
        return rect.move(-self.offset_x, -self.offset_y)

    def apply_point(self, x, y):
        """Return a point shifted by camera offset."""
        return (x - self.offset_x, y - self.offset_y)
