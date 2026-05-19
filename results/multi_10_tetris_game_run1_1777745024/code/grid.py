"""Grid class managing the playing field."""

from settings import GRID_WIDTH, GRID_HEIGHT


class Grid:
    """The playing field: a 2D grid of locked cells."""

    def __init__(self):
        # grid[row][col] = color or None
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

    def is_valid(self, piece) -> bool:
        """Check if the piece's cells are all within bounds and not overlapping locked cells."""
        for row, col in piece.cells():
            if col < 0 or col >= GRID_WIDTH:
                return False
            if row >= GRID_HEIGHT:
                return False
            if row < 0:
                continue  # allow above the grid
            if self.grid[row][col] is not None:
                return False
        return True

    def lock(self, piece, color):
        """Lock the piece's cells onto the grid with the given color."""
        for row, col in piece.cells():
            if 0 <= row < GRID_HEIGHT and 0 <= col < GRID_WIDTH:
                self.grid[row][col] = color

    def clear_lines(self) -> int:
        """Clear completed rows and return the number of lines cleared."""
        lines_cleared = 0
        row = GRID_HEIGHT - 1
        while row >= 0:
            if all(self.grid[row][col] is not None for col in range(GRID_WIDTH)):
                # Remove this row
                del self.grid[row]
                # Insert empty row at top
                self.grid.insert(0, [None for _ in range(GRID_WIDTH)])
                lines_cleared += 1
                # Don't decrement row — the next row shifted into this position
            else:
                row -= 1
        return lines_cleared

    def get_cell(self, row: int, col: int):
        """Return the color at (row, col) or None."""
        if 0 <= row < GRID_HEIGHT and 0 <= col < GRID_WIDTH:
            return self.grid[row][col]
        return None

    def reset(self):
        """Clear the grid."""
        self.grid = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
