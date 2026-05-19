"""
Core game logic: board state, piece management, collision detection,
line clearing, scoring, and speed control.
"""

from copy import deepcopy
import random
from constants import (
    COLS, ROWS, INITIAL_SPEED, SPEED_DECREMENT, MIN_SPEED,
    POINTS_PER_LINE, LINES_PER_LEVEL,
)
from pieces import PIECES, PIECE_NAMES


class Game:
    """Encapsulates all Tetris game state and rules."""

    def __init__(self):
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.fall_timer = 0.0

        # Create first two pieces
        self.current_piece = self._make_piece()
        self.next_piece = self._make_piece()
        self._spawn_piece()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_speed(self) -> float:
        """Return auto-drop interval in milliseconds for the current level."""
        speed = INITIAL_SPEED - (self.level - 1) * SPEED_DECREMENT
        return max(speed, MIN_SPEED)

    def collides(self, shape, px: int, py: int) -> bool:
        """Return True if *shape* placed at (px, py) overlaps walls or
        locked blocks."""
        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    bx = px + col_idx
                    by = py + row_idx
                    if bx < 0 or bx >= COLS or by >= ROWS:
                        return True
                    if by >= 0 and self.board[by][bx] is not None:
                        return True
        return False

    # ------------------------------------------------------------------
    # Piece movement
    # ------------------------------------------------------------------

    def move(self, dx: int, dy: int) -> bool:
        """Try to move the current piece by (dx, dy). Returns True on success."""
        shape = self.current_piece["shapes"][self.current_piece["rotation"]]
        nx = self.current_piece["x"] + dx
        ny = self.current_piece["y"] + dy
        if not self.collides(shape, nx, ny):
            self.current_piece["x"] = nx
            self.current_piece["y"] = ny
            return True
        return False

    def rotate(self) -> bool:
        """Try to rotate the current piece clockwise. Uses basic wall kicks."""
        if self.current_piece["type"] == "O":
            return False  # O never rotates

        shapes = self.current_piece["shapes"]
        old_rot = self.current_piece["rotation"]
        new_rot = (old_rot + 1) % len(shapes)
        new_shape = shapes[new_rot]
        ox, oy = self.current_piece["x"], self.current_piece["y"]

        # Wall kick offsets to try (dx, dy)
        kicks = [(0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0)]
        if self.current_piece["type"] == "I":
            kicks = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, -2)]

        for kx, ky in kicks:
            if not self.collides(new_shape, ox + kx, oy + ky):
                self.current_piece["rotation"] = new_rot
                self.current_piece["x"] = ox + kx
                self.current_piece["y"] = oy + ky
                return True
        return False

    def hard_drop(self) -> int:
        """Instant drop to the lowest valid position. Returns cells dropped."""
        dropped = 0
        while self.move(0, 1):
            dropped += 1
        self.lock_piece()
        return dropped

    def get_ghost_y(self) -> int:
        """Return the row where the current piece would land."""
        shape = self.current_piece["shapes"][self.current_piece["rotation"]]
        gy = self.current_piece["y"]
        while not self.collides(shape, self.current_piece["x"], gy + 1):
            gy += 1
        return gy

    # ------------------------------------------------------------------
    # Update loop
    # ------------------------------------------------------------------

    def update(self, dt_ms: float):
        """Advance game state by dt_ms milliseconds."""
        if self.game_over:
            return

        self.fall_timer += dt_ms
        speed = self.get_speed()
        while self.fall_timer >= speed:
            self.fall_timer -= speed
            if not self.move(0, 1):
                self.lock_piece()
                break

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_piece(self) -> dict:
        """Create a fresh random piece dict (not yet positioned)."""
        name = random.choice(PIECE_NAMES)
        info = PIECES[name]
        return {
            "type": name,
            "color": info["color"],
            "shapes": info["shapes"],
            "rotation": 0,
            "x": 0,
            "y": 0,
        }

    def _spawn_piece(self):
        """Place current_piece at the top-center of the board."""
        self.current_piece = self.next_piece
        self.next_piece = self._make_piece()

        shape = self.current_piece["shapes"][0]
        # Center horizontally
        self.current_piece["x"] = COLS // 2 - len(shape[0]) // 2
        self.current_piece["y"] = 0
        self.current_piece["rotation"] = 0

        if self.collides(shape, self.current_piece["x"], self.current_piece["y"]):
            self.game_over = True

    def lock_piece(self):
        """Write the current piece into the board, then clear lines and spawn."""
        shape = self.current_piece["shapes"][self.current_piece["rotation"]]
        color = self.current_piece["color"]
        px, py = self.current_piece["x"], self.current_piece["y"]

        for row_idx, row in enumerate(shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    bx = px + col_idx
                    by = py + row_idx
                    if 0 <= by < ROWS and 0 <= bx < COLS:
                        self.board[by][bx] = color

        self._clear_lines()
        self._spawn_piece()

    def _clear_lines(self):
        """Find and remove complete rows, then update score / level."""
        cleared = 0
        new_board = []
        for row in self.board:
            if all(cell is not None for cell in row):
                cleared += 1
            else:
                new_board.append(row)

        # Add empty rows at the top to keep ROWS constant
        for _ in range(cleared):
            new_board.insert(0, [None for _ in range(COLS)])

        self.board = new_board

        if cleared > 0:
            self.lines_cleared += cleared
            # Award points: base * level multiplier
            base = POINTS_PER_LINE.get(cleared, cleared * 200)
            self.score += base * self.level

            # Recalculate level
            self.level = self.lines_cleared // LINES_PER_LEVEL + 1
