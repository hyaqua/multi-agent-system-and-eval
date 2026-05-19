"""
Coin class: collectible items.
"""
import pygame
from settings import COIN_RADIUS, COIN_COLOR
import math


class Coin:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x - COIN_RADIUS, y - COIN_RADIUS,
                                COIN_RADIUS * 2, COIN_RADIUS * 2)
        self.x = x
        self.y = y
        self.tick = 0

    def update(self):
        self.tick += 1

    def draw(self, screen, camera_x):
        draw_x = self.x - camera_x
        # Slight bob
        bob = math.sin(self.tick * 0.08) * 3
        draw_y = self.y - COIN_RADIUS + bob
        # Outer glow
        pygame.draw.circle(screen, (255, 240, 100), (draw_x, draw_y + COIN_RADIUS), COIN_RADIUS + 2)
        pygame.draw.circle(screen, COIN_COLOR, (draw_x, draw_y + COIN_RADIUS), COIN_RADIUS)
        # Inner shine
        pygame.draw.circle(screen, (255, 255, 220), (draw_x - 2, draw_y + COIN_RADIUS - 2), COIN_RADIUS // 3)
