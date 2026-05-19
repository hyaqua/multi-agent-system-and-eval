"""
Main game module: ties everything together, handles game loop, UI, and state.
"""
import pygame
import sys
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    SKY_COLOR, UI_TEXT_COLOR, HEALTH_COLOR, HEALTH_BG,
    GAME_OVER_BG, PLAYER_MAX_HEALTH,
)
from levels import LEVELS
from player import Player
from platform import Platform
from coin import Coin
from enemy import Enemy
from goal import Goal


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Platformer Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        self.current_level = 0
        self.score = 0
        self.camera_x = 0.0
        self.game_over = False
        self.won = False

        self._load_level(self.current_level)

    def _load_level(self, level_index):
        """Initialize all objects from level data."""
        if level_index >= len(LEVELS):
            self.won = True
            return

        data = LEVELS[level_index]
        self.player = Player(*data["player_start"])
        self.platforms = [Platform(x, y, w) for (x, y, w) in data["platforms"]]
        self.coins = [Coin(x, y) for (x, y) in data["coins"]]
        self.enemies = [Enemy(x, y) for (x, y) in data["enemies"]]
        self.goal = Goal(*data["goal"])
        self.level_name = data["name"]
        self.camera_x = 0.0

    def run(self):
        """Main game loop."""
        running = True
        while running:
            dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if self.game_over or self.won:
                        if event.key == pygame.K_r:
                            self._restart()
                        elif event.key == pygame.K_q:
                            running = False

            if not self.game_over and not self.won:
                self._update()
            self._draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _update(self):
        keys = pygame.key.get_pressed()

        # Update player
        collected = self.player.update(keys, self.platforms, self.enemies, self.coins)
        self.score += collected

        # Update enemies
        for enemy in self.enemies:
            enemy.update()

        # Update coins (animation)
        for coin in self.coins:
            coin.update()

        # Update camera to follow player
        target_x = self.player.rect.centerx - SCREEN_WIDTH // 2
        self.camera_x += (target_x - self.camera_x) * 0.1
        if self.camera_x < 0:
            self.camera_x = 0

        # Check goal
        if self.player.rect.colliderect(self.goal.rect):
            self.current_level += 1
            if self.current_level >= len(LEVELS):
                self.won = True
            else:
                self._load_level(self.current_level)

        # Check death
        if not self.player.is_alive():
            self.game_over = True
        # Check fall off bottom
        if self.player.rect.top > SCREEN_HEIGHT + 100:
            self.player.health = 0
            self.game_over = True

    def _draw(self):
        self.screen.fill(SKY_COLOR)

        if self.won:
            self._draw_win_screen()
            return

        if self.game_over:
            self._draw_game_over_screen()
            return

        # Draw platforms
        for plat in self.platforms:
            plat.draw(self.screen, self.camera_x)

        # Draw goal
        self.goal.draw(self.screen, self.camera_x)

        # Draw coins
        for coin in self.coins:
            coin.draw(self.screen, self.camera_x)

        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(self.screen, self.camera_x)

        # Draw player
        self.player.draw(self.screen, self.camera_x)

        # HUD
        self._draw_hud()

    def _draw_hud(self):
        # Coin counter
        coin_text = self.font.render(f"Coins: {self.score}", True, UI_TEXT_COLOR)
        self.screen.blit(coin_text, (10, 10))

        # Level name
        level_text = self.small_font.render(
            f"Level {self.current_level + 1}: {self.level_name}", True, UI_TEXT_COLOR
        )
        self.screen.blit(level_text, (10, 45))

        # Health bar
        bar_x = SCREEN_WIDTH - 220
        bar_y = 15
        bar_w = 200
        bar_h = 24
        pygame.draw.rect(self.screen, HEALTH_BG, (bar_x, bar_y, bar_w, bar_h))
        health_w = int(bar_w * (self.player.health / PLAYER_MAX_HEALTH))
        if health_w > 0:
            pygame.draw.rect(self.screen, HEALTH_COLOR, (bar_x, bar_y, health_w, bar_h))
        pygame.draw.rect(self.screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 2)
        health_label = self.small_font.render("Health", True, UI_TEXT_COLOR)
        self.screen.blit(health_label, (bar_x, bar_y + bar_h + 2))

    def _draw_game_over_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(GAME_OVER_BG)
        self.screen.blit(overlay, (0, 0))

        title = self.font.render("GAME OVER", True, (255, 80, 80))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 200))

        score_text = self.small_font.render(
            f"Final Score: {self.score} coins", True, UI_TEXT_COLOR
        )
        self.screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 260))

        restart = self.small_font.render("Press R to Restart | Q to Quit", True, UI_TEXT_COLOR)
        self.screen.blit(restart, (SCREEN_WIDTH // 2 - restart.get_width() // 2, 320))

    def _draw_win_screen(self):
        self.screen.fill((20, 40, 20))
        title = self.font.render("YOU WIN!", True, (80, 255, 80))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 200))

        score_text = self.small_font.render(
            f"Total Score: {self.score} coins", True, UI_TEXT_COLOR
        )
        self.screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 260))

        restart = self.small_font.render("Press R to Play Again | Q to Quit", True, UI_TEXT_COLOR)
        self.screen.blit(restart, (SCREEN_WIDTH // 2 - restart.get_width() // 2, 320))

    def _restart(self):
        self.current_level = 0
        self.score = 0
        self.game_over = False
        self.won = False
        self._load_level(0)
