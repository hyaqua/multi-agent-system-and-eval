"""
Player class: movement, jumping, gravity, health, collision.
"""
import pygame
from settings import (
    PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_COLOR,
    PLAYER_SPEED, PLAYER_JUMP_POWER, GRAVITY,
    PLAYER_MAX_HEALTH,
)


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.health = PLAYER_MAX_HEALTH
        self.facing_right = True
        self.invincible_timer = 0  # brief invincibility after damage

    def update(self, keys, platforms, enemies, coins):
        # Horizontal movement
        self.vx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -PLAYER_SPEED
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = PLAYER_SPEED
            self.facing_right = True

        # Jump
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground:
            self.vy = PLAYER_JUMP_POWER
            self.on_ground = False

        # Gravity
        self.vy += GRAVITY
        if self.vy > 15:
            self.vy = 15  # terminal velocity

        # Move X
        self.rect.x += self.vx
        self._resolve_x_collisions(platforms)

        # Move Y
        self.rect.y += self.vy
        self._resolve_y_collisions(platforms)

        # Decrement invincibility timer
        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # Check enemy collisions
        for enemy in enemies:
            if self.rect.colliderect(enemy.rect) and self.invincible_timer == 0:
                self.take_damage()

        # Check coin collisions
        collected = 0
        for coin in coins[:]:
            if self.rect.colliderect(coin.rect):
                coins.remove(coin)
                collected += 1
        return collected

    def _resolve_x_collisions(self, platforms):
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vx > 0:  # moving right
                    self.rect.right = plat.rect.left
                elif self.vx < 0:  # moving left
                    self.rect.left = plat.rect.right

    def _resolve_y_collisions(self, platforms):
        self.on_ground = False
        for plat in platforms:
            if self.rect.colliderect(plat.rect):
                if self.vy > 0:  # falling down
                    self.rect.bottom = plat.rect.top
                    self.vy = 0
                    self.on_ground = True
                elif self.vy < 0:  # jumping up
                    self.rect.top = plat.rect.bottom
                    self.vy = 0

    def take_damage(self):
        self.health -= 1
        self.invincible_timer = 60  # 1 second at 60fps
        # Knockback
        if self.facing_right:
            self.vx = -8
        else:
            self.vx = 8
        self.vy = -6

    def is_alive(self):
        return self.health > 0

    def draw(self, screen, camera_x):
        draw_rect = self.rect.move(-camera_x, 0)
        # Flash when invincible
        if self.invincible_timer > 0 and (self.invincible_timer // 4) % 2 == 0:
            # Skip drawing every other flash
            pass
        else:
            pygame.draw.rect(screen, PLAYER_COLOR, draw_rect)
            # Eyes
            eye_x = draw_rect.centerx + (8 if self.facing_right else -8)
            pygame.draw.circle(screen, (255, 255, 255), (eye_x, draw_rect.top + 12), 4)
            pygame.draw.circle(screen, (0, 0, 0), (eye_x, draw_rect.top + 12), 2)
