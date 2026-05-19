"""Wire class for connecting output pins to input pins with orthogonal routing."""

from __future__ import annotations

import math
import pygame
from typing import Optional, TYPE_CHECKING

from config import (
    GRID_SIZE, COLOR_WIRE, COLOR_WIRE_HIGH, COLOR_WIRE_LOW,
    COLOR_WIRE_ERROR, COLOR_WIRE_PREVIEW,
)
from pins import OutputPin, InputPin

if TYPE_CHECKING:
    from camera import Camera


def snap_to_grid(value: float) -> float:
    """Snap a coordinate to the nearest grid point."""
    return round(value / GRID_SIZE) * GRID_SIZE


class Wire:
    """A connection from an output pin to an input pin with orthogonally routed waypoints."""

    def __init__(self, start_pin: OutputPin, end_pin: InputPin, waypoints: Optional[list] = None):
        self.start_pin = start_pin
        self.end_pin = end_pin
        self.has_cycle_error: bool = False

        if waypoints is not None:
            self.waypoints = [pygame.Vector2(p) for p in waypoints]
        else:
            self.waypoints = self._compute_route()

        # Register with pins
        self.start_pin.wires.append(self)
        self.end_pin.wire = self

    def _compute_route(self) -> list[pygame.Vector2]:
        """Compute an orthogonal path from start pin to end pin."""
        start = self.start_pin.world_pos
        end = self.end_pin.world_pos
        waypoints = [start.copy()]

        # Determine directions
        # Output pins are typically on the right side, so exit right
        # Input pins are typically on the left side, so enter from left
        exit_dir = 1  # right
        entry_dir = -1  # left

        # Override based on actual positions
        if start.x > end.x:
            # Output is to the right of input - need different routing
            pass

        # Standard routing: exit right from start, then vertical, then enter from left
        mid_x = (start.x + end.x) / 2
        mid_x = snap_to_grid(mid_x)

        # Ensure mid_x is to the right of start and left of end
        if mid_x <= start.x + GRID_SIZE:
            mid_x = start.x + GRID_SIZE * 2
        if mid_x >= end.x - GRID_SIZE:
            mid_x = end.x - GRID_SIZE * 2

        # If mid_x doesn't make sense, use a simpler route
        if mid_x <= start.x or mid_x >= end.x:
            # Route: start -> go right a bit -> go vertically -> go to end
            mid_x = start.x + GRID_SIZE * 2

        waypoints.append(pygame.Vector2(mid_x, start.y))
        waypoints.append(pygame.Vector2(mid_x, end.y))
        waypoints.append(end.copy())

        return waypoints

    def recompute_route(self):
        """Recompute the route based on current pin positions."""
        self.waypoints = self._compute_route()

    def get_segments(self) -> list[tuple[pygame.Vector2, pygame.Vector2]]:
        """Return list of line segments (start, end) making up the wire."""
        segments = []
        pts = self.waypoints
        for i in range(len(pts) - 1):
            segments.append((pts[i], pts[i + 1]))
        return segments

    def get_value(self) -> bool:
        """Get the logic value this wire carries."""
        return self.start_pin.value

    def render(self, screen: pygame.Surface, camera: 'Camera', preview: bool = False):
        """Render the wire on screen."""
        if preview:
            color = COLOR_WIRE_PREVIEW
        elif self.has_cycle_error:
            color = COLOR_WIRE_ERROR
        elif self.get_value():
            color = COLOR_WIRE_HIGH
        else:
            color = COLOR_WIRE_LOW

        pts = self.waypoints
        for i in range(len(pts) - 1):
            p1 = camera.world_to_screen(pts[i])
            p2 = camera.world_to_screen(pts[i + 1])
            pygame.draw.line(screen, color, (int(p1.x), int(p1.y)),
                             (int(p2.x), int(p2.y)), 2)

    def hit_test(self, screen_pos: tuple, camera: 'Camera') -> bool:
        """Check if a screen position is near any segment of this wire."""
        threshold = 8  # pixels
        for seg_start, seg_end in self.get_segments():
            p1 = camera.world_to_screen(seg_start)
            p2 = camera.world_to_screen(seg_end)
            if self._point_near_segment(screen_pos, p1, p2, threshold):
                return True
        return False

    @staticmethod
    def _point_near_segment(point, a, b, threshold) -> bool:
        """Check if point is within threshold distance of line segment ab."""
        px, py = point
        ax, ay = a.x, a.y
        bx, by = b.x, b.y

        dx = bx - ax
        dy = by - ay
        length_sq = dx * dx + dy * dy

        if length_sq == 0:
            return math.hypot(px - ax, py - ay) <= threshold

        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        closest_x = ax + t * dx
        closest_y = ay + t * dy
        return math.hypot(px - closest_x, py - closest_y) <= threshold

    def disconnect(self):
        """Remove this wire from its pins."""
        if self in self.start_pin.wires:
            self.start_pin.wires.remove(self)
        if self.end_pin.wire == self:
            self.end_pin.wire = None
