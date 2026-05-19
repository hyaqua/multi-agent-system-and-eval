"""Rendering functions for the Tetris game."""

import pygame
import settings


class Display:
    """Handles all rendering of the game."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_large = pygame.font.Font(None, 48)
        self.font_title = pygame.font.Font(None, 64)

    def draw(self, state: dict):
        """Draw the entire game frame."""
        self.screen.fill(settings.BLACK)

        self._draw_grid_background()
        self._draw_locked_cells(state['grid_cells'])
        self._draw_ghost_piece(state['ghost_cells'])
        self._draw_active_piece(state['piece_cells'])
        self._draw_grid_border()
        self._draw_sidebar(state)

        if state['game_over']:
            self._draw_game_over_overlay(state)

    def _draw_grid_background(self):
        """Draw the grid background with subtle cell lines."""
        x0 = settings.GRID_OFFSET_X
        y0 = settings.GRID_OFFSET_Y
        width = settings.GRID_WIDTH * settings.CELL_SIZE
        height = settings.GRID_HEIGHT * settings.CELL_SIZE

        # Background
        pygame.draw.rect(self.screen, settings.GRID_BG,
                         (x0, y0, width, height))

        # Grid lines
        for row in range(settings.GRID_HEIGHT + 1):
            y = y0 + row * settings.CELL_SIZE
            pygame.draw.line(self.screen, settings.DARK_GRAY,
                             (x0, y), (x0 + width, y), 1)
        for col in range(settings.GRID_WIDTH + 1):
            x = x0 + col * settings.CELL_SIZE
            pygame.draw.line(self.screen, settings.DARK_GRAY,
                             (x, y0), (x, y0 + height), 1)

    def _draw_grid_border(self):
        """Draw a bright border around the grid."""
        x0 = settings.GRID_OFFSET_X
        y0 = settings.GRID_OFFSET_Y
        width = settings.GRID_WIDTH * settings.CELL_SIZE
        height = settings.GRID_HEIGHT * settings.CELL_SIZE
        pygame.draw.rect(self.screen, settings.GRID_BORDER,
                         (x0 - 2, y0 - 2, width + 4, height + 4), 2)

    def _draw_locked_cells(self, grid_cells):
        """Draw locked cells on the grid."""
        for row, col, color in grid_cells:
            self._draw_cell(row, col, color)

    def _draw_active_piece(self, piece_cells):
        """Draw the active piece."""
        for row, col, color in piece_cells:
            if row >= 0:  # Don't draw cells above the grid
                self._draw_cell(row, col, color)

    def _draw_ghost_piece(self, ghost_cells):
        """Draw ghost piece (where piece will land)."""
        for row, col, color in ghost_cells:
            if row >= 0:
                self._draw_cell(row, col, color, ghost=True)

    def _draw_cell(self, row: int, col: int, color, ghost: bool = False):
        """Draw a single cell on the grid."""
        x = settings.GRID_OFFSET_X + col * settings.CELL_SIZE
        y = settings.GRID_OFFSET_Y + row * settings.CELL_SIZE
        size = settings.CELL_SIZE

        if ghost:
            # Draw outline only for ghost
            pygame.draw.rect(self.screen, color, (x, y, size, size), 2)
        else:
            # Filled cell with border
            pygame.draw.rect(self.screen, color, (x + 1, y + 1, size - 2, size - 2))
            # Lighter top-left edge for 3D effect
            lighter = tuple(min(255, c + 60) for c in color)
            darker = tuple(max(0, c - 60) for c in color)
            pygame.draw.line(self.screen, lighter, (x + 1, y + 1), (x + size - 2, y + 1), 1)
            pygame.draw.line(self.screen, lighter, (x + 1, y + 1), (x + 1, y + size - 2), 1)
            pygame.draw.line(self.screen, darker, (x + 1, y + size - 2), (x + size - 2, y + size - 2), 1)
            pygame.draw.line(self.screen, darker, (x + size - 2, y + 1), (x + size - 2, y + size - 2), 1)

    def _draw_sidebar(self, state):
        """Draw the sidebar with next piece preview, score, level, lines."""
        sidebar_x = settings.GRID_OFFSET_X + settings.GRID_WIDTH * settings.CELL_SIZE + settings.SIDEBAR_PADDING
        y = settings.GRID_OFFSET_Y

        # Next piece label
        label = self.font_medium.render("NEXT", True, settings.WHITE)
        self.screen.blit(label, (sidebar_x, y))
        y += 30

        # Next piece box
        box_size = 5 * settings.PREVIEW_CELL_SIZE
        box_x = sidebar_x
        box_y = y
        pygame.draw.rect(self.screen, settings.GRID_BG,
                         (box_x, box_y, box_size, box_size))
        pygame.draw.rect(self.screen, settings.GRID_BORDER,
                         (box_x, box_y, box_size, box_size), 2)

        # Draw next piece inside the box
        if state['next_cells'] and state['next_color']:
            # Calculate bounding box of the piece to center it
            cells = state['next_cells']
            min_row = min(r for r, c in cells)
            max_row = max(r for r, c in cells)
            min_col = min(c for r, c in cells)
            max_col = max(c for r, c in cells)
            piece_w = (max_col - min_col + 1) * settings.PREVIEW_CELL_SIZE
            piece_h = (max_row - min_row + 1) * settings.PREVIEW_CELL_SIZE
            offset_x = box_x + (box_size - piece_w) // 2 - min_col * settings.PREVIEW_CELL_SIZE
            offset_y = box_y + (box_size - piece_h) // 2 - min_row * settings.PREVIEW_CELL_SIZE

            for r, c in cells:
                px = offset_x + c * settings.PREVIEW_CELL_SIZE
                py = offset_y + r * settings.PREVIEW_CELL_SIZE
                pygame.draw.rect(self.screen, state['next_color'],
                                 (px + 1, py + 1,
                                  settings.PREVIEW_CELL_SIZE - 2,
                                  settings.PREVIEW_CELL_SIZE - 2))

        y += box_size + 20

        # Score
        score_label = self.font_medium.render("SCORE", True, settings.WHITE)
        self.screen.blit(score_label, (sidebar_x, y))
        y += 28
        score_val = self.font_large.render(str(state['score']), True, settings.WHITE)
        self.screen.blit(score_val, (sidebar_x, y))
        y += 40

        # Level
        level_label = self.font_medium.render("LEVEL", True, settings.WHITE)
        self.screen.blit(level_label, (sidebar_x, y))
        y += 28
        level_val = self.font_large.render(str(state['level']), True, settings.WHITE)
        self.screen.blit(level_val, (sidebar_x, y))
        y += 40

        # Lines
        lines_label = self.font_medium.render("LINES", True, settings.WHITE)
        self.screen.blit(lines_label, (sidebar_x, y))
        y += 28
        lines_val = self.font_large.render(str(state['lines']), True, settings.WHITE)
        self.screen.blit(lines_val, (sidebar_x, y))

        # Controls hint
        y = settings.WINDOW_HEIGHT - 160
        controls = [
            "CONTROLS",
            "← →  Move",
            "↑     Rotate",
            "↓     Soft Drop",
            "SPACE  Hard Drop",
            "R     Restart",
            "Q     Quit",
        ]
        for line in controls:
            if line == "CONTROLS":
                text = self.font_small.render(line, True, settings.LIGHT_GRAY)
            else:
                text = self.font_small.render(line, True, settings.LIGHT_GRAY)
            self.screen.blit(text, (sidebar_x, y))
            y += 18

    def _draw_game_over_overlay(self, state):
        """Draw the game over overlay."""
        # Semi-transparent dark overlay
        overlay = pygame.Surface((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(settings.BLACK)
        self.screen.blit(overlay, (0, 0))

        center_x = settings.WINDOW_WIDTH // 2
        center_y = settings.WINDOW_HEIGHT // 2

        # Game Over title
        title = self.font_title.render("GAME OVER", True, (255, 80, 80))
        title_rect = title.get_rect(center=(center_x, center_y - 80))
        self.screen.blit(title, title_rect)

        # Score
        score_text = self.font_medium.render(f"Final Score: {state['score']}", True, settings.WHITE)
        score_rect = score_text.get_rect(center=(center_x, center_y - 20))
        self.screen.blit(score_text, score_rect)

        # Level
        level_text = self.font_medium.render(f"Level Reached: {state['level']}", True, settings.WHITE)
        level_rect = level_text.get_rect(center=(center_x, center_y + 20))
        self.screen.blit(level_text, level_rect)

        # Lines
        lines_text = self.font_medium.render(f"Lines Cleared: {state['lines']}", True, settings.WHITE)
        lines_rect = lines_text.get_rect(center=(center_x, center_y + 60))
        self.screen.blit(lines_text, lines_rect)

        # Restart / Quit prompt
        prompt = self.font_small.render("Press R to Restart  |  Press Q to Quit", True, settings.LIGHT_GRAY)
        prompt_rect = prompt.get_rect(center=(center_x, center_y + 120))
        self.screen.blit(prompt, prompt_rect)
