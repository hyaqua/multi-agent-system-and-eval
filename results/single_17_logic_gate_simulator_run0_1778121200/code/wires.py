# wires.py - Wire class for connections between component pins
import pygame
from constants import *

class Wire:
    """Represents a connection from an output pin to an input pin."""
    def __init__(self, wire_id, from_comp_id, from_pin_id, to_comp_id, to_pin_id):
        self.wire_id = wire_id
        self.from_comp_id = from_comp_id
        self.from_pin_id = from_pin_id
        self.to_comp_id = to_comp_id
        self.to_pin_id = to_pin_id

    def get_path(self, components):
        """Compute orthogonal path from output pin to input pin."""
        from_comp = components.get(self.from_comp_id)
        to_comp = components.get(self.to_comp_id)
        if not from_comp or not to_comp:
            return []

        from_pin = None
        for p in from_comp.output_pins:
            if p.pin_id == self.from_pin_id:
                from_pin = p
                break
        to_pin = None
        for p in to_comp.input_pins:
            if p.pin_id == self.to_pin_id:
                to_pin = p
                break
        if not from_pin or not to_pin:
            return []

        x1, y1 = from_pin.get_world_pos(from_comp.x, from_comp.y)
        x2, y2 = to_pin.get_world_pos(to_comp.x, to_comp.y)

        # Snap endpoints to grid
        x1 = round(x1 / GRID_SIZE) * GRID_SIZE
        y1 = round(y1 / GRID_SIZE) * GRID_SIZE
        x2 = round(x2 / GRID_SIZE) * GRID_SIZE
        y2 = round(y2 / GRID_SIZE) * GRID_SIZE

        # Compute orthogonal path with grid-snapped mid points
        offset = GRID_SIZE * 3
        # Go right from source, then vertical, then to destination
        if x2 > x1:
            mid_x = max(x1 + offset, x2)
        else:
            mid_x = max(x1 + offset, x2 + offset)

        # Snap mid_x to grid
        mid_x = round(mid_x / GRID_SIZE) * GRID_SIZE

        path = [
            (x1, y1),
            (mid_x, y1),
            (mid_x, y2),
            (x2, y2),
        ]
        return path

    def hit_test(self, world_x, world_y, components, threshold=6):
        """Check if a world point is near this wire."""
        path = self.get_path(components)
        if len(path) < 2:
            return False
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i+1]
            if self._point_near_segment(world_x, world_y, x1, y1, x2, y2, threshold):
                return True
        return False

    def _point_near_segment(self, px, py, x1, y1, x2, y2, threshold):
        """Check if point is near a line segment."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return (px - x1)**2 + (py - y1)**2 <= threshold**2

        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        nearest_x = x1 + t * dx
        nearest_y = y1 + t * dy
        return (px - nearest_x)**2 + (py - nearest_y)**2 <= threshold**2

    def get_segments(self, components):
        """Get list of (x1,y1,x2,y2) segments for rendering."""
        path = self.get_path(components)
        segments = []
        for i in range(len(path) - 1):
            segments.append((path[i][0], path[i][1], path[i+1][0], path[i+1][1]))
        return segments

    def to_dict(self):
        return {
            "id": self.wire_id,
            "from_component": self.from_comp_id,
            "from_pin": self.from_pin_id,
            "to_component": self.to_comp_id,
            "to_pin": self.to_pin_id,
        }

    def render(self, screen, camera, components, highlight=False, preview=False, preview_end=None):
        """Render the wire."""
        if preview and preview_end:
            # Draw preview wire from output pin to current mouse
            from_comp = components.get(self.from_comp_id)
            if from_comp:
                from_pin = None
                for p in from_comp.output_pins:
                    if p.pin_id == self.from_pin_id:
                        from_pin = p
                        break
                if from_pin:
                    x1, y1 = from_pin.get_world_pos(from_comp.x, from_comp.y)
                    path = [(x1, y1), (x1 + GRID_SIZE*2, y1),
                            (x1 + GRID_SIZE*2, preview_end[1]), preview_end]
                    segments = []
                    for i in range(len(path)-1):
                        segments.append((path[i][0], path[i][1], path[i+1][0], path[i+1][1]))
                    color = WIRE_PREVIEW_COLOR
                    for (sx1, sy1, sx2, sy2) in segments:
                        sc1 = camera.world_to_screen(sx1, sy1)
                        sc2 = camera.world_to_screen(sx2, sy2)
                        pygame.draw.line(screen, color, sc1, sc2, max(2, int(3 * camera.zoom)))
                    return

        segments = self.get_segments(components)
        color = WIRE_HIGHLIGHT_COLOR if highlight else WIRE_COLOR
        for (x1, y1, x2, y2) in segments:
            sc1 = camera.world_to_screen(x1, y1)
            sc2 = camera.world_to_screen(x2, y2)
            pygame.draw.line(screen, color, sc1, sc2, max(2, int(3 * camera.zoom)))
