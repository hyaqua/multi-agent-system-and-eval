"""
Enemy class: patrols back and forth on platforms.
"""
import pygame
from settings import ENEMY_WIDTH, ENEMY_HEIGHT, ENEMY_COLOR, ENEMY_SPEED, ENEMY_PATROL_RANGE


class Enemy:
    def __init__(self, x, y):
        # y is the top of the platform; enemies stand on it
        self.rect = pygame.Rect(x, y - ENEMY_HEIGHT, ENEMY_WIDTH, ENEMY_HEIGHT)
        self.spawn_x = x
        self.vx = ENEMY_SPEED
        self.patrol_left = x - ENEMY_PATROL_RANGE
        self.patrol_right = x + ENEMY_PATROL_RANGE

    def update(self):
        self.rect.x += self.vx
        if self.rect.x <= self.patrol_left or self.rect.x >= self.patrol_right:
            self.vx = -self.vx

    def draw(self, screen, camera_x):
        draw_rect = self.rect.move(-camera_x, 0)
        pygame.draw.rect(screen, ENEMY_COLOR, draw_rect)
        # Eyes
        eye_y = draw_rect.top + 10
        left_eye = draw_rect.centerx - 6
        right_eye = draw_rect.centerx + 6
        pygame.draw.circle(screen, (255, 255, 255), (left_eye, eye_y), 5)
        pygame.draw.circle(screen, (255, 255, 255), (right_eye, eye_y), 5)
        pygame.draw.circle(screen, (0, 0, 0), (left_eye, eye_y), 2)
        pygame.draw.circle(screen, (0, 0, 0), (right_eye, eye_y), 2)
        # Angry brows
        brow_y = eye_y - 6
        pygame.draw.line(screen, (0, 0, 0),
                         (left_eye - 4, brow_y), (left_eye + 4, brow_y), 2)
        pygame.draw.line(screen, (0, 0, 0),
                         (right_eye - 4, brow_y), (right_eye + 4, brow_y), 2)
