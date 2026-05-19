"""
Platformer Game - Player module
Handles player movement, jumping, gravity, health, and collision.
"""
import pygame
from constants import *


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.velocity = pygame.Vector2(0, 0)
        self.on_ground = False
        self.health = PLAYER_MAX_HEALTH
        self.alive = True
        self.invincible_timer = 0
        self.facing_right = True

    def handle_input(self, keys):
        """Handle horizontal movement input."""
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.velocity.x -= PLAYER_ACCELERATION
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.velocity.x += PLAYER_ACCELERATION
            self.facing_right = True

    def apply_physics(self):
        """Apply gravity and friction."""
        # Apply gravity
        self.velocity.y += GRAVITY
        if self.velocity.y > MAX_FALL_SPEED:
            self.velocity.y = MAX_FALL_SPEED

        # Apply friction
        if self.on_ground:
            self.velocity.x *= (1 - PLAYER_FRICTION)
        else:
            self.velocity.x *= (1 - PLAYER_FRICTION * 0.5)

        # Clamp horizontal speed
        if self.velocity.x > PLAYER_MAX_SPEED:
            self.velocity.x = PLAYER_MAX_SPEED
        elif self.velocity.x < -PLAYER_MAX_SPEED:
            self.velocity.x = -PLAYER_MAX_SPEED

        # Stop very small velocities
        if abs(self.velocity.x) < 0.1:
            self.velocity.x = 0

    def jump(self):
        """Make the player jump if on ground."""
        if self.on_ground:
            self.velocity.y = JUMP_STRENGTH
            self.on_ground = False

    def move_x(self, platforms):
        """Move horizontally and resolve collisions."""
        self.rect.x += self.velocity.x

        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.velocity.x > 0:
                    # Moving right; hit left side of platform
                    self.rect.right = platform.rect.left
                elif self.velocity.x < 0:
                    # Moving left; hit right side of platform
                    self.rect.left = platform.rect.right
                self.velocity.x = 0

    def move_y(self, platforms):
        """Move vertically and resolve collisions."""
        self.rect.y += self.velocity.y

        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.velocity.y > 0:
                    # Falling down; land on top of platform
                    self.rect.bottom = platform.rect.top
                    self.velocity.y = 0
                    self.on_ground = True
                elif self.velocity.y < 0:
                    # Moving up; hit bottom of platform
                    self.rect.top = platform.rect.bottom
                    self.velocity.y = 0

    def update(self, platforms):
        """Update player state for one frame."""
        # Decrement invincibility timer
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # Apply physics
        self.apply_physics()

        # Move and resolve collisions
        self.on_ground = False
        self.move_x(platforms)
        self.move_y(platforms)

        # Kill player if they fall off the map
        if self.rect.top > HEIGHT + 100:
            self.health = 0
            self.alive = False

    def take_damage(self):
        """Apply damage to player if not invincible."""
        if self.invincible_timer <= 0:
            self.health -= 1
            self.invincible_timer = DAMAGE_COOLDOWN
            # Apply knockback
            knockback_dir = -1 if self.facing_right else 1
            self.velocity.x = knockback_dir * KNOCKBACK_X
            self.velocity.y = KNOCKBACK_Y
            self.on_ground = False
            if self.health <= 0:
                self.health = 0
                self.alive = False

    def is_invincible(self):
        """Return True if player is currently invincible."""
        return self.invincible_timer > 0

    def draw(self, screen, camera_x):
        """Draw the player on the screen."""
        draw_rect = pygame.Rect(
            self.rect.x - camera_x,
            self.rect.y,
            self.rect.width,
            self.rect.height
        )

        # Blink when invincible
        if self.is_invincible() and (self.invincible_timer // 5) % 2 == 0:
            color = (100, 100, 255)  # Lighter blue when blinking
        else:
            color = PLAYER_COLOR

        pygame.draw.rect(screen, color, draw_rect)
        # Draw border
        pygame.draw.rect(screen, WHITE, draw_rect, 2)

        # Draw eyes to show facing direction
        eye_y = draw_rect.y + 10
        if self.facing_right:
            eye_x = draw_rect.x + draw_rect.width - 8
        else:
            eye_x = draw_rect.x + 8
        pygame.draw.circle(screen, WHITE, (eye_x, eye_y), 3)
        pygame.draw.circle(screen, BLACK, (eye_x, eye_y), 1.5)

    def reset(self, x, y):
        """Reset player to starting position with full health."""
        self.rect.x = x
        self.rect.y = y
        self.velocity = pygame.Vector2(0, 0)
        self.on_ground = False
        self.health = PLAYER_MAX_HEALTH
        self.alive = True
        self.invincible_timer = 0
