import pygame
from settings import (
    PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_SPEED, PLAYER_JUMP_VELOCITY,
    PLAYER_GRAVITY, PLAYER_MAX_HEALTH, PLAYER_INVINCIBILITY_TIME,
    COLOR_BLUE, COLOR_WHITE, SCREEN_HEIGHT
)


class Player:
    """The player character with physics and collision."""

    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.coins_collected = 0
        self.invincibility_timer = 0
        self.facing_right = True

    def handle_input(self):
        """Handle keyboard input for movement."""
        keys = pygame.key.get_pressed()

        self.vel_x = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel_x = -PLAYER_SPEED
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel_x = PLAYER_SPEED
            self.facing_right = True

        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vel_y = PLAYER_JUMP_VELOCITY
            self.on_ground = False

    def update(self, platforms: list):
        """Apply gravity, move, and handle platform collisions."""
        # Apply gravity
        self.vel_y += PLAYER_GRAVITY
        # Terminal velocity
        if self.vel_y > 15:
            self.vel_y = 15

        # Move horizontally
        self.rect.x += self.vel_x
        self._collide_horizontal(platforms)

        # Move vertically
        self.rect.y += self.vel_y
        self._collide_vertical(platforms)

        # Fall off screen = death
        if self.rect.top > SCREEN_HEIGHT + 50:
            self.health = 0

        # Update invincibility
        if self.invincibility_timer > 0:
            self.invincibility_timer -= 1

    def _collide_horizontal(self, platforms: list):
        """Handle horizontal collisions with platforms."""
        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.vel_x > 0:  # Moving right
                    self.rect.right = platform.rect.left
                elif self.vel_x < 0:  # Moving left
                    self.rect.left = platform.rect.right

    def _collide_vertical(self, platforms: list):
        """Handle vertical collisions with platforms."""
        self.on_ground = False
        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.vel_y > 0:  # Falling down
                    self.rect.bottom = platform.rect.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0:  # Jumping up
                    self.rect.top = platform.rect.bottom
                    self.vel_y = 0

    def check_coin_collisions(self, coins: list) -> int:
        """Check collision with coins. Returns number of coins collected this frame."""
        collected = 0
        for coin in coins:
            if not coin.collected and self.rect.colliderect(coin.rect):
                coin.collected = True
                collected += 1
        self.coins_collected += collected
        return collected

    def check_enemy_collisions(self, enemies: list) -> bool:
        """Check collision with enemies. Returns True if damage was taken."""
        if self.invincibility_timer > 0:
            return False
        for enemy in enemies:
            if self.rect.colliderect(enemy.rect):
                self.health -= 1
                self.invincibility_timer = PLAYER_INVINCIBILITY_TIME
                # Knockback
                if self.rect.centerx < enemy.rect.centerx:
                    self.vel_x = -6
                    self.vel_y = -6
                else:
                    self.vel_x = 6
                    self.vel_y = -6
                self.on_ground = False
                return True
        return False

    def check_goal_collision(self, goal_rect: pygame.Rect) -> bool:
        """Check if player has reached the goal."""
        if goal_rect:
            return self.rect.colliderect(goal_rect)
        return False

    def is_dead(self) -> bool:
        return self.health <= 0

    def draw(self, screen: pygame.Surface, camera_offset: int):
        """Draw the player relative to the camera."""
        # Blink when invincible
        if self.invincibility_timer > 0 and (self.invincibility_timer // 5) % 2 == 0:
            return

        adjusted_rect = self.rect.move(-camera_offset, 0)

        # Body
        pygame.draw.rect(screen, COLOR_BLUE, adjusted_rect)
        # Border
        pygame.draw.rect(screen, (30, 60, 180), adjusted_rect, 2)

        # Eyes
        eye_y = adjusted_rect.y + 10
        if self.facing_right:
            eye_x = adjusted_rect.x + adjusted_rect.width - 10
        else:
            eye_x = adjusted_rect.x + 10
        pygame.draw.circle(screen, COLOR_WHITE, (eye_x, eye_y), 5)
        pygame.draw.circle(screen, (0, 0, 0), (eye_x, eye_y), 2)

        # Feet
        foot_y = adjusted_rect.y + adjusted_rect.height - 6
        pygame.draw.rect(screen, (30, 30, 80), (adjusted_rect.x + 4, foot_y, 8, 6))
        pygame.draw.rect(screen, (30, 30, 80), (adjusted_rect.x + adjusted_rect.width - 12, foot_y, 8, 6))
