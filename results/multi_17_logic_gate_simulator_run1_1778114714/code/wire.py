"""Wire class for connecting component pins."""
import math
import pygame
from config import COLOR_WIRE, COLOR_WIRE_HOT, COLOR_WIRE_PREVIEW, GRID_SPACING


class Wire:
    """A wire connecting an output pin to an input pin with orthogonal routing."""
    def __init__(self, wire_id, from_comp, from_pin, to_comp, to_pin):
        self.id = wire_id
        self.from_comp_id = from_comp.id
        self.from_pin_name = from_pin.name
        self.to_comp_id = to_comp.id
        self.to_pin_name = to_pin.name
        self.path = []  # List of (x, y) world points

    def compute_path(self, components):
        """Compute orthogonal path from source pin to target pin."""
        from_comp = None
        to_comp = None
        for c in components:
            if c.id == self.from_comp_id:
                from_comp = c
            if c.id == self.to_comp_id:
                to_comp = c

        if not from_comp or not to_comp:
            self.path = []
            return

        src = from_comp.get_pin_world_pos(self.from_pin_name)
        dst = to_comp.get_pin_world_pos(self.to_pin_name)

        if not src or not dst:
            self.path = [src or dst]
            return

        # Orthogonal routing with one bend point
        sx, sy = src
        dx, dy = dst

        # Determine bend strategy based on pin directions
        # Source pin is an output (on right side typically)
        # Target pin is an input (on left side typically)
        # Strategy: go horizontal from source, then vertical, then horizontal to target

        # Simple: use midpoint for bend
        mid_x = (sx + dx) / 2

        # Snap to grid
        mid_x = round(mid_x / GRID_SPACING) * GRID_SPACING

        path = [(sx, sy)]

        if abs(sx - dx) < GRID_SPACING:
            # Almost aligned vertically - simple vertical line
            path.append((dx, dy))
        elif abs(sy - dy) < GRID_SPACING:
            # Almost aligned horizontally - simple horizontal line
            path.append((dx, dy))
        else:
            # Two bends: horizontal to mid_x, then vertical, then horizontal
            path.append((mid_x, sy))
            path.append((mid_x, dy))
            path.append((dx, dy))

        self.path = path

    def get_segments(self):
        """Return list of (start, end) world-coord segments."""
        segs = []
        for i in range(len(self.path) - 1):
            segs.append((self.path[i], self.path[i + 1]))
        return segs

    def distance_to_point(self, wx, wy):
        """Minimum distance from world point to any segment of this wire."""
        min_dist = float('inf')
        for (x1, y1), (x2, y2) in self.get_segments():
            # Distance from point to line segment
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0 and dy == 0:
                dist = math.hypot(wx - x1, wy - y1)
            else:
                t = max(0, min(1, ((wx - x1) * dx + (wy - y1) * dy) / (dx * dx + dy * dy)))
                px = x1 + t * dx
                py = y1 + t * dy
                dist = math.hypot(wx - px, wy - py)
            min_dist = min(min_dist, dist)
        return min_dist

    def draw(self, screen, canvas, hot=False, cycle=False):
        """Draw the wire with orthogonal segments."""
        if not self.path:
            return

        color = COLOR_WIRE
        width = 2
        if hot:
            color = COLOR_WIRE_HOT
            width = 3
        elif cycle:
            color = (255, 80, 80)
            width = 3

        for i in range(len(self.path) - 1):
            sx1, sy1 = canvas.world_to_screen(self.path[i][0], self.path[i][1])
            sx2, sy2 = canvas.world_to_screen(self.path[i + 1][0], self.path[i + 1][1])
            pygame.draw.line(screen, color, (sx1, sy1), (sx2, sy2), max(1, int(width * canvas.zoom)))

    def to_dict(self):
        """Serialize to dict."""
        return {
            "from": [self.from_comp_id, self.from_pin_name],
            "to": [self.to_comp_id, self.to_pin_name],
        }

    @staticmethod
    def from_dict(data, wire_id, components):
        """Deserialize from dict."""
        from_id, from_pin = data["from"]
        to_id, to_pin = data["to"]

        from_comp = None
        to_comp = None
        from_pin_obj = None
        to_pin_obj = None

        for c in components:
            if c.id == from_id:
                from_comp = c
            if c.id == to_id:
                to_comp = c

        if from_comp:
            for p in from_comp.pins:
                if p.name == from_pin:
                    from_pin_obj = p
                    break
        if to_comp:
            for p in to_comp.pins:
                if p.name == to_pin:
                    to_pin_obj = p
                    break

        if not all([from_comp, to_comp, from_pin_obj, to_pin_obj]):
            raise ValueError(f"Invalid wire data: {data}")

        wire = Wire(wire_id, from_comp, from_pin_obj, to_comp, to_pin_obj)
        return wire
