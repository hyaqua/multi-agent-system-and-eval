"""
Platformer Game - Level loader and container.
Reads level data from JSON and creates game objects.
"""
import json
import os
from platform import Platform
from enemy import Enemy
from coin import Coin


class Level:
    def __init__(self):
        self.platforms = []
        self.coins = []
        self.enemies = []
        self.player_start = (100, 400)
        self.goal_rect = None
        self.width = 1200
        self.level_number = 1

    def load(self, filepath):
        """Load level data from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.platforms.clear()
        self.coins.clear()
        self.enemies.clear()

        self.width = data.get("width", 2400)
        self.player_start = tuple(data.get("player_start", [100, 400]))

        # Load platforms
        for p_data in data.get("platforms", []):
            plat = Platform(
                p_data[0], p_data[1],
                p_data[2], p_data[3]
            )
            self.platforms.append(plat)

        # Load coins
        for c_data in data.get("coins", []):
            coin = Coin(c_data[0], c_data[1])
            self.coins.append(coin)

        # Load enemies
        for e_data in data.get("enemies", []):
            x, y = e_data[0], e_data[1]
            patrol_left = e_data[2] if len(e_data) > 2 else None
            patrol_right = e_data[3] if len(e_data) > 3 else None
            enemy = Enemy(x, y, patrol_left, patrol_right)
            self.enemies.append(enemy)

        # Load goal
        goal_data = data.get("goal", None)
        if goal_data:
            import pygame
            self.goal_rect = pygame.Rect(
                goal_data[0], goal_data[1],
                goal_data[2], goal_data[3]
            )
        else:
            self.goal_rect = None

    def update(self):
        """Update all level objects."""
        for coin in self.coins:
            if not coin.collected:
                coin.update()
        for enemy in self.enemies:
            enemy.update(self.platforms)

    def draw(self, screen, camera_x):
        """Draw all level objects with camera offset."""
        # Draw platforms
        for platform in self.platforms:
            platform.draw(screen, camera_x)

        # Draw coins
        for coin in self.coins:
            coin.draw(screen, camera_x)

        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(screen, camera_x)

        # Draw goal
        if self.goal_rect:
            import pygame
            from constants import GOAL_COLOR, GOAL_OUTLINE_COLOR, WHITE
            draw_rect = pygame.Rect(
                self.goal_rect.x - camera_x,
                self.goal_rect.y,
                self.goal_rect.width,
                self.goal_rect.height
            )
            # Pulsating effect
            import math
            pulse = int(20 * abs(math.sin(pygame.time.get_ticks() * 0.003)))
            glow_rect = draw_rect.inflate(pulse, pulse)
            pygame.draw.rect(screen, (255, 255, 150, 100), glow_rect, 3)

            pygame.draw.rect(screen, GOAL_COLOR, draw_rect)
            pygame.draw.rect(screen, GOAL_OUTLINE_COLOR, draw_rect, 3)

            # Draw flag/star
            center = draw_rect.center
            font = pygame.font.Font(None, 28)
            star_text = font.render("★", True, (200, 150, 0))
            star_rect = star_text.get_rect(center=center)
            screen.blit(star_text, star_rect)

    def check_coin_collisions(self, player_rect):
        """Check and collect coins, return number collected this frame."""
        collected = 0
        for coin in self.coins:
            if not coin.collected and player_rect.colliderect(coin.rect):
                coin.collected = True
                collected += 1
        return collected

    def check_enemy_collisions(self, player_rect):
        """Check if player touches any enemy."""
        for enemy in self.enemies:
            if player_rect.colliderect(enemy.rect):
                return True
        return False

    def check_goal_collision(self, player_rect):
        """Check if player reached the goal."""
        if self.goal_rect and player_rect.colliderect(self.goal_rect):
            return True
        return False

    def get_total_coins(self):
        """Return total number of coins in the level."""
        return len(self.coins)

    def get_collected_coins(self):
        """Return number of collected coins."""
        return sum(1 for c in self.coins if c.collected)
