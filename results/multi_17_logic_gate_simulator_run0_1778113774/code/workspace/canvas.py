"""Camera and canvas rendering for infinite grid."""

import pygame
from constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GRID_SPACING,
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP,
    COLOR_BG, COLOR_GRID_DOT,
)


class Camera:
    """Handles world/screen coordinate transforms, pan, zoom."""

    def __init__(self):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = 1.0

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert world coordinates to screen coordinates."""
        sx = (wx + self.offset_x) * self.zoom + WINDOW_WIDTH / 2
        sy = (wy + self.offset_y) * self.zoom + WINDOW_HEIGHT / 2
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert screen coordinates to world coordinates."""
        wx = (sx - WINDOW_WIDTH / 2) / self.zoom - self.offset_x
        wy = (sy - WINDOW_HEIGHT / 2) / self.zoom - self.offset_y
        return wx, wy

    def pan(self, dx: float, dy: float):
        """Pan by screen delta, adjusting for zoom."""
        self.offset_x += dx / self.zoom
        self.offset_y += dy / self.zoom

    def zoom_at(self, sx: float, sy: float, direction: float):
        """Zoom centered on screen point (sx, sy)."""
        old_zoom = self.zoom
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom + direction * ZOOM_STEP))
        if old_zoom == self.zoom:
            return
        # Adjust offset so that (sx, sy) stays at the same screen position
        ratio = 1.0 / self.zoom - 1.0 / old_zoom
        self.offset_x -= (sx - WINDOW_WIDTH / 2) * ratio
        self.offset_y -= (sy - WINDOW_HEIGHT / 2) * ratio

    def get_visible_world_rect(self) -> tuple[float, float, float, float]:
        """Return visible world rectangle (left, top, right, bottom)."""
        left, top = self.screen_to_world(0, 0)
        right, bottom = self.screen_to_world(WINDOW_WIDTH, WINDOW_HEIGHT)
        return left, top, right, bottom


def draw_grid(surface: pygame.Surface, camera: Camera):
    """Draw dot grid background."""
    surface.fill(COLOR_BG)

    left, top, right, bottom = camera.get_visible_world_rect()
    gs = GRID_SPACING

    # Snap to grid
    start_x = int(left // gs) * gs
    start_y = int(top // gs) * gs
    end_x = int(right // gs + 1) * gs
    end_y = int(bottom // gs + 1) * gs

    dot_radius = max(1, int(1.5 * camera.zoom))
    if camera.zoom < 0.3:
        # Skip drawing many dots at very low zoom
        step = gs * max(1, int(1 / camera.zoom / 2))
    else:
        step = gs

    for wx in range(start_x, end_x + step, step):
        for wy in range(start_y, end_y + step, step):
            sx, sy = camera.world_to_screen(wx, wy)
            if 0 <= sx <= WINDOW_WIDTH and 0 <= sy <= WINDOW_HEIGHT:
                pygame.draw.circle(surface, COLOR_GRID_DOT, (int(sx), int(sy)), dot_radius)


def snap_to_grid(value: float) -> float:
    """Snap a world coordinate to the nearest grid point."""
    return round(value / GRID_SPACING) * GRID_SPACING
