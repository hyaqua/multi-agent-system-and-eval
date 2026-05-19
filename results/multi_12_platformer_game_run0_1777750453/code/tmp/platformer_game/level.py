# level.py - Level loading and Level class

import json
import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
from sprites import Platform, Coin, Enemy, Goal


class Level:
    """Holds all sprite groups and data for a level."""

    def __init__(self):
        self.platforms = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.goals = pygame.sprite.Group()
        self.all_sprites = pygame.sprite.Group()
        self.player_start = (0, 0)
        self.world_width = 800
        self.world_height = 600
        self.name = ""


class LevelLoader:
    """Loads level data from JSON files."""

    @staticmethod
    def load(level_path):
        """Load a level from a JSON file, return a Level object."""
        with open(level_path, 'r') as f:
            data = json.load(f)

        level = Level()
        level.name = data.get("name", "Unknown")

        # Create platforms
        for plat_data in data.get("platforms", []):
            x, y, w, h = plat_data
            platform = Platform(x, y, w, h)
            level.platforms.add(platform)
            level.all_sprites.add(platform)

        # Create coins
        for coin_data in data.get("coins", []):
            x, y = coin_data
            coin = Coin(x, y)
            level.coins.add(coin)
            level.all_sprites.add(coin)

        # Create enemies
        for enemy_data in data.get("enemies", []):
            x, y = enemy_data[0], enemy_data[1]
            patrol_range = None
            if len(enemy_data) >= 4:
                patrol_range = (enemy_data[2], enemy_data[3])
            enemy = Enemy(x, y, patrol_range)
            level.enemies.add(enemy)
            level.all_sprites.add(enemy)

        # Create goal
        goal_data = data.get("goal", [])
        if goal_data:
            gx, gy, gw, gh = goal_data
            goal = Goal(gx, gy, gw, gh)
            level.goals.add(goal)
            level.all_sprites.add(goal)

        # Player start
        player_start = data.get("player_start", [100, 400])
        level.player_start = (player_start[0], player_start[1])

        # Calculate world bounds
        all_x = [p.rect.right for p in level.platforms]
        all_x.append(SCREEN_WIDTH)
        if goal_data:
            all_x.append(gx + gw)
        level.world_width = max(all_x)

        all_y = [p.rect.bottom for p in level.platforms]
        all_y.append(SCREEN_HEIGHT)
        if goal_data:
            all_y.append(gy + gh)
        level.world_height = max(all_y)

        return level
