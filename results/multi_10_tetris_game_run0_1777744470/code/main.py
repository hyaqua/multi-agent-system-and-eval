"""
Tetris – main entry point.  Handles the game loop, rendering, input, and state.
"""

import random
import sys
import pygame

import constants as C
from board import Board
from piece import Piece, SHAPES


# ---------------------------------------------------------------------------
# Helper / rendering utilities
# ---------------------------------------------------------------------------

def draw_cell(surface, col, row, color, alpha=255):
    """Draw a single board cell at grid coordinates."""
    x = C.BOARD_X + col * C.CELL_SIZE
    y = C.BOARD_Y + row * C.CELL_SIZE
    rect = pygame.Rect(x, y, C.CELL_SIZE, C.CELL_SIZE)

    if alpha < 255:
        # Create a temporary surface for alpha blending
        cell_surf = pygame.Surface((C.CELL_SIZE, C.CELL_SIZE), pygame.SRCALPHA)
        cell_surf.fill((*color, alpha))
        surface.blit(cell_surf, (x, y))
    else:
        pygame.draw.rect(surface, color, rect)

    # Subtle 3D highlight
    lighter = tuple(min(255, c + 60) for c in color)
    darker = tuple(max(0, c - 60) for c in color)
    pygame.draw.line(surface, lighter, rect.topleft, rect.topright, 2)
    pygame.draw.line(surface, lighter, rect.topleft, rect.bottomleft, 2)
    pygame.draw.line(surface, darker, rect.bottomleft, rect.bottomright, 2)
    pygame.draw.line(surface, darker, rect.topright, rect.bottomright, 2)


def draw_text(surface, text, x, y, size=22, color=C.WHITE, center=False):
    """Render *text* at pixel position."""
    font = pygame.font.Font(None, size)
    img = font.render(text, True, color)
    if center:
        rect = img.get_rect(center=(x, y))
        surface.blit(img, rect)
    else:
        surface.blit(img, (x, y))


def draw_preview(surface, piece_type, x, y):
    """Draw a miniature preview of the next piece inside a bordered box."""
    box_width = 120
    box_height = 120
    # Box background
    pygame.draw.rect(surface, C.DARK_GRAY, (x, y, box_width, box_height))
    pygame.draw.rect(surface, C.WHITE, (x, y, box_width, box_height), 2)

    draw_text(surface, "NEXT", x + box_width // 2, y - 18, size=20,
              color=C.LIGHT_GRAY, center=True)

    shape = SHAPES[piece_type]['shape']
    color = SHAPES[piece_type]['color']
    cell_sz = 22
    rows = len(shape)
    cols = len(shape[0])
    # Centre the piece inside the preview box
    offset_x = x + (box_width - cols * cell_sz) // 2
    offset_y = y + (box_height - rows * cell_sz) // 2

    for r, row in enumerate(shape):
        for c, val in enumerate(row):
            if val:
                px = offset_x + c * cell_sz
                py = offset_y + r * cell_sz
                rect = pygame.Rect(px, py, cell_sz, cell_sz)
                pygame.draw.rect(surface, color, rect)
                pygame.draw.rect(surface, C.WHITE, rect, 1)


def draw_board(surface, board):
    """Draw the locked cells + grid lines."""
    # Board background
    board_rect = pygame.Rect(C.BOARD_X, C.BOARD_Y, C.BOARD_WIDTH, C.BOARD_HEIGHT)
    pygame.draw.rect(surface, C.DARK_GRAY, board_rect)

    # Grid lines
    for r in range(C.ROWS + 1):
        y = C.BOARD_Y + r * C.CELL_SIZE
        pygame.draw.line(surface, C.GRID_LINE_COLOR,
                         (C.BOARD_X, y), (C.BOARD_X + C.BOARD_WIDTH, y))
    for c in range(C.COLS + 1):
        x = C.BOARD_X + c * C.CELL_SIZE
        pygame.draw.line(surface, C.GRID_LINE_COLOR,
                         (x, C.BOARD_Y), (x, C.BOARD_Y + C.BOARD_HEIGHT))

    # Locked cells
    for r in range(C.ROWS):
        for c in range(C.COLS):
            color = board.grid[r][c]
            if color != C.BLACK:
                draw_cell(surface, c, r, color)

    # Border
    pygame.draw.rect(surface, C.BOARD_BORDER_COLOR, board_rect, 3)


def draw_piece(surface, piece):
    """Draw the currently active piece (ghost cells are only drawn when on the board)."""
    for board_x, board_y in piece.get_cells():
        if board_y >= 0:  # don't draw cells above the visible area
            draw_cell(surface, board_x, board_y, piece.color)


# ---------------------------------------------------------------------------
# Game state machine
# ---------------------------------------------------------------------------

