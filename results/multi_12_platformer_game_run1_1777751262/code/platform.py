"""
Platformer Game - Platform module
Simple rect-based solid surfaces.
"""
import pygame
from constants import *


class Platform:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = PLATFORM_COLOR
        self.outline_color = PLATFORM_OUTLINE_COLOR

    def draw(self, screen, camera_x):
        """Draw the platform with camera offset."""
        draw_rect = pygame.Rect(
            self.rect.x - camera_x,
            self.rect.y,
            self.rect.width,
            self.rect.height
        )
        pygame.draw.rect(screen, self.color, draw_rect)
        pygame.draw.rect(screen, self.outline_color, draw_rect, 2)
        # Add grass-like texture on top
        grass_rect = pygame.Rect(
            draw_rect.x,
            draw_rect.y,
            draw_rect.width,
            6
        )
        pygame.draw.rect(screen, DARK_GREEN, grass_rect)
