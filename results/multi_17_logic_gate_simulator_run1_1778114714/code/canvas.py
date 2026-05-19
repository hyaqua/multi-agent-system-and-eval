"""Canvas class for infinite pan/zoom with dot-grid background."""
import pygame
from config import (
    COLOR_BG, COLOR_GRID_DOT, COLOR_GRID_LINE, GRID_SPACING,
    TOOLBAR_WIDTH, WINDOW_WIDTH, WINDOW_HEIGHT,
)


class Canvas:
    """Manages pan, zoom, and coordinate transforms."""
    def __init__(self, width, height, toolbar_width=TOOLBAR_WIDTH):
        self.offset_x = float(width - toolbar_width) / 2 + toolbar_width
        self.offset_y = float(height) / 2
        self.zoom = 1.0
        self.width = width
        self.height = height
        self.toolbar_width = toolbar_width
        self.canvas_rect = pygame.Rect(toolbar_width, 0, width - toolbar_width, height)

    @property
    def canvas_left(self):
        return self.toolbar_width

    def world_to_screen(self, wx, wy):
        """Convert world coordinates to screen coordinates."""
        sx = wx * self.zoom + self.offset_x
        sy = wy * self.zoom + self.offset_y
        return (sx, sy)

    def screen_to_world(self, sx, sy):
        """Convert screen coordinates to world coordinates."""
        wx = (sx - self.offset_x) / self.zoom
        wy = (sy - self.offset_y) / self.zoom
        return (wx, wy)

    def is_on_canvas(self, sx, sy):
        """Check if screen point is on the canvas area."""
        return self.canvas_rect.collidepoint(sx, sy)

    def pan(self, dx, dy):
        """Pan by screen delta."""
        self.offset_x += dx
        self.offset_y += dy

    def zoom_at(self, sx, sy, factor):
        """Zoom centered on screen point (sx, sy)."""
        # World point under cursor before zoom
        wx = (sx - self.offset_x) / self.zoom
        wy = (sy - self.offset_y) / self.zoom

        # Apply zoom
        new_zoom = self.zoom * factor
        new_zoom = max(0.1, min(5.0, new_zoom))
        self.zoom = new_zoom

        # Adjust offset to keep world point under cursor
        self.offset_x = sx - wx * self.zoom
        self.offset_y = sy - wy * self.zoom

    def draw_grid(self, screen):
        """Draw dot-grid background in world space."""
        # Calculate visible world area
        wx1, wy1 = self.screen_to_world(self.canvas_left, 0)
        wx2, wy2 = self.screen_to_world(self.width, self.height)

        step = GRID_SPACING
        if self.zoom < 0.2:
            step = GRID_SPACING * 5
        elif self.zoom < 0.5:
            step = GRID_SPACING * 2

        # Align to grid
        start_x = int(wx1 // step) * step
        start_y = int(wy1 // step) * step
        end_x = wx2 + step
        end_y = wy2 + step

        x = start_x
        while x <= end_x:
            y = start_y
            while y <= end_y:
                sx, sy = self.world_to_screen(x, y)
                if self.canvas_left <= sx <= self.width and 0 <= sy <= self.height:
                    if self.zoom > 0.6:
                        # Draw small dot
                        pygame.draw.circle(screen, COLOR_GRID_DOT, (int(sx), int(sy)), 1)
                    else:
                        pygame.draw.circle(screen, COLOR_GRID_DOT, (int(sx), int(sy)), max(1, int(self.zoom * 0.8)))
                y += step
            x += step

    def draw(self, screen):
        """Clear canvas area and draw grid."""
        screen.fill(COLOR_BG, self.canvas_rect)
        self.draw_grid(screen)
