"""
Food class: spawns at a random unoccupied cell, provides its position,
and regenerates when eaten.
"""

import random
from constants import GRID_WIDTH, GRID_HEIGHT


class Food:
    """Represents a food item on the grid."""

    def __init__(self):
        self.position = [0, 0]
        # First spawn requires occupied cells; caller must call respawn

    def respawn(self, occupied_cells):
        """Place food at a random free cell.

        Args:
            occupied_cells: an iterable of (x, y) positions that cannot
                            be used (e.g., snake segments).
        """
        # Build a set of all possible positions, remove occupied ones
        all_positions = {
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
        }
        occupied = {tuple(cell) for cell in occupied_cells}
        free = all_positions - occupied

        if free:
            self.position = list(random.choice(list(free)))
        else:
            # All cells occupied (snake fills entire grid) — victory!
            # Place at (0, 0) as a fallback; game can treat as win.
            self.position = [0, 0]
