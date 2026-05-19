import pygame
from settings import (
    COLOR_WHITE, COLOR_RED, COLOR_GREEN, COLOR_BLACK, COLOR_GOLD,
    COIN_COUNTER_POS, HEALTH_BAR_POS, HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT,
    SCREEN_WIDTH, SCREEN_HEIGHT
)


def draw_coin_counter(screen: pygame.Surface, font: pygame.font.Font, count: int):
    """Draw the coin counter at a fixed position on screen."""
    # Background shadow
    shadow_surf = font.render(f"Coins: {count}", True, COLOR_BLACK)
    screen.blit(shadow_surf, (COIN_COUNTER_POS[0] + 2, COIN_COUNTER_POS[1] + 2))
    # Text
    text_surf = font.render(f"Coins: {count}", True, COLOR_GOLD)
    screen.blit(text_surf, COIN_COUNTER_POS)


def draw_health_bar(screen: pygame.Surface, health: int, max_health: int):
    """Draw a health bar at a fixed position on screen."""
    x, y = HEALTH_BAR_POS
    width = HEALTH_BAR_WIDTH
    height = HEALTH_BAR_HEIGHT

    # Background (empty)
    pygame.draw.rect(screen, (60, 60, 60), (x, y, width, height))
    pygame.draw.rect(screen, COLOR_WHITE, (x, y, width, height), 2)

    # Health fill
    if health > 0:
        fill_width = int((health / max_health) * (width - 4))
        fill_rect = pygame.Rect(x + 2, y + 2, fill_width, height - 4)
        # Color gradient from green to red based on health ratio
        ratio = health / max_health
        if ratio > 0.5:
            color = COLOR_GREEN
        elif ratio > 0.25:
            color = (220, 220, 0)  # Yellow
        else:
            color = COLOR_RED
        pygame.draw.rect(screen, color, fill_rect)

    # Health text
    font = pygame.font.Font(None, 20)
    text = font.render(f"HP: {health}/{max_health}", True, COLOR_WHITE)
    screen.blit(text, (x + 4, y + 2))


def draw_game_over(screen: pygame.Surface, large_font: pygame.font.Font, small_font: pygame.font.Font):
    """Draw the game over screen."""
    # Dark overlay
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(180)
    overlay.fill(COLOR_BLACK)
    screen.blit(overlay, (0, 0))

    # Game over text
    game_over_text = large_font.render("GAME OVER", True, COLOR_RED)
    rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40))
    screen.blit(game_over_text, rect)

    restart_text = small_font.render("Press any key to restart", True, COLOR_WHITE)
    rect2 = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
    screen.blit(restart_text, rect2)


def draw_level_complete(screen: pygame.Surface, large_font: pygame.font.Font, level_name: str):
    """Draw a level complete message."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    overlay.set_alpha(150)
    overlay.fill(COLOR_BLACK)
    screen.blit(overlay, (0, 0))

    text = large_font.render("LEVEL COMPLETE!", True, COLOR_GREEN)
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
    screen.blit(text, rect)

    sub_text = pygame.font.Font(None, 36).render(f"Loading {level_name}...", True, COLOR_WHITE)
    rect2 = sub_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
    screen.blit(sub_text, rect2)


def draw_level_title(screen: pygame.Surface, font: pygame.font.Font, level_name: str, alpha: int):
    """Draw a level title with fade effect."""
    text = font.render(level_name, True, COLOR_WHITE)
    text.set_alpha(alpha)
    rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(text, rect)
