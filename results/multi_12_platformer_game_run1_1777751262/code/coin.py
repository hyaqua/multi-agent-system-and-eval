"""
Platformer Game - Coin module
Collectible coin item.
"""
import pygame
from constants import *


class Coin:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, COIN_SIZE, COIN_SIZE)
        self.collected = False
        self.animation_timer = 0
        self.bob_offset = 0

    def update(self):
        """Animate the coin with a gentle bob."""
        self.animation_timer += 1
        self.bob_offset = int(3 * pygame.math.Vector2(0, 1).y *
                              (self.animation_timer * 0.05))
        # Actually, let's use sine-like bob
        import math
        self.bob_offset = int(2 * math.sin(self.animation_timer * 0.08))

    def draw(self, screen, camera_x):
        """Draw the coin with camera offset and bob effect."""
        if self.collected:
            return

        draw_rect = pygame.Rect(
            self.rect.x - camera_x,
            self.rect.y + self.bob_offset,
            self.rect.width,
            self.rect.height
        )

        # Draw glowing coin
        # Outer glow
        glow_rect = draw_rect.inflate(6, 6)
        glow_color = (255, 255, 150)
        pygame.draw.ellipse(screen, glow_color, glow_rect)

        # Main coin
        pygame.draw.ellipse(screen, COIN_COLOR, draw_rect)
        pygame.draw.ellipse(screen, (200, 160, 0), draw_rect, 2)

        # Dollar sign or star in middle
        center = draw_rect.center
        font = pygame.font.Font(None, 14)
        text = font.render("$", True, (180, 140, 0))
        text_rect = text.get_rect(center=center)
        screen.blit(text, text_rect)
