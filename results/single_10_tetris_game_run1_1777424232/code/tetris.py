#!/usr/bin/env python3
"""
Tetris Game - Classic Tetris implemented with Pygame.
All 7 standard tetrominoes, row clearing, scoring, level progression.
"""

import pygame
import random
import sys
import copy

# Initialize pygame
pygame.init()

# --- Constants ---
BOARD_COLS = 10
BOARD_ROWS = 20
CELL_SIZE = 30
BOARD_X = 30
BOARD_Y = 30
BOARD_WIDTH = BOARD_COLS * CELL_SIZE
BOARD_HEIGHT = BOARD_ROWS * CELL_SIZE

PREVIEW_CELL = 22
PREVIEW_X = BOARD_X + BOARD_WIDTH + 40
PREVIEW_Y = BOARD_Y + 10

SCREEN_WIDTH = 520
SCREEN_HEIGHT = 700
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
LIGHT_GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)
BORDER_COLOR = (100, 100, 100)
BG_COLOR = (20, 20, 30)
PANEL_BG = (30, 30, 40)

PIECE_COLORS = {
    'I': (0, 255, 255),    # Cyan
    'O': (255, 255, 0),    # Yellow
    'T': (160, 32, 240),   # Purple
    'S': (0, 255, 0),      # Green
    'Z': (255, 0, 0),      # Red
    'L': (255, 165, 0),    # Orange
    'J': (0, 0, 255),      # Blue
}

# Piece shapes: each piece maps to 4 rotation states (0, R, 2, L)
# Each rotation is a 2D matrix where 1 = filled cell
SHAPES = {
    'I': [
        [[0, 0, 0, 0],
         [1, 1, 1, 1],
         [0, 0, 0, 0],
         [0, 0, 0, 0]],
        [[0, 0, 1, 0],
         [0, 0, 1, 0],
         [0, 0, 1, 0],
         [0, 0, 1, 0]],
        [[0, 0, 0, 0],
         [0, 0, 0, 0],
         [1, 1, 1, 1],
         [0, 0, 0, 0]],
        [[0, 1, 0, 0],
         [0, 1, 0, 0],
         [0, 1, 0, 0],
         [0, 1, 0, 0]],
    ],
    'O': [
        [[1, 1],
         [1, 1]],
        [[1, 1],
         [1, 1]],
        [[1, 1],
         [1, 1]],
        [[1, 1],
         [1, 1]],
    ],
    'T': [
        [[0, 1, 0],
         [1, 1, 1],
         [0, 0, 0]],
        [[1, 0, 0],
         [1, 1, 0],
         [1, 0, 0]],
        [[0, 0, 0],
         [1, 1, 1],
         [0, 1, 0]],
        [[0, 0, 1],
         [0, 1, 1],
         [0, 0, 1]],
    ],
    'S': [
        [[0, 1, 1],
         [1, 1, 0],
         [0, 0, 0]],
        [[1, 0, 0],
         [1, 1, 0],
         [0, 1, 0]],
        [[0, 0, 0],
         [0, 1, 1],
         [1, 1, 0]],
        [[0, 1, 0],
         [0, 1, 1],
         [0, 0, 1]],
    ],
    'Z': [
        [[1, 1, 0],
         [0, 1, 1],
         [0, 0, 0]],
        [[0, 0, 1],
         [0, 1, 1],
         [0, 1, 0]],
        [[0, 0, 0],
         [1, 1, 0],
         [0, 1, 1]],
        [[0, 1, 0],
         [1, 1, 0],
         [1, 0, 0]],
    ],
    'L': [
        [[0, 0, 1],
         [1, 1, 1],
         [0, 0, 0]],
        [[1, 0, 0],
         [1, 1, 0],
         [1, 0, 0]],
        [[0, 0, 0],
         [1, 1, 1],
         [1, 0, 0]],
        [[1, 1, 0],
         [0, 1, 0],
         [0, 1, 0]],
    ],
    'J': [
        [[1, 0, 0],
         [1, 1, 1],
         [0, 0, 0]],
        [[1, 1, 0],
         [0, 1, 0],
         [0, 1, 0]],
        [[0, 0, 0],
         [1, 1, 1],
         [0, 0, 1]],
        [[0, 1, 0],
         [0, 1, 0],
         [1, 1, 0]],
    ],
}

