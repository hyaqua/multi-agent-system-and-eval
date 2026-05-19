import pygame
from settings import ENEMY_WIDTH, ENEMY_HEIGHT, ENEMY_SPEED, COLOR_RED, COLOR_DARK_RED


class Enemy:
    """An enemy that patrols back and forth horizontally."""

    def __init__(self, x: int, y: int, min_x: int, max_x: int):
        self.rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        self.min_x = min_x
        self.max_x = max_x
        self.speed = ENEMY_SPEED
        self.direction = 1  # 1 = right, -1 = left

    def update(self):
        """Move the enemy back and forth within its patrol range."""
        self.rect.x += self.speed * self.direction

        # Reverse direction at boundaries
        if self.rect.right >= self.max_x:
            self.rect.right = self.max_x
            self.direction = -1
        elif self.rect.left <= self.min_x:
            self.rect.left = self.min_x
            self.direction = 1

    def draw(self, screen: pygame.Surface, camera_offset: int):
        """Draw the enemy relative to the camera."""
        adjusted_rect = self.rect.move(-camera_offset, 0)
        # Main body
        pygame.draw.rect(screen, COLOR_RED, adjusted_rect)
        # Eyes
        eye_y = adjusted_rect.y + 8
        if self.direction > 0:
            eye_x1 = adjusted_rect.x + adjusted_rect.width - 10
            eye_x2 = adjusted_rect.x + adjusted_rect.width - 22
        else:
            eye_x1 = adjusted_rect.x + 10
            eye_x2 = adjusted_rect.x + 22
        pygame.draw.circle(screen, (255, 255, 255), (eye_x1, eye_y), 5)
        pygame.draw.circle(screen, (0, 0, 0), (eye_x1, eye_y), 2)
        pygame.draw.circle(screen, (255, 255, 255), (eye_x2, eye_y), 5)
        pygame.draw.circle(screen, (0, 0, 0), (eye_x2, eye_y), 2)
        # Feet
        foot_y = adjusted_rect.y + adjusted_rect.height - 4
        pygame.draw.rect(screen, COLOR_DARK_RED, (adjusted_rect.x + 4, foot_y, 8, 4))
        pygame.draw.rect(screen, COLOR_DARK_RED, (adjusted_rect.x + adjusted_rect.width - 12, foot_y, 8, 4))
