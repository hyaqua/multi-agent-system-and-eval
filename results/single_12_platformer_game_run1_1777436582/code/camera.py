"""
camera.py – A Camera class that scrolls horizontally to follow the player.
"""
import pygame
from settings import *


class Camera:
    """Keeps track of an offset so the viewport follows the player."""

    def __init__(self, level_width, level_height):
        self.level_width = level_width
        self.level_height = level_height
        self.x = 0.0
        self.y = 0.0

    def update(self, target_rect):
        """Center the camera on the target rect horizontally,
           with a slight vertical offset."""
        # Horizontal: keep player centered
        target_x = target_rect.centerx - SCREEN_WIDTH // 2
        # Vertical: keep player slightly above center
        target_y = target_rect.centery - SCREEN_HEIGHT // 2 - 40

        # Clamp to level bounds
        self.x = max(0, min(target_x, self.level_width - SCREEN_WIDTH))
        self.y = max(0, min(target_y, self.level_height - SCREEN_HEIGHT))

    def apply(self, rect):
        """Return a new rect offset by camera position (for rendering)."""
        return rect.move(-int(self.x), -int(self.y))

    def apply_point(self, x, y):
        """Offset a single point for HUD elements that shouldn't scroll."""
        return (x - int(self.x), y - int(self.y))
