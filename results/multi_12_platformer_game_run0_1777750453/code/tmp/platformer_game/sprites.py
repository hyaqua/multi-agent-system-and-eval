# sprites.py - Player, Enemy, Coin, Platform, Goal sprite classes

import pygame
from settings import (
    PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_SPEED, JUMP_STRENGTH, GRAVITY,
    MAX_HEALTH, INVINCIBILITY_TIME, ENEMY_WIDTH, ENEMY_HEIGHT, ENEMY_SPEED,
    COIN_RADIUS, GREEN, RED, YELLOW, BLUE, ORANGE, WHITE, BLACK,
    BROWN, PLATFORM_COLOR, GOAL_COLOR
)


class Platform(pygame.sprite.Sprite):
    """A solid platform the player can stand on."""

    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(PLATFORM_COLOR)
        # Add a subtle border
        pygame.draw.rect(self.image, (0, 100, 0), (0, 0, width, height), 2)
        self.rect = self.image.get_rect(topleft=(x, y))


class Coin(pygame.sprite.Sprite):
    """A collectible coin."""

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((COIN_RADIUS * 2, COIN_RADIUS * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, YELLOW, (COIN_RADIUS, COIN_RADIUS), COIN_RADIUS)
        pygame.draw.circle(self.image, ORANGE, (COIN_RADIUS, COIN_RADIUS), COIN_RADIUS - 2)
        self.rect = self.image.get_rect(center=(x, y))
        self.anim_timer = 0


class Enemy(pygame.sprite.Sprite):
    """A patrolling enemy that damages the player on contact."""

    def __init__(self, x, y, patrol_range=None):
        super().__init__()
        self.image = pygame.Surface((ENEMY_WIDTH, ENEMY_HEIGHT))
        self.image.fill(RED)
        # Draw angry eyes
        pygame.draw.circle(self.image, WHITE, (8, 10), 5)
        pygame.draw.circle(self.image, WHITE, (22, 10), 5)
        pygame.draw.circle(self.image, BLACK, (8, 10), 2)
        pygame.draw.circle(self.image, BLACK, (22, 10), 2)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.pos = pygame.math.Vector2(x, y)
        self.vel = pygame.math.Vector2(ENEMY_SPEED, 0)

        self.patrol_range = patrol_range
        self.patrol_left = None
        self.patrol_right = None
        if patrol_range:
            self.patrol_left = min(patrol_range)
            self.patrol_right = max(patrol_range)

    def update(self, platforms):
        """Patrol left/right, reversing at patrol range boundaries."""
        self.pos.x += self.vel.x
        self.rect.x = int(self.pos.x)

        # Reverse at patrol range edges
        if self.patrol_left is not None and self.patrol_right is not None:
            if self.rect.left <= self.patrol_left:
                self.rect.left = self.patrol_left
                self.pos.x = self.rect.x
                self.vel.x = abs(self.vel.x)
            elif self.rect.right >= self.patrol_right:
                self.rect.right = self.patrol_right
                self.pos.x = self.rect.x
                self.vel.x = -abs(self.vel.x)

        # Also reverse at platform edges — raycast down to detect edge
        self._check_platform_edge(platforms)

        # Apply gravity
        self.vel.y = 5  # constant downward pull
        self.pos.y += self.vel.y
        self.rect.y = int(self.pos.y)
        self._check_collision_y(platforms)

    def _check_platform_edge(self, platforms):
        """Reverse direction if about to walk off a platform edge."""
        # Check if there's ground ahead in the direction of movement
        check_x = self.rect.right + 5 if self.vel.x > 0 else self.rect.left - 5
        check_y = self.rect.bottom + 5
        on_edge = True
        for plat in platforms:
            if plat.rect.left <= check_x <= plat.rect.right:
                if plat.rect.top <= check_y <= plat.rect.bottom + 10:
                    on_edge = False
                    break
        # Also check if there's a platform directly below
        for plat in platforms:
            if plat.rect.left <= self.rect.centerx <= plat.rect.right:
                if 0 <= plat.rect.top - self.rect.bottom <= 10:
                    on_edge = False
                    break

        if on_edge:
            self.vel.x = -self.vel.x

    def _check_collision_y(self, platforms):
        """Resolve vertical collisions with platforms."""
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vel.y > 0:  # falling
                    self.rect.bottom = plat.rect.top
                    self.pos.y = self.rect.y
                    self.vel.y = 0
                elif self.vel.y < 0:  # rising
                    self.rect.top = plat.rect.bottom
                    self.pos.y = self.rect.y
                    self.vel.y = 0


class Goal(pygame.sprite.Sprite):
    """The goal/exit that completes the level when touched."""

    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.image.fill(GOAL_COLOR)
        # Draw a star or flag pattern
        pygame.draw.rect(self.image, (200, 150, 0), (0, 0, width, height), 3)
        # Simple arrow shape
        cx, cy = width // 2, height // 2
        pygame.draw.polygon(self.image, BLACK, [
            (cx - 15, cy - 10),
            (cx + 15, cy),
            (cx - 15, cy + 10),
        ])
        self.rect = self.image.get_rect(topleft=(x, y))


class Player(pygame.sprite.Sprite):
    """Player character with movement, jumping, gravity, and health."""

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT))
        self.image.fill(BLUE)
        # Draw a simple face
        pygame.draw.circle(self.image, WHITE, (PLAYER_WIDTH // 2, 10), 6)
        pygame.draw.rect(self.image, (30, 30, 200), (8, 18, 14, 10))

        self.rect = self.image.get_rect(topleft=(x, y))
        self.pos = pygame.math.Vector2(x, y)
        self.vel = pygame.math.Vector2(0, 0)

        self.health = MAX_HEALTH
        self.coins = 0
        self.on_ground = False
        self.invincibility_timer = 0
        self.facing_right = True

    def update(self, platforms, enemies, coins, keys):
        """Update player state each frame."""
        # --- Horizontal movement ---
        dx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx = -PLAYER_SPEED
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx = PLAYER_SPEED
            self.facing_right = True

        self.vel.x = dx

        # --- Jumping ---
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vel.y = JUMP_STRENGTH
            self.on_ground = False

        # --- Apply gravity ---
        self.vel.y += GRAVITY
        if self.vel.y > 15:
            self.vel.y = 15  # terminal velocity

        # --- Move X ---
        self.pos.x += self.vel.x
        self.rect.x = int(self.pos.x)
        self._check_collision_x(platforms)

        # --- Move Y ---
        self.pos.y += self.vel.y
        self.rect.y = int(self.pos.y)
        self.on_ground = False
        self._check_collision_y(platforms)

        # --- Update invincibility ---
        if self.invincibility_timer > 0:
            self.invincibility_timer -= 1

        # --- Coin collision ---
        collected = pygame.sprite.spritecollide(self, coins, True)
        self.coins += len(collected)

        # --- Enemy collision (damage) ---
        if self.invincibility_timer == 0:
            hits = pygame.sprite.spritecollide(self, enemies, False)
            if hits:
                self.health -= 1
                self.invincibility_timer = INVINCIBILITY_TIME
                # Knockback
                for enemy in hits:
                    if self.rect.centerx < enemy.rect.centerx:
                        self.vel.x = -6
                    else:
                        self.vel.x = 6
                    self.vel.y = -4

    def _check_collision_x(self, platforms):
        """Resolve horizontal collisions with platforms."""
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vel.x > 0:  # moving right
                    self.rect.right = plat.rect.left
                elif self.vel.x < 0:  # moving left
                    self.rect.left = plat.rect.right
                self.pos.x = self.rect.x
                self.vel.x = 0

    def _check_collision_y(self, platforms):
        """Resolve vertical collisions with platforms."""
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vel.y > 0:  # falling
                    self.rect.bottom = plat.rect.top
                    self.on_ground = True
                elif self.vel.y < 0:  # rising
                    self.rect.top = plat.rect.bottom
                self.pos.y = self.rect.y
                self.vel.y = 0
