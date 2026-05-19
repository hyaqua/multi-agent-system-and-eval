"""Game class orchestrating game state, input, and timing."""

import random

import pygame
import settings
from grid import Grid
from pieces import Piece, PIECE_TYPES


class Game:
    """Main game controller."""

    def __init__(self):
        self.grid = Grid()
        self.score = 0
        self.level = 0
        self.total_lines_cleared = 0
        self.game_over = False

        self.current_piece = None
        self.current_color = None
        self.next_piece_type = None

        self.fall_timer = 0.0
        self.soft_drop = False

        self._spawn_piece()

    def _spawn_piece(self):
        """Spawn the next piece at the top of the grid. If no next piece, generate one."""
        if self.next_piece_type is None:
            self.next_piece_type = random.choice(PIECE_TYPES)

        piece_type = self.next_piece_type
        self.next_piece_type = random.choice(PIECE_TYPES)

        # Spawn centered at top
        col = (settings.GRID_WIDTH // 2) - 1
        row = 0  # start at the top of the visible area

        new_piece = Piece(piece_type, row=row, col=col, rotation=0)
        self.current_piece = new_piece
        self.current_color = settings.PIECE_COLORS[piece_type]

        if not self.grid.is_valid(new_piece):
            # Check if piece can be placed at spawn; if not, game over
            self.game_over = True

    def handle_input(self, event):
        """Process a pygame event for piece movement."""
        if self.game_over:
            return

        if event.type == pygame.KEYDOWN:
            key = event.key
            if key in (pygame.K_LEFT, pygame.K_a):
                self._try_move(0, -1)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self._try_move(0, 1)
            elif key in (pygame.K_UP, pygame.K_w):
                self._try_rotate()
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.soft_drop = True
            elif key == pygame.K_SPACE:
                self._hard_drop()
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.soft_drop = False

    def _try_move(self, dr: int, dc: int):
        """Try to move current piece; apply if valid."""
        if self.current_piece is None:
            return
        moved = self.current_piece.move(dr, dc)
        if self.grid.is_valid(moved):
            self.current_piece = moved

    def _try_rotate(self):
        """Try to rotate current piece clockwise with basic wall kicks."""
        if self.current_piece is None:
            return
        rotated = self.current_piece.rotated(1)
        # Try original position
        if self.grid.is_valid(rotated):
            self.current_piece = rotated
            return
        # Wall kick: try shifting left/right by 1 or 2
        for dc in (-1, 1, -2, 2):
            kicked = rotated.move(0, dc)
            if self.grid.is_valid(kicked):
                self.current_piece = kicked
                return
        # Also try shifting up
        for dr in (-1, -2):
            kicked = rotated.move(dr, 0)
            if self.grid.is_valid(kicked):
                self.current_piece = kicked
                return

    def _hard_drop(self):
        """Instantly drop piece to the lowest valid position and lock it."""
        if self.current_piece is None:
            return
        while True:
            moved = self.current_piece.move(1, 0)
            if self.grid.is_valid(moved):
                self.current_piece = moved
            else:
                break
        self._lock_piece()

    def _lock_piece(self):
        """Lock the current piece onto the grid, clear lines, spawn next."""
        if self.current_piece is None:
            return

        self.grid.lock(self.current_piece, self.current_color)

        lines = self.grid.clear_lines()
        if lines > 0:
            self.total_lines_cleared += lines
            points = settings.SCORE_TABLE.get(lines, lines * 100)
            self.score += points
            # Update level
            self.level = self.total_lines_cleared // settings.LINES_PER_LEVEL

        self.current_piece = None
        self.current_color = None
        self._spawn_piece()

    def update(self, dt: float):
        """Update game state given delta time in seconds."""
        if self.game_over:
            return
        if self.current_piece is None:
            return

        # Determine drop interval
        interval = settings.SOFT_DROP_INTERVAL if self.soft_drop else self._get_drop_interval()
        self.fall_timer += dt * 1000  # convert to ms

        if self.fall_timer >= interval:
            self.fall_timer = 0.0
            moved = self.current_piece.move(1, 0)
            if self.grid.is_valid(moved):
                self.current_piece = moved
            else:
                self._lock_piece()

    def _get_drop_interval(self) -> float:
        """Calculate drop interval based on level."""
        interval = settings.BASE_DROP_INTERVAL - self.level * settings.SPEED_DECREASE
        return max(settings.MIN_DROP_INTERVAL, interval)

    def get_state(self) -> dict:
        """Return a dict of drawable state for the display module."""
        piece_cells = []
        if self.current_piece is not None:
            piece_cells = [(r, c, self.current_color) for r, c in self.current_piece.cells()]

        # Ghost piece (where piece would land)
        ghost_cells = []
        if self.current_piece is not None and not self.game_over:
            ghost = self.current_piece.clone()
            while True:
                moved = ghost.move(1, 0)
                if self.grid.is_valid(moved):
                    ghost = moved
                else:
                    break
            if ghost.row != self.current_piece.row:
                ghost_color = tuple(max(0, c // 3) for c in self.current_color)  # dimmer version
                ghost_cells = [(r, c, ghost_color) for r, c in ghost.cells()]

        # Grid cells
        grid_cells = []
        for row in range(settings.GRID_HEIGHT):
            for col in range(settings.GRID_WIDTH):
                color = self.grid.get_cell(row, col)
                if color is not None:
                    grid_cells.append((row, col, color))

        # Next piece preview
        next_cells = []
        if self.next_piece_type is not None:
            offsets = Piece(self.next_piece_type).cells()  # Preview in rotation 0
            next_cells = list(offsets)
            next_color = settings.PIECE_COLORS[self.next_piece_type]
        else:
            next_color = None

        return {
            'grid_cells': grid_cells,
            'piece_cells': piece_cells,
            'ghost_cells': ghost_cells,
            'next_cells': next_cells,
            'next_color': next_color,
            'score': self.score,
            'level': self.level,
            'lines': self.total_lines_cleared,
            'game_over': self.game_over,
        }

    def reset(self):
        """Reset game state."""
        self.grid.reset()
        self.score = 0
        self.level = 0
        self.total_lines_cleared = 0
        self.game_over = False
        self.current_piece = None
        self.current_color = None
        self.next_piece_type = None
        self.fall_timer = 0.0
        self.soft_drop = False
        self._spawn_piece()
