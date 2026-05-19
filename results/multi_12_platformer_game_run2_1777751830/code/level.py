import json
import os
import pygame
from platform import Platform
from coin import Coin
from enemy import Enemy
from settings import COLOR_SKY, COLOR_GREEN, SCREEN_WIDTH


class Level:
    """Loads and manages a level from a JSON file."""

    def __init__(self, level_path: str):
        self.platforms: list[Platform] = []
        self.coins: list[Coin] = []
        self.enemies: list[Enemy] = []
        self.player_start = (100, 500)
        self.goal_rect: pygame.Rect | None = None
        self.level_width = SCREEN_WIDTH
        self.name = "Level"

        self._load(level_path)
        self._calculate_level_width()

    def _load(self, level_path: str):
        """Load level data from a JSON file."""
        # Try multiple possible paths
        possible_paths = [
            os.path.join("levels", level_path),
            level_path,
            os.path.join(os.path.dirname(__file__), "levels", level_path),
        ]
        full_path = None
        for p in possible_paths:
            if os.path.exists(p):
                full_path = p
                break
        if full_path is None:
            print(f"Warning: Level file not found: {level_path}")
            # Create a default fallback level
            self._create_fallback()
            return

        with open(full_path, "r") as f:
            data = json.load(f)

        self.name = data.get("name", "Level")

        # Load platforms
        for p_data in data.get("platforms", []):
            color = tuple(p_data["color"]) if "color" in p_data else None
            platform = Platform(p_data["x"], p_data["y"], p_data["width"], p_data["height"], color)
            self.platforms.append(platform)

        # Load coins
        for c_data in data.get("coins", []):
            coin = Coin(c_data["x"], c_data["y"])
            self.coins.append(coin)

        # Load enemies
        for e_data in data.get("enemies", []):
            enemy = Enemy(e_data["x"], e_data["y"], e_data["min_x"], e_data["max_x"])
            self.enemies.append(enemy)

        # Player start position
        ps = data.get("player_start", [100, 500])
        self.player_start = (ps[0], ps[1])

        # Goal
        goal_data = data.get("goal", None)
        if goal_data:
            self.goal_rect = pygame.Rect(goal_data[0], goal_data[1], goal_data[2], goal_data[3])

        # Level width override (optional)
        if "level_width" in data:
            self.level_width = data["level_width"]

    def _create_fallback(self):
        """Create a simple fallback level if no JSON file is found."""
        # Ground
        self.platforms.append(Platform(0, 550, 800, 50))
        self.player_start = (100, 500)
        self.goal_rect = pygame.Rect(750, 510, 40, 40)
        self.name = "Fallback Level"

    def _calculate_level_width(self):
        """Determine the total width of the level based on platforms and goal."""
        max_x = SCREEN_WIDTH
        for p in self.platforms:
            if p.rect.right > max_x:
                max_x = p.rect.right
        if self.goal_rect and self.goal_rect.right > max_x:
            max_x = self.goal_rect.right
        # Add some padding
        self.level_width = max_x + 100

    def update(self):
        """Update all level entities."""
        for coin in self.coins:
            coin.update()
        for enemy in self.enemies:
            enemy.update()

    def draw(self, screen: pygame.Surface, camera_offset: int):
        """Draw all level entities relative to camera."""
        # Draw sky background
        screen.fill(COLOR_SKY)

        # Draw platforms
        for platform in self.platforms:
            platform.draw(screen, camera_offset)

        # Draw goal
        if self.goal_rect:
            adjusted_goal = self.goal_rect.move(-camera_offset, 0)
            # Pulsating goal
            pygame.draw.rect(screen, COLOR_GREEN, adjusted_goal)
            pygame.draw.rect(screen, (0, 100, 0), adjusted_goal, 3)
            # Draw "GOAL" text on it if it's wide enough
            if adjusted_goal.width > 40:
                font = pygame.font.Font(None, 16)
                goal_text = font.render("GOAL", True, (0, 0, 0))
                screen.blit(goal_text, (adjusted_goal.x + 4, adjusted_goal.y + 2))

        # Draw coins
        for coin in self.coins:
            coin.draw(screen, camera_offset)

        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(screen, camera_offset)

    def get_active_coins(self) -> list[Coin]:
        """Return list of coins that have not been collected yet."""
        return [c for c in self.coins if not c.collected]

    def get_platform_rects(self) -> list[pygame.Rect]:
        """Return list of platform rects for collision."""
        return [p.rect for p in self.platforms]
