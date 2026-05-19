"""
Board (grid) state, collision detection, line clearing.
"""

from constants import COLS, ROWS, BLACK


class Board:
    """Represents the locked-down blocks on the play field."""

    def __init__(self):
        # Grid: ROWS x COLS, each cell is either BLACK (empty) or a colour tuple.
        self.grid = [[BLACK for _ in range(COLS)] for _ in range(ROWS)]

    def is_valid_position(self, shape, offset_x, offset_y):
        """Check whether *shape* placed at (offset_x, offset_y) collides with
        walls, floor, or locked blocks.  Returns True if the position is free."""
        for r, row in enumerate(shape):
            for c, value in enumerate(row):
                if not value:
                    continue
                board_x = offset_x + c
                board_y = offset_y + r

                # Horizontal bounds
                if board_x < 0 or board_x >= COLS:
                    return False
                # Allow pieces to be partially above the top of the board
                if board_y >= ROWS:
                    return False
                # If cell is within the board, check collision with locked blocks
                if board_y >= 0 and self.grid[board_y][board_x] != BLACK:
                    return False
        return True

    def lock_piece(self, piece):
        """Write the piece's cells into the board grid."""
        for board_x, board_y in piece.get_cells():
            if 0 <= board_y < ROWS and 0 <= board_x < COLS:
                self.grid[board_y][board_x] = piece.color

    def clear_lines(self):
        """Remove completed rows, shift everything down, return number cleared."""
        cleared = 0
        row = ROWS - 1
        while row >= 0:
            if all(self.grid[row][col] != BLACK for col in range(COLS)):
                # Remove this row
                del self.grid[row]
                # Insert a new empty row at the top
                self.grid.insert(0, [BLACK for _ in range(COLS)])
                cleared += 1
                # Row index stays the same because rows shifted down
            else:
                row -= 1
        return cleared

    def is_game_over(self, piece):
        """Return True if *piece* cannot be placed at its current spawn position."""
        return not self.is_valid_position(piece.shape, piece.x, piece.y)

    def reset(self):
        """Clear the entire board."""
        self.grid = [[BLACK for _ in range(COLS)] for _ in range(ROWS)]
