"""
Platformer Game - Enemy module
Patrol behavior and collision damage.
"""
import pygame
from constants import *


class Enemy:
    def __init__(self, x, y, patrol_left=None, patrol_right=None):
        self.rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        self.velocity = ENEMY_SPEED
        self.start_x = x

        # Patrol bounds
        if patrol_left is not None:
            self.patrol_left = patrol_left
        else:
            self.patrol_left = x - ENEMY_PATROL_DISTANCE

        if patrol_right is not None:
            self.patrol_right = patrol_right
        else:
            self.patrol_right = x + ENEMY_PATROL_DISTANCE

        self.facing_right = True
        self.animation_timer = 0

    def update(self, platforms):
        """Update enemy position and handle patrol logic."""
        # Move horizontally
        self.rect.x += self.velocity

        # Check patrol bounds
        if self.rect.x <= self.patrol_left:
            self.rect.x = self.patrol_left
            self.velocity = abs(self.velocity)  # Go right
            self.facing_right = True
        elif self.rect.right >= self.patrol_right:
            self.rect.right = self.patrol_right
            self.velocity = -abs(self.velocity)  # Go left
            self.facing_right = False

        # Check platform edges: reverse if about to walk off
        on_platform = False
        for platform in platforms:
            # Check if enemy's feet are on this platform
            foot_rect = pygame.Rect(
                self.rect.x + 5,
                self.rect.bottom,
                self.rect.width - 10,
                4
            )
            if foot_rect.colliderect(platform.rect):
                on_platform = True
                break

        # If moving and not on any platform, reverse
        if not on_platform:
            # Check forward edge
            check_x = self.rect.x + (self.rect.width if self.velocity > 0 else -5)
            check_rect = pygame.Rect(check_x, self.rect.bottom, 5, 8)
            edge_on_platform = False
            for platform in platforms:
                if check_rect.colliderect(platform.rect):
                    edge_on_platform = True
                    break
            if not edge_on_platform:
                self.velocity = -self.velocity
                self.facing_right = not self.facing_right

        self.animation_timer += 1

    def draw(self, screen, camera_x):
        """Draw the enemy with camera offset."""
        draw_rect = pygame.Rect(
            self.rect.x - camera_x,
            self.rect.y,
            self.rect.width,
            self.rect.height
        )

        # Draw enemy body
        pygame.draw.rect(screen, ENEMY_COLOR, draw_rect)
        pygame.draw.rect(screen, DARK_RED, draw_rect, 2)

        # Draw "eyes"
        eye_y = draw_rect.y + 8
        if self.facing_right:
            eye_x = draw_rect.x + draw_rect.width - 8
        else:
            eye_x = draw_rect.x + 8
        pygame.draw.circle(screen, WHITE, (eye_x, eye_y), 4)
        pygame.draw.circle(screen, BLACK, (eye_x, eye_y), 2)

        # Draw spike/angry features
        spike_y = draw_rect.y + draw_rect.height - 4
        spike_offset = (self.animation_timer // 20) % 2  # subtle animation
        for i in range(3):
            sx = draw_rect.x + 6 + i * 8 + spike_offset
            pygame.draw.rect(screen, DARK_RED, (sx, spike_y, 4, 4))
