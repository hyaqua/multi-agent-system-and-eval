import pygame
import random
import sys
from constants import *

class Tetris:
    def __init__(self):
        # The board: grid with extra hidden rows at top
        # 0 = empty, otherwise a color tuple
        self.total_rows = GRID_ROWS + HIDDEN_ROWS
        self.board = [[None for _ in range(GRID_COLS)] for _ in range(self.total_rows)]

        self.current_piece = None
        self.current_pos = (0, 0)  # (row, col) of top-left of piece bounding box
        self.next_piece_name = None
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.fall_speed = INITIAL_SPEED
        self.fall_timer = 0
        self.soft_dropping = False

        # Bag randomizer: shuffle all 7 pieces, deal them out, reshuffle when empty
        self.bag = []
        self._refill_bag()
        self._spawn_piece()

    def _refill_bag(self):
        pieces = list(TETROMINOES.keys())
        random.shuffle(pieces)
        self.bag.extend(pieces)

    def _get_next_from_bag(self):
        if len(self.bag) == 0:
            self._refill_bag()
        return self.bag.pop(0)

    def _get_piece_shape(self, piece_name):
        return [row[:] for row in TETROMINOES[piece_name]['shape']]

    def _get_piece_color(self, piece_name):
        return TETROMINOES[piece_name]['color']

    def _spawn_piece(self):
        if self.next_piece_name is None:
            piece_name = self._get_next_from_bag()
        else:
            piece_name = self.next_piece_name

        self.next_piece_name = self._get_next_from_bag()

        shape = self._get_piece_shape(piece_name)
        color = self._get_piece_color(piece_name)
        self.current_piece = {
            'name': piece_name,
            'shape': shape,
            'color': color
        }

        # Spawn position: centered horizontally, at top (in hidden rows)
        piece_width = len(shape[0])
        spawn_col = (GRID_COLS - piece_width) // 2
        spawn_row = 0  # top of hidden rows

        if not self._is_valid_position(shape, spawn_row, spawn_col):
            self.game_over = True
            self.current_piece = None
        else:
            self.current_pos = (spawn_row, spawn_col)

        self.fall_timer = 0
        self.soft_dropping = False

    def _is_valid_position(self, shape, row, col):
        """Check if the piece placed at (row, col) is valid (no collisions)."""
        for r in range(len(shape)):
            for c in range(len(shape[r])):
                if shape[r][c]:
                    board_r = row + r
                    board_c = col + c
                    # Check boundaries
                    if board_c < 0 or board_c >= GRID_COLS:
                        return False
                    if board_r >= self.total_rows:
                        return False
                    # Allow pieces above the board (negative row) — but they must be within hidden rows
                    if board_r < 0:
                        continue
                    # Check collision with existing blocks
                    if self.board[board_r][board_c] is not None:
                        return False
        return True

    def move_left(self):
        if self.game_over or self.current_piece is None:
            return
        shape = self.current_piece['shape']
        row, col = self.current_pos
        if self._is_valid_position(shape, row, col - 1):
            self.current_pos = (row, col - 1)

    def move_right(self):
        if self.game_over or self.current_piece is None:
            return
        shape = self.current_piece['shape']
        row, col = self.current_pos
        if self._is_valid_position(shape, row, col + 1):
            self.current_pos = (row, col + 1)

    def rotate(self):
        """Rotate clockwise using SRS-style rotation (transpose + reverse rows)."""
        if self.game_over or self.current_piece is None:
            return
        shape = self.current_piece['shape']
        # Transpose and reverse each row for clockwise rotation
        n = len(shape)
        rotated = [[shape[n - 1 - c][r] for c in range(n)] for r in range(n)]

        row, col = self.current_pos

        # Try basic rotation first
        if self._is_valid_position(rotated, row, col):
            self.current_piece['shape'] = rotated
            return

        # Wall kick attempts: try shifting left/right/up
        kicks = [(0, -1), (0, -2), (0, 1), (0, 2), (-1, 0), (-1, -1), (-1, 1), (-2, 0)]
        for dr, dc in kicks:
            if self._is_valid_position(rotated, row + dr, col + dc):
                self.current_piece['shape'] = rotated
                self.current_pos = (row + dr, col + dc)
                return

    def soft_drop(self, active):
        self.soft_dropping = active

    def hard_drop(self):
        """Instantly drop the piece to the lowest valid position."""
        if self.game_over or self.current_piece is None:
            return
        shape = self.current_piece['shape']
        row, col = self.current_pos
        drop_distance = 0
        while self._is_valid_position(shape, row + 1, col):
            row += 1
            drop_distance += 1
        self.current_pos = (row, col)
        self.score += drop_distance * SOFT_DROP_BONUS * 2  # hard drop bonus
        self._lock_piece()

    def _lock_piece(self):
        """Lock the current piece onto the board."""
        if self.current_piece is None:
            return
        shape = self.current_piece['shape']
        color = self.current_piece['color']
        row, col = self.current_pos

        for r in range(len(shape)):
            for c in range(len(shape[r])):
                if shape[r][c]:
                    board_r = row + r
                    board_c = col + c
                    if 0 <= board_r < self.total_rows and 0 <= board_c < GRID_COLS:
                        self.board[board_r][board_c] = color

        # Check for completed lines
        self._clear_lines()
        # Spawn next piece
        self._spawn_piece()

    def _clear_lines(self):
        """Find and clear completed horizontal rows."""
        cleared = 0
        new_board = []
        for r in range(self.total_rows):
            if all(self.board[r][c] is not None for c in range(GRID_COLS)):
                cleared += 1
            else:
                new_board.append(self.board[r])
        # Add empty rows at top for each cleared line
        for _ in range(cleared):
            new_board.insert(0, [None for _ in range(GRID_COLS)])
        self.board = new_board

        if cleared > 0:
            # Update score
            self.score += SCORE_TABLE.get(cleared, cleared * 200)
            self.lines_cleared += cleared
            # Update level
            new_level = self.lines_cleared // LINES_PER_LEVEL + 1
            if new_level > self.level:
                self.level = new_level
                self.fall_speed = max(MIN_SPEED, INITIAL_SPEED - (self.level - 1) * SPEED_DECREMENT)

    def update(self, dt):
        """Update game state. dt is milliseconds elapsed."""
        if self.game_over or self.current_piece is None:
            return

        effective_speed = self.fall_speed
        if self.soft_dropping:
            effective_speed = max(50, self.fall_speed // 10)

        self.fall_timer += dt
        while self.fall_timer >= effective_speed:
            self.fall_timer -= effective_speed
            locked = self._move_down()
            if locked:
                # Piece was locked and new piece spawned; reset timer to avoid
                # immediately moving the new piece
                self.fall_timer = 0
                break

    def _move_down(self):
        """Move piece down by one row. Lock if it cannot move.
        Returns True if the piece was locked (new piece spawned or game over)."""
        if self.game_over or self.current_piece is None:
            return False
        shape = self.current_piece['shape']
        row, col = self.current_pos
        if self._is_valid_position(shape, row + 1, col):
            self.current_pos = (row + 1, col)
            if self.soft_dropping:
                self.score += SOFT_DROP_BONUS
            return False
        else:
            self._lock_piece()
            return True

    def get_ghost_position(self):
        """Return the row,col where the piece would land."""
        if self.current_piece is None:
            return None
        shape = self.current_piece['shape']
        row, col = self.current_pos
        while self._is_valid_position(shape, row + 1, col):
            row += 1
        return (row, col)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        self.tetris = Tetris()
        self.running = True

    def draw_cell(self, x, y, color, size=CELL_SIZE, border=True):
        """Draw a single cell with a 3D-ish border effect."""
        rect = pygame.Rect(x, y, size, size)
        # Fill
        pygame.draw.rect(self.screen, color, rect)
        # Highlight (top-left edges)
        lighter = tuple(min(255, c + 60) for c in color)
        darker = tuple(max(0, c - 60) for c in color)
        if border:
            pygame.draw.line(self.screen, lighter, (x, y), (x + size - 1, y), 2)
            pygame.draw.line(self.screen, lighter, (x, y), (x, y + size - 1), 2)
            pygame.draw.line(self.screen, darker, (x + size - 1, y), (x + size - 1, y + size - 1), 2)
            pygame.draw.line(self.screen, darker, (x, y + size - 1), (x + size - 1, y + size - 1), 2)

    def draw_board(self):
        # Board background
        board_rect = pygame.Rect(BOARD_X - 2, BOARD_Y - 2,
                                 GRID_COLS * CELL_SIZE + 4,
                                 GRID_ROWS * CELL_SIZE + 4)
        pygame.draw.rect(self.screen, WHITE, board_rect, 2)

        # Draw grid lines
        for r in range(GRID_ROWS + 1):
            y = BOARD_Y + r * CELL_SIZE
            pygame.draw.line(self.screen, DARK_GRAY, (BOARD_X, y),
                             (BOARD_X + GRID_COLS * CELL_SIZE, y), 1)
        for c in range(GRID_COLS + 1):
            x = BOARD_X + c * CELL_SIZE
            pygame.draw.line(self.screen, DARK_GRAY, (x, BOARD_Y),
                             (x, BOARD_Y + GRID_ROWS * CELL_SIZE), 1)

        # Draw locked cells (only visible rows)
        for r in range(HIDDEN_ROWS, self.tetris.total_rows):
            for c in range(GRID_COLS):
                color = self.tetris.board[r][c]
                if color is not None:
                    draw_r = r - HIDDEN_ROWS
                    self.draw_cell(BOARD_X + c * CELL_SIZE,
                                   BOARD_Y + draw_r * CELL_SIZE,
                                   color)

    def draw_piece(self, shape, color, board_row, board_col, ghost=False):
        """Draw a piece shape at a given board position."""
        for r in range(len(shape)):
            for c in range(len(shape[r])):
                if shape[r][c]:
                    draw_r = board_row + r - HIDDEN_ROWS
                    draw_c = board_col + c
                    if draw_r >= 0:  # Only draw visible rows
                        if ghost:
                            # Draw ghost as outline
                            x = BOARD_X + draw_c * CELL_SIZE
                            y = BOARD_Y + draw_r * CELL_SIZE
                            rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                            pygame.draw.rect(self.screen, color, rect, 2)
                        else:
                            self.draw_cell(BOARD_X + draw_c * CELL_SIZE,
                                           BOARD_Y + draw_r * CELL_SIZE,
                                           color)

    def draw_current_piece(self):
        if self.tetris.current_piece is None:
            return

        # Draw ghost piece first
        ghost_pos = self.tetris.get_ghost_position()
        if ghost_pos:
            ghost_row, ghost_col = ghost_pos
            # Only draw ghost if different from current position
            cur_row, cur_col = self.tetris.current_pos
            if ghost_row != cur_row:
                self.draw_piece(self.tetris.current_piece['shape'],
                                self.tetris.current_piece['color'],
                                ghost_row, ghost_col, ghost=True)

        # Draw actual piece
        row, col = self.tetris.current_pos
        self.draw_piece(self.tetris.current_piece['shape'],
                        self.tetris.current_piece['color'],
                        row, col)

    def draw_preview(self):
        """Draw the next piece preview panel."""
        if self.tetris.next_piece_name is None:
            return

        # Panel background
        panel_w = 160
        panel_h = 120
        pygame.draw.rect(self.screen, DARK_GRAY,
                         (PREVIEW_X - 5, PREVIEW_Y - 5, panel_w, panel_h))
        pygame.draw.rect(self.screen, WHITE,
                         (PREVIEW_X - 5, PREVIEW_Y - 5, panel_w, panel_h), 2)

        # Label
        label = self.font_small.render("NEXT", True, WHITE)
        self.screen.blit(label, (PREVIEW_X + 5, PREVIEW_Y - 30))

        shape = TETROMINOES[self.tetris.next_piece_name]['shape']
        color = TETROMINOES[self.tetris.next_piece_name]['color']

        # Center the piece in the preview
        piece_pixel_w = len(shape[0]) * PREVIEW_CELL_SIZE
        piece_pixel_h = len(shape) * PREVIEW_CELL_SIZE
        offset_x = PREVIEW_X + (panel_w - piece_pixel_w) // 2 - 5
        offset_y = PREVIEW_Y + (panel_h - piece_pixel_h) // 2 - 5

        for r in range(len(shape)):
            for c in range(len(shape[r])):
                if shape[r][c]:
                    self.draw_cell(offset_x + c * PREVIEW_CELL_SIZE,
                                   offset_y + r * PREVIEW_CELL_SIZE,
                                   color, PREVIEW_CELL_SIZE)

    def draw_score(self):
        # Score
        score_label = self.font_small.render("SCORE", True, WHITE)
        self.screen.blit(score_label, (PREVIEW_X, PREVIEW_Y + 140))
        score_val = self.font_medium.render(str(self.tetris.score), True, WHITE)
        self.screen.blit(score_val, (PREVIEW_X, PREVIEW_Y + 165))

        # Level
        level_label = self.font_small.render("LEVEL", True, WHITE)
        self.screen.blit(level_label, (PREVIEW_X, PREVIEW_Y + 210))
        level_val = self.font_medium.render(str(self.tetris.level), True, WHITE)
        self.screen.blit(level_val, (PREVIEW_X, PREVIEW_Y + 235))

        # Lines
        lines_label = self.font_small.render("LINES", True, WHITE)
        self.screen.blit(lines_label, (PREVIEW_X, PREVIEW_Y + 280))
        lines_val = self.font_medium.render(str(self.tetris.lines_cleared), True, WHITE)
        self.screen.blit(lines_val, (PREVIEW_X, PREVIEW_Y + 305))

        # Controls
        controls = [
            "← →  Move",
            "↑     Rotate",
            "↓     Soft Drop",
            "SPACE Hard Drop",
            "ESC   Quit",
        ]
        for i, text in enumerate(controls):
            ctrl = self.font_small.render(text, True, LIGHT_GRAY)
            self.screen.blit(ctrl, (PREVIEW_X, PREVIEW_Y + 370 + i * 25))

    def draw_game_over(self):
        """Draw game over overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        go_text = self.font_large.render("GAME OVER", True, WHITE)
        go_rect = go_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40))
        self.screen.blit(go_text, go_rect)

        final_score = self.font_medium.render(f"Final Score: {self.tetris.score}", True, WHITE)
        fs_rect = final_score.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(final_score, fs_rect)

        final_level = self.font_medium.render(f"Level Reached: {self.tetris.level}", True, WHITE)
        fl_rect = final_level.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        self.screen.blit(final_level, fl_rect)

        restart_text = self.font_small.render("Press R to restart or ESC to quit", True, LIGHT_GRAY)
        rs_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 110))
        self.screen.blit(restart_text, rs_rect)

    def run(self):
        # DAS (Delayed Auto Shift) for left/right movement
        das_delay = 170  # ms before auto-repeat starts
        das_repeat = 50  # ms between repeats
        left_timer = 0
        right_timer = 0
        left_held = False
        right_held = False
        left_next_repeat = 0
        right_next_repeat = 0

        while self.running:
            dt = self.clock.tick(60)  # 60 FPS

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

                    if self.tetris.game_over:
                        if event.key == pygame.K_r:
                            self.tetris = Tetris()
                            left_held = False
                            right_held = False
                            left_timer = 0
                            right_timer = 0
                        continue

                    if event.key == pygame.K_LEFT:
                        self.tetris.move_left()
                        left_held = True
                        left_timer = 0
                        left_next_repeat = das_delay
                    elif event.key == pygame.K_RIGHT:
                        self.tetris.move_right()
                        right_held = True
                        right_timer = 0
                        right_next_repeat = das_delay
                    elif event.key == pygame.K_UP:
                        self.tetris.rotate()
                    elif event.key == pygame.K_DOWN:
                        self.tetris.soft_drop(True)
                    elif event.key == pygame.K_SPACE:
                        self.tetris.hard_drop()

                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_LEFT:
                        left_held = False
                        left_timer = 0
                    elif event.key == pygame.K_RIGHT:
                        right_held = False
                        right_timer = 0
                    elif event.key == pygame.K_DOWN:
                        self.tetris.soft_drop(False)

            # Handle DAS for held left/right keys
            if left_held and not self.tetris.game_over:
                left_timer += dt
                while left_timer >= left_next_repeat:
                    self.tetris.move_left()
                    left_next_repeat += das_repeat
            if right_held and not self.tetris.game_over:
                right_timer += dt
                while right_timer >= right_next_repeat:
                    self.tetris.move_right()
                    right_next_repeat += das_repeat

            # Update game
            if not self.tetris.game_over:
                self.tetris.update(dt)

            # Draw everything
            self.screen.fill(BLACK)
            self.draw_board()
            self.draw_current_piece()
            self.draw_preview()
            self.draw_score()

            if self.tetris.game_over:
                self.draw_game_over()

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()
