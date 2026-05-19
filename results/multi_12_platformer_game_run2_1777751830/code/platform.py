import pygame
from settings import COLOR_BROWN


class Platform:
    """A static rectangular platform."""

    def __init__(self, x: int, y: int, width: int, height: int, color: tuple = None):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color if color else COLOR_BROWN

    def draw(self, screen: pygame.Surface, camera_offset: int):
        """Draw the platform relative to the camera."""
        adjusted_rect = self.rect.move(-camera_offset, 0)
        pygame.draw.rect(screen, self.color, adjusted_rect)
        # Draw a subtle border
        pygame.draw.rect(screen, (80, 60, 30), adjusted_rect, 2)
