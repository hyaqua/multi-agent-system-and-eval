# camera.py - Camera for panning and zooming
import pygame
from constants import GRID_SIZE

class Camera:
    def __init__(self, width, height, toolbar_width=0):
        self.width = width
        self.height = height
        self.toolbar_width = toolbar_width
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

    @property
    def canvas_width(self):
        return self.width - self.toolbar_width

    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates."""
        sx = (world_x + self.offset_x) * self.zoom + self.toolbar_width
        sy = (world_y + self.offset_y) * self.zoom
        return sx, sy

    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates."""
        wx = (screen_x - self.toolbar_width) / self.zoom - self.offset_x
        wy = screen_y / self.zoom - self.offset_y
        return wx, wy

    def zoom_at(self, screen_x, screen_y, factor):
        """Zoom centered on a screen position."""
        old_zoom = self.zoom
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))

        # Adjust offset to keep the point under the cursor fixed
        world_x = (screen_x - self.toolbar_width) / old_zoom - self.offset_x
        world_y = screen_y / old_zoom - self.offset_y
        self.offset_x = (screen_x - self.toolbar_width) / self.zoom - world_x
        self.offset_y = screen_y / self.zoom - world_y

    def pan(self, dx, dy):
        """Pan by screen-space delta."""
        self.offset_x += dx / self.zoom
        self.offset_y += dy / self.zoom

    def snap_to_grid(self, world_x, world_y):
        """Snap world coordinates to grid."""
        gx = round(world_x / GRID_SIZE) * GRID_SIZE
        gy = round(world_y / GRID_SIZE) * GRID_SIZE
        return gx, gy

    def get_visible_rect(self):
        """Return the world-space rectangle currently visible."""
        x1 = -self.offset_x
        y1 = -self.offset_y
        x2 = x1 + self.canvas_width / self.zoom
        y2 = y1 + self.height / self.zoom
        return (x1, y1, x2, y2)
