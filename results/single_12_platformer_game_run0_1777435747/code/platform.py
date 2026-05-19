"""
Platform class: solid colored rectangles that the player stands on.
"""
import pygame
from settings import PLATFORM_COLOR, PLATFORM_OUTLINE, PLATFORM_HEIGHT


class Platform:
    def __init__(self, x, y, width):
        self.rect = pygame.Rect(x, y, width, PLATFORM_HEIGHT)
        self.width = width

    def draw(self, screen, camera_x):
        draw_rect = self.rect.move(-camera_x, 0)
        pygame.draw.rect(screen, PLATFORM_COLOR, draw_rect)
        pygame.draw.rect(screen, PLATFORM_OUTLINE, draw_rect, 2)
        # Grass/dirt line on top
        pygame.draw.line(
            screen, (80, 160, 40),
            (draw_rect.left, draw_rect.top),
            (draw_rect.right, draw_rect.top),
            3,
        )