# Wall kick offsets: (col_shift, row_shift) to try when rotating
# row_shift negative = up (since row increases downward)
WALL_KICKS_3 = [(0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0), (0, -2)]
WALL_KICKS_I = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, -2), (-3, 0), (3, 0)]


class BagRandomizer:
    """Random piece generator using the 7-bag system."""
    def __init__(self):
        self.bag = []

    def _refill(self):
        self.bag = ['I', 'O', 'T', 'S', 'Z', 'L', 'J']
        random.shuffle(self.bag)

    def next(self):
        if not self.bag:
            self._refill()
        return self.bag.pop()

    def peek(self):
        """See the next piece without consuming it."""
        if not self.bag:
            self._refill()
        return self.bag[-1]


class Board:
    """The Tetris playing field."""
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.grid = [[0 for _ in range(cols)] for _ in range(rows)]
        # 0 = empty, otherwise stores the piece type letter (or color)

    def is_valid_position(self, shape, row, col):
        """Check if the shape can be placed at (row, col) without collision."""
        shape_rows = len(shape)
        shape_cols = len(shape[0])
        for r in range(shape_rows):
            for c in range(shape_cols):
                if shape[r][c]:
                    board_r = row + r
                    board_c = col + c
                    if board_c < 0 or board_c >= self.cols or board_r >= self.rows:
                        return False
                    if board_r < 0:
                        continue  # Above the board is OK
                    if self.grid[board_r][board_c]:
                        return False
        return True

    def lock_piece(self, shape, row, col, piece_type):
        """Lock the piece onto the board."""
        shape_rows = len(shape)
        shape_cols = len(shape[0])
        for r in range(shape_rows):
            for c in range(shape_cols):
                if shape[r][c]:
                    board_r = row + r
                    board_c = col + c
                    if 0 <= board_r < self.rows and 0 <= board_c < self.cols:
                        self.grid[board_r][board_c] = piece_type

    def clear_rows(self):
        """Clear completed rows and return the number cleared."""
        rows_cleared = 0
        new_grid = []
        for row in range(self.rows):
            if all(self.grid[row][c] for c in range(self.cols)):
                rows_cleared += 1
            else:
                new_grid.append(self.grid[row])
        # Add empty rows at the top
        while len(new_grid) < self.rows:
            new_grid.insert(0, [0 for _ in range(self.cols)])
        self.grid = new_grid
        return rows_cleared

    def is_game_over(self, shape, row, col):
        """Check if placing shape at (row, col) means game over."""
        return not self.is_valid_position(shape, row, col)


class Piece:
    """The currently active falling piece."""
    def __init__(self, piece_type):
        self.type = piece_type
        self.rotation = 0
        self.shape = SHAPES[piece_type][0]
        self.color = PIECE_COLORS[piece_type]
        # Spawn position: centered horizontally, top of board
        self.row = 0
        self.col = (BOARD_COLS - len(self.shape[0])) // 2

    def get_shape(self):
        return self.shape

    def get_rotated_shape(self):
        """Get shape for the next rotation state (clockwise)."""
        next_rot = (self.rotation + 1) % 4
        return SHAPES[self.type][next_rot]

    def rotate(self):
        """Apply clockwise rotation."""
        self.rotation = (self.rotation + 1) % 4
        self.shape = SHAPES[self.type][self.rotation]



