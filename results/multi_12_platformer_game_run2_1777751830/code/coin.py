import pygame
from settings import COIN_SIZE, COLOR_GOLD, COLOR_YELLOW


class Coin:
    """A collectible coin."""

    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x - COIN_SIZE // 2, y - COIN_SIZE // 2, COIN_SIZE, COIN_SIZE)
        self.collected = False
        self.anim_timer = 0

    def update(self):
        """Update coin animation."""
        self.anim_timer += 1

    def draw(self, screen: pygame.Surface, camera_offset: int):
        """Draw the coin relative to the camera."""
        if self.collected:
            return
        adjusted_rect = self.rect.move(-camera_offset, 0)

        # Pulsating effect
        import math
        pulse = math.sin(self.anim_timer * 0.1) * 2
        draw_rect = adjusted_rect.inflate(pulse, pulse)

        pygame.draw.ellipse(screen, COLOR_GOLD, draw_rect)
        pygame.draw.ellipse(screen, COLOR_YELLOW, draw_rect.inflate(-4, -4))