class Game:
    """Top-level Tetris game controller."""

    def __init__(self):
        self.board = Board()
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False

        # Piece queue
        self.next_type = self._random_type()
        self.current_piece = None

        # Timing
        self.last_drop_time = 0
        self.drop_interval = C.INITIAL_DROP_INTERVAL
        self.soft_drop_active = False

        self._spawn_piece()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _random_type(self):
        return random.choice(list(SHAPES.keys()))

    def _spawn_piece(self):
        """Create the next piece and advance the preview."""
        piece_type = self.next_type
        self.next_type = self._random_type()
        piece = Piece(piece_type)
        if self.board.is_game_over(piece):
            self.game_over = True
            self.current_piece = None
        else:
            self.current_piece = piece
            self.last_drop_time = pygame.time.get_ticks()
            self.soft_drop_active = False

    def _lock_and_advance(self):
        """Lock the current piece, clear lines, update score/level, spawn next."""
        self.board.lock_piece(self.current_piece)
        cleared = self.board.clear_lines()
        if cleared > 0:
            # Scoring
            pts = C.POINTS_PER_LINE.get(cleared, cleared * 200)
            self.score += pts * self.level
            self.lines_cleared += cleared
            # Level up
            new_level = self.lines_cleared // C.LINES_PER_LEVEL + 1
            if new_level > self.level:
                self.level = new_level
                self.drop_interval = max(
                    C.MIN_DROP_INTERVAL,
                    C.INITIAL_DROP_INTERVAL - (self.level - 1) * C.SPEED_DECREMENT_PER_LEVEL,
                )
        self._spawn_piece()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_keydown(self, key):
        if self.game_over:
            return

        piece = self.current_piece
        if piece is None:
            return

        if key == pygame.K_LEFT:
            if self.board.is_valid_position(piece.shape, piece.x - 1, piece.y):
                piece.x -= 1
        elif key == pygame.K_RIGHT:
            if self.board.is_valid_position(piece.shape, piece.x + 1, piece.y):
                piece.x += 1
        elif key == pygame.K_UP:
            self._rotate_piece()
        # Soft drop is handled via key polling in update() — see below.

    def _rotate_piece(self):
        """Attempt to rotate the current piece clockwise, with simple wall kicks."""
        piece = self.current_piece
        if piece is None or piece.type == 'O':  # O doesn't rotate
            return

        rotated = piece.rotate()

        # Try original position
        if self.board.is_valid_position(rotated, piece.x, piece.y):
            piece.shape = rotated
            return

        # Simple wall-kick offsets: ±1, ±2 columns
        for dx in (1, -1, 2, -2):
            if self.board.is_valid_position(rotated, piece.x + dx, piece.y):
                piece.shape = rotated
                piece.x += dx
                return

    # ------------------------------------------------------------------
    # Update (called every frame)
    # ------------------------------------------------------------------

    def update(self):
        if self.game_over or self.current_piece is None:
            return

        # Poll for soft-drop (down arrow held)
        keys = pygame.key.get_pressed()
        self.soft_drop_active = keys[pygame.K_DOWN]

        now = pygame.time.get_ticks()
        interval = C.SOFT_DROP_INTERVAL if self.soft_drop_active else self.drop_interval

        if now - self.last_drop_time >= interval:
            self._try_move_down()
            self.last_drop_time = now

    def _try_move_down(self):
        """Move current piece down by one row; lock if impossible."""
        piece = self.current_piece
        if self.board.is_valid_position(piece.shape, piece.x, piece.y + 1):
            piece.y += 1
            # Award a small score for soft drop
            if self.soft_drop_active:
                self.score += 1
        else:
            self._lock_and_advance()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface):
        surface.fill(C.BG_COLOR)

        # Board
        draw_board(surface, self.board)

        # Active piece
        if self.current_piece is not None and not self.game_over:
            draw_piece(surface, self.current_piece)

        # Sidebar
        sx = C.SIDEBAR_X
        sy = C.SIDEBAR_Y

        # Next piece preview
        draw_preview(surface, self.next_type, sx, sy + 20)

        # Score / Level / Lines
        info_y = sy + 170
        draw_text(surface, f"Score", sx, info_y, size=18, color=C.LIGHT_GRAY)
        draw_text(surface, f"{self.score:,}", sx, info_y + 22, size=26, color=C.WHITE)

        info_y += 60
        draw_text(surface, f"Level", sx, info_y, size=18, color=C.LIGHT_GRAY)
        draw_text(surface, f"{self.level}", sx, info_y + 22, size=26, color=C.WHITE)

        info_y += 60
        draw_text(surface, f"Lines", sx, info_y, size=18, color=C.LIGHT_GRAY)
        draw_text(surface, f"{self.lines_cleared}", sx, info_y + 22, size=26, color=C.WHITE)

        # Game-over overlay
        if self.game_over:
            self._draw_game_over(surface)

    def _draw_game_over(self, surface):
        """Semi-transparent overlay with final stats."""
        overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        cx = C.WINDOW_WIDTH // 2
        cy = C.WINDOW_HEIGHT // 2

        draw_text(surface, "GAME OVER", cx, cy - 60, size=48, color=C.RED, center=True)
        draw_text(surface, f"Final Score: {self.score:,}", cx, cy, size=28,
                  color=C.WHITE, center=True)
        draw_text(surface, f"Level Reached: {self.level}", cx, cy + 35, size=24,
                  color=C.LIGHT_GRAY, center=True)
        draw_text(surface, "Press ESC to quit  |  Press R to restart", cx, cy + 80,
                  size=18, color=C.GRAY, center=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Tetris")
    screen = pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT))
    clock = pygame.time.Clock()

    game = Game()

    # Key repeat for held-down left/right/down keys
    pygame.key.set_repeat(200, 50)

    running = True
    while running:
        # --- Event pump ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r and game.game_over:
                    game = Game()  # restart
                else:
                    game.handle_keydown(event.key)

            # KEYUP not needed — soft-drop is polled in update()

        # --- Update ---
        game.update()

        # --- Draw ---
        game.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