class TetrisGame:
    """Main game class managing all game state and logic."""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris")
        self.clock = pygame.time.Clock()

        # Initialize fonts - use default pygame font for maximum compatibility
        self.font_small = pygame.font.Font(None, 20)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_large = pygame.font.Font(None, 40)
        self.font_huge = pygame.font.Font(None, 52)

        pygame.key.set_repeat(170, 50)

        self.reset_game()

    def reset_game(self):
        """Reset all game state for a new game."""
        self.board = Board(BOARD_COLS, BOARD_ROWS)
        self.bag = BagRandomizer()
        self.score = 0
        self.level = 1
        self.total_rows_cleared = 0
        self.state = 'PLAYING'  # 'PLAYING', 'GAME_OVER', 'PAUSED'

        # Spawn the first two pieces (current and next)
        self.current_piece = Piece(self.bag.next())
        self.next_piece_type = self.bag.next()

        # Timing
        self.fall_interval = self.get_fall_interval()  # ms between gravity drops
        self.last_fall_time = pygame.time.get_ticks()
        self.last_rotate_time = 0
        self.can_rotate = True

        # Locking
        self.lock_delay = 500  # ms before piece locks after landing
        self.lock_timer = None  # Set when piece first can't move down

    def get_fall_interval(self):
        """Get gravity drop interval based on level."""
        # Starts at 800ms, decreases by 60ms per level, minimum 100ms
        return max(100, 800 - (self.level - 1) * 60)

    def get_ghost_position(self):
        """Find where the current piece would land."""
        row = self.current_piece.row
        while self.board.is_valid_position(
                self.current_piece.shape, row + 1, self.current_piece.col):
            row += 1
        return row

    def move_piece(self, dr, dc):
        """Try to move the current piece by (dr, dc). Returns True if successful."""
        new_row = self.current_piece.row + dr
        new_col = self.current_piece.col + dc
        if self.board.is_valid_position(self.current_piece.shape, new_row, new_col):
            self.current_piece.row = new_row
            self.current_piece.col = new_col
            # Update lock timer based on whether piece can now fall
            if self.board.is_valid_position(self.current_piece.shape,
                                            self.current_piece.row + 1,
                                            self.current_piece.col):
                # Piece can still fall further - reset lock
                self.lock_timer = None
            else:
                # Piece is sitting on something - start lock timer if not started
                if self.lock_timer is None:
                    self.lock_timer = pygame.time.get_ticks()
            return True
        return False

    def rotate_piece(self):
        """Try to rotate the current piece clockwise with wall kicks."""
        new_shape = self.current_piece.get_rotated_shape()
        kicks = WALL_KICKS_I if self.current_piece.type == 'I' else WALL_KICKS_3

        for dc, dr in kicks:
            new_row = self.current_piece.row + dr
            new_col = self.current_piece.col + dc
            if self.board.is_valid_position(new_shape, new_row, new_col):
                self.current_piece.shape = new_shape
                self.current_piece.rotation = (self.current_piece.rotation + 1) % 4
                self.current_piece.row = new_row
                self.current_piece.col = new_col
                # Update lock timer based on whether piece can fall after rotation
                if self.board.is_valid_position(self.current_piece.shape,
                                                self.current_piece.row + 1,
                                                self.current_piece.col):
                    self.lock_timer = None
                else:
                    if self.lock_timer is None:
                        self.lock_timer = pygame.time.get_ticks()
                return True
        return False

    def hard_drop(self):
        """Instantly drop the piece to its ghost position and lock."""
        ghost_row = self.get_ghost_position()
        drop_distance = ghost_row - self.current_piece.row
        self.current_piece.row = ghost_row
        self.score += drop_distance * 2
        self.lock_piece()

    def soft_drop(self):
        """Move piece down one row, adding score."""
        if self.move_piece(1, 0):
            self.score += 1

    def lock_piece(self):
        """Lock the current piece onto the board and spawn next."""
        self.board.lock_piece(
            self.current_piece.shape,
            self.current_piece.row,
            self.current_piece.col,
            self.current_piece.type
        )

        # Clear completed rows
        rows_cleared = self.board.clear_rows()
        if rows_cleared > 0:
            self.total_rows_cleared += rows_cleared
            # Score based on number of rows cleared at once
            scores = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += scores.get(rows_cleared, rows_cleared * 200) * self.level
            # Update level
            self.level = (self.total_rows_cleared // 10) + 1
            self.fall_interval = self.get_fall_interval()

        # Spawn next piece
        self.current_piece = Piece(self.next_piece_type)
        self.next_piece_type = self.bag.next()

        # Reset lock state
        self.lock_timer = None
        self.last_fall_time = pygame.time.get_ticks()

        # Check game over
        if not self.board.is_valid_position(
                self.current_piece.shape,
                self.current_piece.row,
                self.current_piece.col):
            self.state = 'GAME_OVER'

    def handle_input(self, events):
        """Process pygame events for the current frame."""
        for event in events:
            if event.type == pygame.QUIT:
                return False

            if self.state == 'PLAYING':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT:
                        self.move_piece(0, -1)
                    elif event.key == pygame.K_RIGHT:
                        self.move_piece(0, 1)
                    elif event.key == pygame.K_DOWN:
                        self.soft_drop()
                    elif event.key == pygame.K_UP and self.can_rotate:
                        self.rotate_piece()
                        self.can_rotate = False
                    elif event.key == pygame.K_SPACE:
                        self.hard_drop()
                    elif event.key == pygame.K_p:
                        self.state = 'PAUSED'
                    elif event.key == pygame.K_ESCAPE:
                        return False

                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_UP:
                        self.can_rotate = True

            elif self.state == 'PAUSED':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_p:
                        self.state = 'PLAYING'
                        self.last_fall_time = pygame.time.get_ticks()
                    elif event.key == pygame.K_ESCAPE:
                        return False

            elif self.state == 'GAME_OVER':
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False

        return True

    def update(self):
        """Update game state for the current frame."""
        if self.state != 'PLAYING':
            return

        now = pygame.time.get_ticks()

        # Check gravity
        if now - self.last_fall_time >= self.fall_interval:
            self.last_fall_time = now
            if not self.move_piece(1, 0):
                # Piece cannot move down - start lock timer if not started
                if self.lock_timer is None:
                    self.lock_timer = now

        # Check lock timer
        if self.lock_timer is not None:
            if now - self.lock_timer >= self.lock_delay:
                self.lock_piece()

    def draw_cell(self, x, y, color, size=CELL_SIZE, alpha=255):
        """Draw a single cell with a border effect."""
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        # Fill with color
        if alpha < 255:
            surface.fill((*color, alpha))
        else:
            surface.fill(color)
        # Inner highlight
        inner = pygame.Rect(2, 2, size - 4, size - 4)
        lighter = tuple(min(255, c + 60) for c in color)
        pygame.draw.rect(surface, lighter, inner, 1)
        # Border
        pygame.draw.rect(surface, (0, 0, 0), surface.get_rect(), 1)
        self.screen.blit(surface, (x, y))

    def draw_board(self):
        """Draw the playing field with grid and locked pieces."""
        # Board background
        board_rect = pygame.Rect(BOARD_X - 2, BOARD_Y - 2,
                                 BOARD_WIDTH + 4, BOARD_HEIGHT + 4)
        pygame.draw.rect(self.screen, BORDER_COLOR, board_rect, 2)
        pygame.draw.rect(self.screen, BLACK,
                         (BOARD_X, BOARD_Y, BOARD_WIDTH, BOARD_HEIGHT))

        # Grid lines
        for r in range(BOARD_ROWS + 1):
            y = BOARD_Y + r * CELL_SIZE
            pygame.draw.line(self.screen, DARK_GRAY,
                             (BOARD_X, y), (BOARD_X + BOARD_WIDTH, y), 1)
        for c in range(BOARD_COLS + 1):
            x = BOARD_X + c * CELL_SIZE
            pygame.draw.line(self.screen, DARK_GRAY,
                             (x, BOARD_Y), (x, BOARD_Y + BOARD_HEIGHT), 1)

        # Locked pieces
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                if self.board.grid[r][c]:
                    color = PIECE_COLORS.get(self.board.grid[r][c], WHITE)
                    x = BOARD_X + c * CELL_SIZE
                    y = BOARD_Y + r * CELL_SIZE
                    self.draw_cell(x, y, color)

    def draw_piece(self, shape, row, col, color, alpha=255, offset_x=BOARD_X, offset_y=BOARD_Y, cell_size=CELL_SIZE):
        """Draw a piece shape at the given board position."""
        shape_rows = len(shape)
        shape_cols = len(shape[0])
        for r in range(shape_rows):
            for c in range(shape_cols):
                if shape[r][c]:
                    board_r = row + r
                    board_c = col + c
                    if board_r >= 0:  # Don't draw pieces above the board
                        x = offset_x + board_c * cell_size
                        y = offset_y + board_r * cell_size
                        self.draw_cell(x, y, color, cell_size, alpha)

    def draw_ghost_piece(self):
        """Draw the ghost piece (landing preview)."""
        ghost_row = self.get_ghost_position()
        if ghost_row != self.current_piece.row:
            self.draw_piece(
                self.current_piece.shape,
                ghost_row,
                self.current_piece.col,
                self.current_piece.color,
                alpha=60
            )

    def draw_preview(self):
        """Draw the next piece preview panel."""
        # Panel header
        label = self.font_medium.render("NEXT", True, WHITE)
        self.screen.blit(label, (PREVIEW_X, PREVIEW_Y))

        # Preview box
        preview_box_x = PREVIEW_X
        preview_box_y = PREVIEW_Y + 30
        box_w = 5 * PREVIEW_CELL
        box_h = 5 * PREVIEW_CELL
        pygame.draw.rect(self.screen, BLACK,
                         (preview_box_x, preview_box_y, box_w, box_h))
        pygame.draw.rect(self.screen, BORDER_COLOR,
                         (preview_box_x, preview_box_y, box_w, box_h), 2)

        # Draw next piece centered in preview box
        shape = SHAPES[self.next_piece_type][0]
        color = PIECE_COLORS[self.next_piece_type]
        shape_h = len(shape)
        shape_w = len(shape[0])
        offset_x = preview_box_x + (box_w - shape_w * PREVIEW_CELL) // 2
        offset_y = preview_box_y + (box_h - shape_h * PREVIEW_CELL) // 2

        for r in range(shape_h):
            for c in range(shape_w):
                if shape[r][c]:
                    x = offset_x + c * PREVIEW_CELL
                    y = offset_y + r * PREVIEW_CELL
                    self.draw_cell(x, y, color, PREVIEW_CELL)

    def draw_score_panel(self):
        """Draw the score, level, and rows cleared."""
        y = PREVIEW_Y + 5 * PREVIEW_CELL + 80

        # Score
        label = self.font_small.render("SCORE", True, LIGHT_GRAY)
        self.screen.blit(label, (PREVIEW_X, y))
        y += 22
        value = self.font_medium.render(str(self.score), True, WHITE)
        self.screen.blit(value, (PREVIEW_X, y))
        y += 35

        # Level
        label = self.font_small.render("LEVEL", True, LIGHT_GRAY)
        self.screen.blit(label, (PREVIEW_X, y))
        y += 22
        value = self.font_medium.render(str(self.level), True, WHITE)
        self.screen.blit(value, (PREVIEW_X, y))
        y += 35

        # Rows
        label = self.font_small.render("ROWS", True, LIGHT_GRAY)
        self.screen.blit(label, (PREVIEW_X, y))
        y += 22
        value = self.font_medium.render(str(self.total_rows_cleared), True, WHITE)
        self.screen.blit(value, (PREVIEW_X, y))

    def draw_game_over(self):
        """Draw the game over overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2

        # Game Over text
        text = self.font_huge.render("GAME OVER", True, (255, 50, 50))
        rect = text.get_rect(center=(center_x, center_y - 70))
        self.screen.blit(text, rect)

        # Score
        text = self.font_medium.render(f"Final Score: {self.score}", True, WHITE)
        rect = text.get_rect(center=(center_x, center_y - 10))
        self.screen.blit(text, rect)

        # Level
        text = self.font_medium.render(f"Level Reached: {self.level}", True, WHITE)
        rect = text.get_rect(center=(center_x, center_y + 30))
        self.screen.blit(text, rect)

        # Rows
        text = self.font_medium.render(f"Rows Cleared: {self.total_rows_cleared}", True, WHITE)
        rect = text.get_rect(center=(center_x, center_y + 70))
        self.screen.blit(text, rect)

        # Restart prompt
        text = self.font_small.render("Press ENTER to play again  |  ESC to quit", True, LIGHT_GRAY)
        rect = text.get_rect(center=(center_x, center_y + 130))
        self.screen.blit(text, rect)

    def draw_pause(self):
        """Draw pause overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        text = self.font_huge.render("PAUSED", True, WHITE)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(text, rect)

        text = self.font_small.render("Press P to resume  |  ESC to quit", True, LIGHT_GRAY)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
        self.screen.blit(text, rect)

    def draw(self):
        """Render everything."""
        self.screen.fill(BG_COLOR)

        self.draw_board()
        self.draw_ghost_piece()

        # Draw current piece
        if self.state == 'PLAYING':
            self.draw_piece(
                self.current_piece.shape,
                self.current_piece.row,
                self.current_piece.col,
                self.current_piece.color
            )

        self.draw_preview()
        self.draw_score_panel()

        if self.state == 'GAME_OVER':
            self.draw_game_over()
        elif self.state == 'PAUSED':
            self.draw_pause()

        # Controls hint at bottom
        hint = self.font_small.render(
            "← → Move   ↑ Rotate   ↓ Soft Drop   Space Hard Drop   P Pause",
            True, LIGHT_GRAY)
        hint_rect = hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 20))
        self.screen.blit(hint, hint_rect)

        pygame.display.flip()

    def run(self):
        """Main game loop."""
        running = True
        while running:
            events = pygame.event.get()
            running = self.handle_input(events)
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == '__main__':
    game = TetrisGame()
    game.run()
