"""Wire class for connecting component pins."""

import pygame
from constants import (
    GRID_SPACING, COLOR_WIRE_LOW, COLOR_WIRE_HIGH, COLOR_WIRE_CYCLE, COLOR_WIRE_PREVIEW,
)


class Wire:
    """Represents a connection between an output pin and an input pin."""

    def __init__(self, from_component_id: str, from_pin_id: str,
                 to_component_id: str, to_pin_id: str,
                 points: list[tuple[float, float]] | None = None):
        self.from_comp_id = from_component_id
        self.from_pin_id = from_pin_id
        self.to_comp_id = to_component_id
        self.to_pin_id = to_pin_id
        self._state = False
        self.in_cycle = False
        # Orthogonal routing points (world coords): start, mid1, mid2, ..., end
        self.points: list[tuple[float, float]] = points if points else []

    def set_state(self, state: bool):
        """Set the wire signal state."""
        self._state = state

    def get_state(self) -> bool:
        """Get the current signal state."""
        return self._state

    def update_routing(self, from_world: tuple[float, float], to_world: tuple[float, float]):
        """Compute orthogonal routing between two world points."""
        x1, y1 = from_world
        x2, y2 = to_world

        # Simple orthogonal routing: go horizontal then vertical
        # with one corner point
        points = []

        # Start point
        points.append((x1, y1))

        # Choose routing based on relative positions
        dx = x2 - x1
        dy = y2 - y1

        # If the points are already aligned, just a straight line
        if abs(dx) < GRID_SPACING or abs(dy) < GRID_SPACING:
            points.append((x2, y2))
        else:
            # Route: horizontal first then vertical
            # Snap to grid for neat routing
            mid_x = x1 + dx / 2
            mid_x = round(mid_x / GRID_SPACING) * GRID_SPACING

            points.append((mid_x, y1))
            points.append((mid_x, y2))
            points.append((x2, y2))

        self.points = points

    def draw(self, surface: pygame.Surface, camera, preview: bool = False):
        """Draw the wire with appropriate color."""
        if not self.points:
            return

        # Convert world points to screen points
        screen_pts = []
        for wx, wy in self.points:
            sx, sy = camera.world_to_screen(wx, wy)
            screen_pts.append((int(sx), int(sy)))

        if len(screen_pts) < 2:
            return

        # Choose color
        if preview:
            color = COLOR_WIRE_PREVIEW
        elif self.in_cycle:
            color = COLOR_WIRE_CYCLE
        elif self._state:
            color = COLOR_WIRE_HIGH
        else:
            color = COLOR_WIRE_LOW

        # Draw lines
        width = max(2, int(3 * camera.zoom))
        pygame.draw.lines(surface, color, False, screen_pts, width)

    def hit_test(self, world_x: float, world_y: float, tolerance: float = 8) -> bool:
        """Check if a world point is near this wire."""
        if not self.points:
            return False

        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]

            # Distance from point to line segment
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0 and dy == 0:
                dist = ((world_x - x1) ** 2 + (world_y - y1) ** 2) ** 0.5
            else:
                t = max(0, min(1, ((world_x - x1) * dx + (world_y - y1) * dy) / (dx * dx + dy * dy)))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                dist = ((world_x - proj_x) ** 2 + (world_y - proj_y) ** 2) ** 0.5

            if dist <= tolerance:
                return True
        return False

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "from": {"component": self.from_comp_id, "pin": self.from_pin_id},
            "to": {"component": self.to_comp_id, "pin": self.to_pin_id},
            "points": [[x, y] for x, y in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Wire":
        """Create Wire from dictionary."""
        points = [(p[0], p[1]) for p in data.get("points", [])]
        return cls(
            from_component_id=data["from"]["component"],
            from_pin_id=data["from"]["pin"],
            to_component_id=data["to"]["component"],
            to_pin_id=data["to"]["pin"],
            points=points,
        )
