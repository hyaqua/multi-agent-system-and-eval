"""Viewport/Camera module for infinite scrollable and zoomable canvas."""

import pygame
from typing import Tuple, Optional


class Viewport:
    """Manages camera position, zoom level, and coordinate transforms."""

    def __init__(self, canvas_rect: pygame.Rect):
        self.canvas_rect = canvas_rect  # Screen area for the canvas
        self.camera_x: float = 0.0
        self.camera_y: float = 0.0
        self.zoom: float = 1.0
        self.min_zoom: float = 0.1
        self.max_zoom: float = 5.0
        self.zoom_step: float = 0.1

        # Panning state
        self.panning: bool = False
        self.pan_start_camera: Tuple[float, float] = (0, 0)
        self.pan_start_mouse: Tuple[int, int] = (0, 0)

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        """Convert screen coordinates (relative to canvas area) to world coordinates."""
        wx = self.camera_x + (sx - self.canvas_rect.x) / self.zoom
        wy = self.camera_y + (sy - self.canvas_rect.y) / self.zoom
        return wx, wy

    def world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        """Convert world coordinates to screen coordinates (relative to window)."""
        sx = (wx - self.camera_x) * self.zoom + self.canvas_rect.x
        sy = (wy - self.camera_y) * self.zoom + self.canvas_rect.y
        return sx, sy

    def world_to_screen_vec(self, world_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Convert world position tuple to screen position tuple."""
        return self.world_to_screen(world_pos[0], world_pos[1])

    def is_in_canvas(self, sx: int, sy: int) -> bool:
        """Check if screen coordinates are within the canvas area."""
        return self.canvas_rect.collidepoint(sx, sy)

    def start_pan(self, mouse_screen: Tuple[int, int]):
        """Begin panning from the given screen position."""
        self.panning = True
        self.pan_start_camera = (self.camera_x, self.camera_y)
        self.pan_start_mouse = mouse_screen

    def update_pan(self, mouse_screen: Tuple[int, int]):
        """Update camera position while panning."""
        if not self.panning:
            return
        dx = (mouse_screen[0] - self.pan_start_mouse[0]) / self.zoom
        dy = (mouse_screen[1] - self.pan_start_mouse[1]) / self.zoom
        self.camera_x = self.pan_start_camera[0] - dx
        self.camera_y = self.pan_start_camera[1] - dy

    def end_pan(self):
        """End panning."""
        self.panning = False

    def zoom_at_point(self, mouse_screen: Tuple[int, int], zoom_in: bool):
        """Zoom in or out, keeping the world point under the cursor fixed."""
        if not self.is_in_canvas(mouse_screen[0], mouse_screen[1]):
            return

        # World position under cursor before zoom
        wx, wy = self.screen_to_world(mouse_screen[0], mouse_screen[1])

        # Apply zoom
        if zoom_in:
            new_zoom = min(self.max_zoom, self.zoom + self.zoom_step)
        else:
            new_zoom = max(self.min_zoom, self.zoom - self.zoom_step)

        if new_zoom == self.zoom:
            return

        self.zoom = new_zoom

        # Adjust camera so world point stays under cursor
        self.camera_x = wx - (mouse_screen[0] - self.canvas_rect.x) / self.zoom
        self.camera_y = wy - (mouse_screen[1] - self.canvas_rect.y) / self.zoom

    def get_visible_world_rect(self) -> pygame.Rect:
        """Return the world-coordinate rectangle currently visible."""
        w = self.canvas_rect.width / self.zoom
        h = self.canvas_rect.height / self.zoom
        return pygame.Rect(self.camera_x, self.camera_y, w, h)

    def draw_grid(self, screen: pygame.Surface):
        """Draw dot-grid background on the canvas."""
        grid_spacing = 20  # World units
        visible = self.get_visible_world_rect()

        # Expand visible rect slightly for dots near edges
        margin = grid_spacing
        start_x = int(visible.x // grid_spacing) * grid_spacing - margin
        start_y = int(visible.y // grid_spacing) * grid_spacing - margin
        end_x = visible.x + visible.width + margin
        end_y = visible.y + visible.height + margin

        dot_radius = max(1, int(1.5 * self.zoom))
        if dot_radius < 1:
            dot_radius = 1

        dot_color = (180, 180, 180)
        if self.zoom < 0.5:
            dot_color = (200, 200, 200)

        x = start_x
        while x <= end_x:
            y = start_y
            while y <= end_y:
                sx, sy = self.world_to_screen(x, y)
                # Only draw if within canvas area
                if self.canvas_rect.collidepoint(sx, sy):
                    pygame.draw.circle(screen, dot_color, (int(sx), int(sy)), dot_radius)
                y += grid_spacing
            x += grid_spacing

    def apply_clip(self, screen: pygame.Surface):
        """Set clipping region to canvas area."""
        screen.set_clip(self.canvas_rect)

    def remove_clip(self, screen: pygame.Surface):
        """Remove clipping region."""
        screen.set_clip(None)
