"""
sprites.py – Game objects: Player, Enemy, Coin, Platform, Goal.
"""
import pygame
import math
from settings import *


class Platform(pygame.sprite.Sprite):
    """A solid rectangular platform the player can stand on."""

    def __init__(self, x, y, width, height):
        super().__init__()
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(topleft=(x, y))
        # Draw platform with a slight 3D edge
        self.image.fill(BROWN)
        # Top edge highlight
        pygame.draw.rect(self.image, (160, 110, 60), (0, 0, width, 4))
        # Bottom edge shadow
        pygame.draw.rect(self.image, DARK_BROWN, (0, height - 3, width, 3))
        # Grass-like top
        pygame.draw.rect(self.image, GREEN, (0, 0, width, 6))


class Goal(pygame.sprite.Sprite):
    """A goal flag the player reaches to complete the level."""

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((GOAL_WIDTH, GOAL_HEIGHT), pygame.SRCALPHA)
        self.rect = self.image.get_rect(bottomleft=(x, y))
        # Draw a flag
        # Pole
        pygame.draw.rect(self.image, DARK_GRAY, (4, 0, 4, GOAL_HEIGHT))
        # Flag
        flag_points = [(8, 4), (GOAL_WIDTH - 2, 12), (8, 24)]
        pygame.draw.polygon(self.image, GOLD, flag_points)
        # Orb on top
        pygame.draw.circle(self.image, YELLOW, (6, 6), 5)

        # Pulsing animation
        self.anim_counter = 0

    def update(self, *args, **kwargs):
        self.anim_counter += 1
        # Subtle color shift
        if self.anim_counter % 30 < 15:
            self.image.fill((0, 0, 0, 0))
            pygame.draw.rect(self.image, DARK_GRAY, (4, 0, 4, GOAL_HEIGHT))
            flag_points = [(8, 4), (GOAL_WIDTH - 2, 12), (8, 24)]
            pygame.draw.polygon(self.image, GOLD, flag_points)
            pygame.draw.circle(self.image, YELLOW, (6, 6), 5)


