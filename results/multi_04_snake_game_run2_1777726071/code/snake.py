"""
Snake class: manages segments, direction, movement, growth,
and self-collision detection.
"""

from constants import GRID_WIDTH, GRID_HEIGHT, INITIAL_LENGTH, INITIAL_DIRECTION


class Snake:
    """Represents the player's snake."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset snake to initial state."""
        # Head starts near the centre, body extends to the left
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.segments = []
        for i in range(INITIAL_LENGTH):
            self.segments.append([start_x - i, start_y])
        self.direction = list(INITIAL_DIRECTION)  # (dx, dy)
        self._grow_pending = False

    @property
    def head(self):
        """Return the head segment [x, y]."""
        return self.segments[0]

    def can_change_direction(self, new_dx, new_dy):
        """Prevent 180° reversal: new direction must not be opposite."""
        # Cannot reverse if new direction is exactly opposite of current
        if new_dx == -self.direction[0] and new_dy == -self.direction[1]:
            return False
        # Also ignore zero moves (no direction)
        if new_dx == 0 and new_dy == 0:
            return False
        return True

    def set_direction(self, dx, dy):
        """Set a new direction if valid."""
        if self.can_change_direction(dx, dy):
            self.direction = [dx, dy]

    def queue_growth(self):
        """Signal that the snake should grow on next move."""
        self._grow_pending = True

    def move(self):
        """Advance the snake by one cell.

        If _grow_pending is True, the tail is not removed, making the
        snake one segment longer.
        """
        dx, dy = self.direction
        new_head = [self.head[0] + dx, self.head[1] + dy]

        # Insert new head at front
        self.segments.insert(0, new_head)

        if self._grow_pending:
            self._grow_pending = False
        else:
            # Remove tail to maintain length
            self.segments.pop()

    def check_self_collision(self):
        """Return True if head collides with any other segment."""
        return self.head in self.segments[1:]

    def check_wall_collision(self):
        """Return True if head is outside grid boundaries."""
        x, y = self.head
        return x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT
