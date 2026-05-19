"""Camera for world-to-screen coordinate transformation."""

import pygame
from config import ZOOM_MIN, ZOOM_MAX, ZOOM_STEP


class Camera:
    """Manages pan offset and zoom scale for the infinite canvas."""

    def __init__(self):
        self.offset = pygame.Vector2(0, 0)  # world offset (top-left of screen in world coords)
        self.zoom = 1.0

    def world_to_screen(self, world_pos: pygame.Vector2 | tuple) -> pygame.Vector2:
        """Convert world coordinates to screen coordinates."""
        x, y = world_pos
        sx = (x - self.offset.x) * self.zoom
        sy = (y - self.offset.y) * self.zoom
        return pygame.Vector2(sx, sy)

    def screen_to_world(self, screen_pos: pygame.Vector2 | tuple) -> pygame.Vector2:
        """Convert screen coordinates to world coordinates."""
        sx, sy = screen_pos
        wx = sx / self.zoom + self.offset.x
        wy = sy / self.zoom + self.offset.y
        return pygame.Vector2(wx, wy)

    def zoom_at_point(self, scroll_amount: float, cursor_screen: tuple):
        """Zoom in or out, keeping the world point under the cursor fixed."""
        old_world = self.screen_to_world(cursor_screen)

        if scroll_amount > 0:
            self.zoom = min(self.zoom + ZOOM_STEP, ZOOM_MAX)
        else:
            self.zoom = max(self.zoom - ZOOM_STEP, ZOOM_MIN)

        # Adjust offset so that the same world point remains under the cursor
        new_offset_x = old_world.x - cursor_screen[0] / self.zoom
        new_offset_y = old_world.y - cursor_screen[1] / self.zoom
        self.offset = pygame.Vector2(new_offset_x, new_offset_y)

    def pan(self, screen_delta: tuple):
        """Pan the camera by a screen-space delta."""
        dx, dy = screen_delta
        self.offset.x -= dx / self.zoom
        self.offset.y -= dy / self.zoom

    def get_visible_world_rect(self, screen_width: int, screen_height: int):
        """Return the world-space rectangle currently visible on screen."""
        top_left = self.screen_to_world((0, 0))
        bottom_right = self.screen_to_world((screen_width, screen_height))
        return pygame.Rect(
            top_left.x, top_left.y,
            bottom_right.x - top_left.x, bottom_right.y - top_left.y
        )
