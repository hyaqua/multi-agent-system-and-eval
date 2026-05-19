from settings import SCREEN_WIDTH


class Camera:
    """Handles horizontal scrolling to follow the player."""

    def __init__(self, level_width: int):
        self.offset = 0.0
        self.level_width = level_width
        self.target_offset = 0.0

    def update(self, player_rect):
        """Update camera offset to follow the player."""
        # Target: center the player horizontally
        target = player_rect.centerx - SCREEN_WIDTH // 2

        # Smooth camera movement
        self.offset += (target - self.offset) * 0.1

        # Clamp camera so it doesn't show beyond the level
        max_offset = self.level_width - SCREEN_WIDTH
        if self.offset < 0:
            self.offset = 0
        elif self.offset > max_offset:
            self.offset = max_offset

        # If level is smaller than screen, center it
        if self.level_width <= SCREEN_WIDTH:
            self.offset = (self.level_width - SCREEN_WIDTH) // 2

    def get_offset(self) -> int:
        """Return the current camera offset as an integer."""
        return int(self.offset)
