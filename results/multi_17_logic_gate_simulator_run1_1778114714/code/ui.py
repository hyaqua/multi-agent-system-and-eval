"""UI helpers for overlays and coordinate display."""
import pygame
from config import COLOR_TEXT, COLOR_CYCLE_WARNING, FONT_SIZE_SMALL


def draw_coordinate_overlay(screen, canvas, font=None):
    """Draw world coordinates under mouse and zoom percentage."""
    if font is None:
        font = pygame.font.Font(None, FONT_SIZE_SMALL)

    mx, my = pygame.mouse.get_pos()
    wx, wy = canvas.screen_to_world(mx, my)

    zoom_pct = f"Zoom: {canvas.zoom * 100:.0f}%"
    coord_text = f"World: ({wx:.0f}, {wy:.0f})"

    # Position in top-right corner of canvas area
    screen_w = screen.get_width()
    x = screen_w - 10
    y = 10

    zoom_surf = font.render(zoom_pct, True, COLOR_TEXT)
    zoom_rect = zoom_surf.get_rect(topright=(x, y))
    screen.blit(zoom_surf, zoom_rect)

    coord_surf = font.render(coord_text, True, COLOR_TEXT)
    coord_rect = coord_surf.get_rect(topright=(x, y + 18))
    screen.blit(coord_surf, coord_rect)


def draw_warning_overlay(screen, message, font=None):
    """Draw a warning message overlay at the top center."""
    if not message:
        return
    if font is None:
        font = pygame.font.Font(None, 24)

    surf = font.render(message, True, COLOR_CYCLE_WARNING)
    rect = surf.get_rect(center=(screen.get_width() // 2, 30))

    # Background
    bg_rect = rect.inflate(20, 10)
    pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
    pygame.draw.rect(screen, COLOR_CYCLE_WARNING, bg_rect, 1)
    screen.blit(surf, rect)


def draw_help_text(screen, font=None):
    """Draw help text at the bottom."""
    if font is None:
        font = pygame.font.Font(None, FONT_SIZE_SMALL)

    help_lines = [
        "Ctrl+S: Save  |  Ctrl+O: Load  |  Del: Delete selected  |  Space+Drag: Pan  |  Scroll: Zoom",
        "Click output pin -> input pin to wire  |  Right-click wire to delete  |  Right-click component: Properties",
    ]
    y = screen.get_height() - 10
    for line in reversed(help_lines):
        surf = font.render(line, True, (140, 140, 150))
        rect = surf.get_rect(bottomright=(screen.get_width() - 10, y))
        screen.blit(surf, rect)
        y -= 16
