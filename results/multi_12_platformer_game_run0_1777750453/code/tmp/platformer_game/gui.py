# gui.py - UI drawing (health, coins, game over, menu, level complete, victory)

import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BLACK, WHITE, RED, GREEN,
    BLUE, YELLOW, ORANGE, DARK_RED, GRAY, MAX_HEALTH
)


def draw_hud(screen, player, font):
    """Draw coin counter and health bar on screen."""
    # Coin counter
    coin_text = font.render(f"Coins: {player.coins}", True, YELLOW)
    screen.blit(coin_text, (20, 20))

    # Health bar background
    bar_width = 200
    bar_height = 20
    bar_x = 20
    bar_y = 55

    # Background
    pygame.draw.rect(screen, DARK_RED, (bar_x, bar_y, bar_width, bar_height))
    # Current health
    health_width = int((player.health / MAX_HEALTH) * bar_width)
    if health_width > 0:
        # Gradient from red to green
        if player.health > MAX_HEALTH * 0.5:
            health_color = GREEN
        elif player.health > MAX_HEALTH * 0.25:
            health_color = YELLOW
        else:
            health_color = RED
        pygame.draw.rect(screen, health_color, (bar_x, bar_y, health_width, bar_height))
    # Border
    pygame.draw.rect(screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)

    # Health label
    health_label = font.render(f"HP: {player.health}/{MAX_HEALTH}", True, WHITE)
    screen.blit(health_label, (bar_x + bar_width + 15, bar_y - 2))


def draw_menu(screen, title_font, font):
    """Draw the main menu screen."""
    screen.fill(BLACK)

    # Title
    title = title_font.render("PLATFORMER GAME", True, YELLOW)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
    screen.blit(title, title_rect)

    # Instructions
    lines = [
        "Arrow Keys / WASD - Move",
        "Space / Up / W - Jump",
        "Collect coins and reach the goal!",
        "Avoid enemies or you'll lose health!",
        "",
        "Press ENTER to Start",
    ]
    for i, line in enumerate(lines):
        text = font.render(line, True, WHITE)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + i * 30))
        screen.blit(text, rect)


def draw_game_over(screen, title_font, font, coins_collected):
    """Draw the game over screen."""
    screen.fill(BLACK)

    title = title_font.render("GAME OVER", True, RED)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
    screen.blit(title, title_rect)

    coin_text = font.render(f"Coins Collected: {coins_collected}", True, YELLOW)
    coin_rect = coin_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(coin_text, coin_rect)

    restart_text = font.render("Press R to Restart", True, WHITE)
    restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40))
    screen.blit(restart_text, restart_text)

    menu_text = font.render("Press M for Menu", True, WHITE)
    menu_rect = menu_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 75))
    screen.blit(menu_text, menu_text)


def draw_level_complete(screen, title_font, font, coins_collected, level_name):
    """Draw the level complete screen."""
    screen.fill(BLACK)

    title = title_font.render("LEVEL COMPLETE!", True, GREEN)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
    screen.blit(title, title_rect)

    level_text = font.render(level_name, True, YELLOW)
    level_rect = level_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10))
    screen.blit(level_text, level_rect)

    coin_text = font.render(f"Coins Collected: {coins_collected}", True, YELLOW)
    coin_rect = coin_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 25))
    screen.blit(coin_text, coin_rect)

    continue_text = font.render("Press ENTER to Continue", True, WHITE)
    continue_rect = continue_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
    screen.blit(continue_text, continue_text)


def draw_victory(screen, title_font, font, total_coins):
    """Draw victory screen (all levels completed)."""
    screen.fill(BLACK)

    title = title_font.render("YOU WIN!", True, YELLOW)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
    screen.blit(title, title_rect)

    coin_text = font.render(f"Total Coins: {total_coins}", True, YELLOW)
    coin_rect = coin_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(coin_text, coin_rect)

    restart_text = font.render("Press R to Play Again", True, WHITE)
    restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40))
    screen.blit(restart_text, restart_text)

    menu_text = font.render("Press M for Menu", True, WHITE)
    menu_rect = menu_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 75))
    screen.blit(menu_text, menu_text)
