from constants import GRID_WIDTH, GRID_HEIGHT, RIGHT


class Snake:
    """Represents the snake: its body segments, direction, and growth state."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reinitialize the snake to starting state."""
        # Start with 3 horizontal segments in the center, heading right
        cx = GRID_WIDTH // 2
        cy = GRID_HEIGHT // 2
        self.segments = [
            (cx, cy),       # head
            (cx - 1, cy),   # body
            (cx - 2, cy),   # tail
        ]
        self.direction = RIGHT
        self._grow_flag = False

    @property
    def head(self):
        """Return the (x, y) grid position of the snake's head."""
        return self.segments[0]

    @property
    def body(self):
        """Return all segments except the head."""
        return self.segments[1:]

    def set_direction(self, new_dir):
        """Change direction, preventing a 180-degree reversal."""
        # Cannot reverse: new direction must not be opposite of current
        if (new_dir[0] + self.direction[0] == 0 and
                new_dir[1] + self.direction[1] == 0):
            return  # ignore reversal
        self.direction = new_dir

    def move(self):
        """Advance the snake one cell in the current direction.
        Returns the new head position.
        Handles growth if grow() was called since last move.
        """
        dx, dy = self.direction
        hx, hy = self.head
        new_head = (hx + dx, hy + dy)

        # Insert new head at front
        self.segments.insert(0, new_head)

        if self._grow_flag:
            # Don't remove tail — snake grows by 1
            self._grow_flag = False
        else:
            self.segments.pop()

        return new_head

    def grow(self):
        """Flag that the snake should grow on the next move."""
        self._grow_flag = True

    def check_self_collision(self):
        """Return True if the head overlaps any body segment."""
        return self.head in self.body
