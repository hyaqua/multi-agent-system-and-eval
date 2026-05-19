"""
Renderer: all drawing functions for the Tetris game.

Functions take a pygame Surface and a Game instance; they know nothing
about input or timing.
"""

import pygame
from constants import (
    COLS, ROWS, CELL_SIZE,
    BOARD_X, BOARD_Y, BOARD_PIXEL_W, BOARD_PIXEL_H,
    PREVIEW_X, PREVIEW_Y, PREVIEW_CELL,
    SCREEN_W, SCREEN_H,
    DARK_GRAY, LIGHT_GRAY, WHITE, RED,
    BG_COLOR, BOARD_BG, BORDER_COLOR, TEXT_COLOR,
)
from game import Game


def init_screen() -> pygame.Surface:
    """Create and return the game window surface."""
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Tetris")
    return screen


def draw_board(surface: pygame.Surface, game: Game):
    """Draw the grid lines and locked cells."""
    # Board background
    rect = pygame.Rect(BOARD_X, BOARD_Y, BOARD_PIXEL_W, BOARD_PIXEL_H)
    pygame.draw.rect(surface, BOARD_BG, rect)

    # Grid lines
    for r in range(ROWS + 1):
        y = BOARD_Y + r * CELL_SIZE
        pygame.draw.line(surface, DARK_GRAY,
                         (BOARD_X, y), (BOARD_X + BOARD_PIXEL_W, y))
    for c in range(COLS + 1):
        x = BOARD_X + c * CELL_SIZE
        pygame.draw.line(surface, DARK_GRAY,
                         (x, BOARD_Y), (x, BOARD_Y + BOARD_PIXEL_H))

    # Locked cells
    for r in range(ROWS):
        for c in range(COLS):
            color = game.board[r][c]
            if color is not None:
                x = BOARD_X + c * CELL_SIZE
                y = BOARD_Y + r * CELL_SIZE
                pygame.draw.rect(surface, color,
                                 (x + 1, y + 1, CELL_SIZE - 2, CELL_SIZE - 2))

    # Border around the board
    pygame.draw.rect(surface, BORDER_COLOR, rect, 2)


def draw_piece(surface: pygame.Surface, piece: dict, alpha: int = 255):
    """Draw a single piece (used for current piece and ghost)."""
    if piece is None:
        return
    shape = piece["shapes"][piece["rotation"]]
    color = piece["color"]
    px, py = piece["x"], piece["y"]

    # Create a temporary surface with alpha if needed
    if alpha < 255:
        # Use a per-pixel alpha surface for transparency
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    bx = BOARD_X + (px + col_idx) * CELL_SIZE
                    by = BOARD_Y + (py + row_idx) * CELL_SIZE
                    if by >= BOARD_Y:  # only draw visible part
                        alpha_surf = pygame.Surface((CELL_SIZE - 2, CELL_SIZE - 2),
                                                    pygame.SRCALPHA)
                        alpha_surf.fill((*color, alpha))
                        surface.blit(alpha_surf, (bx + 1, by + 1))
    else:
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    bx = BOARD_X + (px + col_idx) * CELL_SIZE
                    by = BOARD_Y + (py + row_idx) * CELL_SIZE
                    if by >= BOARD_Y:
                        pygame.draw.rect(surface, color,
                                         (bx + 1, by + 1,
                                          CELL_SIZE - 2, CELL_SIZE - 2))


def draw_ghost(surface: pygame.Surface, game: Game):
    """Draw the ghost piece (landing preview)."""
    if game.game_over:
        return
    ghost = game.current_piece.copy()
    ghost["y"] = game.get_ghost_y()
    # Make sure we don't draw ghost on top of the actual piece if they overlap
    if ghost["y"] == game.current_piece["y"]:
        return
    draw_piece(surface, ghost, alpha=60)


def draw_next_preview(surface: pygame.Surface, game: Game):
    """Draw the next-piece preview panel."""
    if game.game_over:
        return

    font = pygame.font.Font(None, 22*2)
    label = font.render("NEXT", True, TEXT_COLOR)
    surface.blit(label, (PREVIEW_X, PREVIEW_Y - 25))

    # Preview box background
    box_w = 4 * PREVIEW_CELL
    box_h = 4 * PREVIEW_CELL
    pygame.draw.rect(surface, BOARD_BG,
                     (PREVIEW_X, PREVIEW_Y, box_w, box_h))
    pygame.draw.rect(surface, BORDER_COLOR,
                     (PREVIEW_X, PREVIEW_Y, box_w, box_h), 2)

    piece = game.next_piece
    shape = piece["shapes"][0]  # always show first rotation
    color = piece["color"]

    # Center the piece in the preview box
    rows = len(shape)
    cols = len(shape[0]) if rows > 0 else 0
    offset_x = (box_w - cols * PREVIEW_CELL) // 2
    offset_y = (box_h - rows * PREVIEW_CELL) // 2

    for row_idx, row in enumerate(shape):
        for col_idx, cell in enumerate(row):
            if cell:
                x = PREVIEW_X + offset_x + col_idx * PREVIEW_CELL
                y = PREVIEW_Y + offset_y + row_idx * PREVIEW_CELL
                pygame.draw.rect(surface, color,
                                 (x + 1, y + 1,
                                  PREVIEW_CELL - 2, PREVIEW_CELL - 2))


def draw_score(surface: pygame.Surface, game: Game):
    """Draw score and level text."""
    font = pygame.font.Font(None, 28*2)

    score_text = f"Score: {game.score}"
    level_text = f"Level: {game.level}"

    score_surf = font.render(score_text, True, TEXT_COLOR)
    level_surf = font.render(level_text, True, TEXT_COLOR)

    sx = PREVIEW_X
    sy = PREVIEW_Y + 4 * PREVIEW_CELL + 20

    surface.blit(score_surf, (sx, sy))
    surface.blit(level_surf, (sx, sy + 30))


def draw_game_over(surface: pygame.Surface, game: Game):
    """Draw the game-over overlay."""
    # Semi-transparent dark overlay
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    font_large = pygame.font.Font(None, 64*2)
    font_small = pygame.font.Font(None, 32*2)
    font_tiny = pygame.font.Font(None, 24*2)

    # Game Over text
    go_surf = font_large.render("GAME OVER", True, RED)
    go_rect = go_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 60))
    surface.blit(go_surf, go_rect)

    # Score
    score_surf = font_small.render(
        f"Final Score: {game.score}", True, WHITE)
    score_rect = score_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2))
    surface.blit(score_surf, score_rect)

    # Level
    level_surf = font_small.render(
        f"Level Reached: {game.level}", True, WHITE)
    level_rect = level_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 35))
    surface.blit(level_surf, level_rect)

    # Restart prompt
    restart_surf = font_tiny.render(
        "Press R to restart  |  ESC to quit", True, LIGHT_GRAY)
    restart_rect = restart_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 80))
    surface.blit(restart_surf, restart_rect)


def render(surface: pygame.Surface, game: Game):
    """Main render function – draws everything for the current frame."""
    surface.fill(BG_COLOR)

    draw_board(surface, game)

    if not game.game_over:
        draw_ghost(surface, game)
        draw_piece(surface, game.current_piece)

    draw_next_preview(surface, game)
    draw_score(surface, game)

    if game.game_over:
        draw_game_over(surface, game)
