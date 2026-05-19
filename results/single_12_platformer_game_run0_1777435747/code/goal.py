"""
Goal / finish point: the player reaches this to advance to the next level.
"""
import pygame
from settings import GOAL_WIDTH, GOAL_HEIGHT, GOAL_COLOR


class Goal:
    def __init__(self, x, y):
        # Goal is placed such that bottom sits on the platform
        self.rect = pygame.Rect(x, y - GOAL_HEIGHT, GOAL_WIDTH, GOAL_HEIGHT)

    def draw(self, screen, camera_x):
        draw_rect = self.rect.move(-camera_x, 0)
        # Draw a flag/pillar
        pygame.draw.rect(screen, (120, 80, 30), draw_rect)  # pole
        # Flag triangle
        flag_rect = pygame.Rect(draw_rect.right - 10, draw_rect.top + 5, 30, 20)
        pygame.draw.polygon(screen, GOAL_COLOR, [
            (flag_rect.left, flag_rect.top),
            (flag_rect.right, flag_rect.top + 10),
            (flag_rect.left, flag_rect.bottom),
        ])
        # "GOAL" text
        font = pygame.font.Font(None, 18)
        txt = font.render("GOAL", True, (255, 255, 255))
        screen.blit(txt, (draw_rect.x - 5, draw_rect.top - 20))