class Coin(pygame.sprite.Sprite):
    """A collectible coin that the player picks up on contact."""

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((COIN_RADIUS * 2 + 4, COIN_RADIUS * 2 + 4),
                                    pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.anim_counter = 0
        self._draw_coin(COIN_RADIUS * 2)

    def _draw_coin(self, width):
        self.image.fill((0, 0, 0, 0))
        cx = self.image.get_width() // 2
        cy = self.image.get_height() // 2
        pygame.draw.circle(self.image, GOLD, (cx, cy), COIN_RADIUS)
        pygame.draw.circle(self.image, YELLOW, (cx, cy), COIN_RADIUS - 3)
        pygame.draw.circle(self.image, GOLD, (cx, cy), COIN_RADIUS - 5)
        # Shine highlight
        pygame.draw.circle(self.image, WHITE, (cx - 3, cy - 4), 3)

    def update(self, *args, **kwargs):
        self.anim_counter += 1
        scale = 1.0 + 0.1 * math.sin(self.anim_counter * 0.1)
        w = int((COIN_RADIUS * 2) * scale)
        self._draw_coin(w)


class Enemy(pygame.sprite.Sprite):
    """An enemy that patrols left/right on a platform."""

    def __init__(self, x, y, patrol_left, patrol_right):
        super().__init__()
        self.image = pygame.Surface((ENEMY_WIDTH, ENEMY_HEIGHT), pygame.SRCALPHA)
        self.rect = self.image.get_rect(bottomleft=(x, y))
        self.patrol_left = patrol_left
        self.patrol_right = patrol_right
        self.speed = ENEMY_SPEED
        self.direction = 1  # 1 = right, -1 = left
        self.anim_timer = 0
        self._draw_enemy()

    def _draw_enemy(self):
        self.image.fill((0, 0, 0, 0))
        # Body
        body_rect = pygame.Rect(2, 6, ENEMY_WIDTH - 4, ENEMY_HEIGHT - 10)
        pygame.draw.rect(self.image, RED, body_rect, border_radius=4)
        # Eyes
        eye_y = 12
        if self.direction == 1:
            pygame.draw.circle(self.image, WHITE, (ENEMY_WIDTH - 10, eye_y), 5)
            pygame.draw.circle(self.image, BLACK, (ENEMY_WIDTH - 8, eye_y), 3)
            pygame.draw.circle(self.image, WHITE, (ENEMY_WIDTH - 18, eye_y), 5)
            pygame.draw.circle(self.image, BLACK, (ENEMY_WIDTH - 16, eye_y), 3)
        else:
            pygame.draw.circle(self.image, WHITE, (10, eye_y), 5)
            pygame.draw.circle(self.image, BLACK, (8, eye_y), 3)
            pygame.draw.circle(self.image, WHITE, (18, eye_y), 5)
            pygame.draw.circle(self.image, BLACK, (16, eye_y), 3)
        # Feet
        pygame.draw.rect(self.image, RED, (2, ENEMY_HEIGHT - 6, 8, 6))
        pygame.draw.rect(self.image, RED, (ENEMY_WIDTH - 10, ENEMY_HEIGHT - 6, 8, 6))
        # Horns
        pygame.draw.polygon(self.image, RED, [(6, 4), (10, 0), (12, 4)])
        pygame.draw.polygon(self.image, RED, [(ENEMY_WIDTH - 6, 4),
                                               (ENEMY_WIDTH - 10, 0),
                                               (ENEMY_WIDTH - 12, 4)])

    def update(self, *args, **kwargs):
        self.anim_timer += 1

        # Move
        self.rect.x += self.speed * self.direction

        # Patrol bounds
        if self.rect.left <= self.patrol_left:
            self.rect.left = self.patrol_left
            self.direction = 1
        elif self.rect.right >= self.patrol_right:
            self.rect.right = self.patrol_right
            self.direction = -1

        # Redraw for eye direction
        if self.anim_timer % 6 == 0:
            self._draw_enemy()


class Player(pygame.sprite.Sprite):
    """The player character."""

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
        self.rect = self.image.get_rect(bottomleft=(x, y))
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = False
        self.facing_right = True
        self.health = PLAYER_MAX_HEALTH
        self.invulnerable = 0  # frames of invulnerability remaining
        self.anim_timer = 0
        self._draw_player()

    def _draw_player(self):
        self.image.fill((0, 0, 0, 0))
        # Body
        body_color = BLUE if self.invulnerable <= 0 or (self.invulnerable // 4) % 2 == 0 else WHITE
        pygame.draw.rect(self.image, body_color,
                         (2, 10, PLAYER_WIDTH - 4, PLAYER_HEIGHT - 14),
                         border_radius=4)
        # Head
        head_color = BLUE if self.invulnerable <= 0 or (self.invulnerable // 4) % 2 == 0 else WHITE
        pygame.draw.rect(self.image, head_color,
                         (6, 0, PLAYER_WIDTH - 12, 14),
                         border_radius=3)
        # Eyes
        eye_y = 4
        if self.facing_right:
            pygame.draw.circle(self.image, WHITE, (PLAYER_WIDTH - 10, eye_y), 4)
            pygame.draw.circle(self.image, BLACK, (PLAYER_WIDTH - 8, eye_y), 2)
        else:
            pygame.draw.circle(self.image, WHITE, (10, eye_y), 4)
            pygame.draw.circle(self.image, BLACK, (8, eye_y), 2)
        # Arms
        arm_color = body_color
        if self.on_ground:
            pygame.draw.rect(self.image, arm_color, (0, 14, 4, 14))
            pygame.draw.rect(self.image, arm_color, (PLAYER_WIDTH - 4, 14, 4, 14))
        else:
            pygame.draw.rect(self.image, arm_color, (0, 10, 4, 10))
            pygame.draw.rect(self.image, arm_color, (PLAYER_WIDTH - 4, 10, 4, 10))
        # Legs
        leg_offset = 0
        if not self.on_ground:
            leg_offset = 3
        pygame.draw.rect(self.image, body_color,
                         (4, PLAYER_HEIGHT - 10, 8, 10 - leg_offset))
        pygame.draw.rect(self.image, body_color,
                         (PLAYER_WIDTH - 12, PLAYER_HEIGHT - 10, 8, 10 - leg_offset))

    def update(self, *args, **kwargs):
        self.anim_timer += 1
        if self.invulnerable > 0:
            self.invulnerable -= 1
        self._draw_player()

    def take_damage(self, amount=1):
        """Reduce health if not invulnerable. Returns True if damage was taken."""
        if self.invulnerable > 0:
            return False
        self.health -= amount
        self.invulnerable = INVULNERABILITY_FRAMES
        self.vel_y = -8  # knockback upward
        return True

    def is_alive(self):
        return self.health > 0
