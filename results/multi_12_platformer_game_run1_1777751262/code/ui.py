"""
Platformer Game - UI module
HUD elements: health bar, coin counter, game over screen, level complete screen.
"""
import pygame
from constants import *


class UI:
    def __init__(self):
        self.font_small = pygame.font.Font(None, 28)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_large = pygame.font.Font(None, 72)

    def draw_hud(self, screen, player, score, level_num):
        """Draw health bar and coin counter."""
        # Health bar background
        bg_rect = pygame.Rect(
            HEALTH_BAR_X, HEALTH_BAR_Y,
            HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT
        )
        pygame.draw.rect(screen, HEALTH_BAR_BG_COLOR, bg_rect)
        pygame.draw.rect(screen, HEALTH_BAR_BORDER_COLOR, bg_rect, 2)

        # Health bar fill
        health_ratio = player.health / PLAYER_MAX_HEALTH
        if health_ratio > 0:
            fill_width = int(HEALTH_BAR_WIDTH * health_ratio)
            fill_rect = pygame.Rect(
                HEALTH_BAR_X + 2, HEALTH_BAR_Y + 2,
                fill_width - 4, HEALTH_BAR_HEIGHT - 4
            )

            # Color shifts from green to red based on health
            if health_ratio > 0.6:
                bar_color = GREEN
            elif health_ratio > 0.3:
                bar_color = YELLOW
            else:
                bar_color = RED

            pygame.draw.rect(screen, bar_color, fill_rect)

        # Health label
        health_text = self.font_small.render(
            f"HP: {player.health}/{PLAYER_MAX_HEALTH}",
            True, WHITE
        )
        screen.blit(health_text, (HEALTH_BAR_X, HEALTH_BAR_Y + HEALTH_BAR_HEIGHT + 5))

        # Coin counter
        coin_text = self.font_medium.render(
            f"Coins: {score}",
            True, GOLD
        )
        coin_x = HEALTH_BAR_X + HEALTH_BAR_WIDTH + 30
        screen.blit(coin_text, (coin_x, HEALTH_BAR_Y))

        # Level indicator
        level_text = self.font_small.render(
            f"Level {level_num}",
            True, WHITE
        )
        level_rect = level_text.get_rect(topright=(WIDTH - 20, 20))
        screen.blit(level_text, level_rect)

    def draw_game_over(self, screen):
        """Draw game over overlay."""
        # Dark overlay
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))

        # Game over text
        game_over_text = self.font_large.render("GAME OVER", True, RED)
        text_rect = game_over_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
        screen.blit(game_over_text, text_rect)

        # Restart instruction
        restart_text = self.font_medium.render(
            "Press R to Restart",
            True, WHITE
        )
        restart_rect = restart_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
        screen.blit(restart_text, restart_rect)

        # Quit instruction
        quit_text = self.font_small.render(
            "Press Q to Quit",
            True, GRAY
        )
        quit_rect = quit_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 70))
        screen.blit(quit_text, quit_rect)

    def draw_level_complete(self, screen, level_num, total_levels):
        """Draw level complete overlay."""
        # Dark overlay
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))

        if level_num >= total_levels:
            # All levels complete!
            title_text = self.font_large.render("YOU WIN!", True, GOLD)
            sub_text = self.font_medium.render(
                "All levels completed!",
                True, WHITE
            )
        else:
            title_text = self.font_large.render("LEVEL COMPLETE!", True, GREEN)
            sub_text = self.font_medium.render(
                "Press ENTER to continue",
                True, WHITE
            )

        title_rect = title_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
        screen.blit(title_text, title_rect)

        sub_rect = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
        screen.blit(sub_text, sub_rect)

        level_str = f"Level {level_num} of {total_levels}"
        level_text = self.font_small.render(level_str, True, GRAY)
        level_rect = level_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 60))
        screen.blit(level_text, level_rect)

    def draw_menu(self, screen):
        """Draw main menu screen."""
        screen.fill(SKY_BLUE)

        # Title
        title_text = self.font_large.render("PLATFORMER", True, WHITE)
        title_rect = title_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
        # Shadow
        shadow_text = self.font_large.render("PLATFORMER", True, DARK_GRAY)
        shadow_rect = shadow_text.get_rect(center=(WIDTH // 2 + 3, HEIGHT // 2 - 77))
        screen.blit(shadow_text, shadow_rect)
        screen.blit(title_text, title_rect)

        # Subtitle
        sub_text = self.font_medium.render("Adventure", True, GOLD)
        sub_rect = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
        screen.blit(sub_text, sub_rect)

        # Instructions
        start_text = self.font_medium.render("Press ENTER to Start", True, WHITE)
        start_rect = start_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50))
        screen.blit(start_text, start_rect)

        controls_text = self.font_small.render(
            "Arrow Keys: Move  |  Space: Jump  |  Collect coins, avoid enemies!",
            True, GRAY
        )
        controls_rect = controls_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 100))
        screen.blit(controls_text, controls_rect)

        # Draw a little player for decoration
        player_rect = pygame.Rect(WIDTH // 2 - 15, HEIGHT // 2 - 160, 30, 40)
        pygame.draw.rect(screen, BLUE, player_rect)
        pygame.draw.rect(screen, WHITE, player_rect, 2)
