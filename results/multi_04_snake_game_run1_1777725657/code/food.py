import random
from constants import GRID_WIDTH, GRID_HEIGHT


class Food:
    """Represents a single food item on the grid."""

    def __init__(self):
        self.position = (0, 0)

    def spawn(self, snake_segments):
        """Place food at a random unoccupied grid cell.
        snake_segments: list of (x, y) tuples occupied by the snake.
        """
        occupied = set(snake_segments)

        # Build list of free cells
        free = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if (x, y) not in occupied
        ]

        if free:
            self.position = random.choice(free)
        else:
            # Snake fills the entire grid — no valid position.
            # Place at (-1, -1) so it's effectively invisible.
            self.position = (-1, -1)
