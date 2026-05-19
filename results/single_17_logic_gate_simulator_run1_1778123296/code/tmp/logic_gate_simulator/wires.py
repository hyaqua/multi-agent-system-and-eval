"""Wire management for logic gate simulator."""

from __future__ import annotations
import pygame
from typing import List, Tuple, Optional, Dict
from components import Pin, PinType, Component


class Wire:
    """Represents a connection between an output pin and an input pin."""

    def __init__(self, wire_id: str, from_pin: Pin, to_pin: Pin,
                 from_comp: Component, to_comp: Component):
        self.wire_id = wire_id
        self.from_pin = from_pin  # Output pin
        self.to_pin = to_pin  # Input pin
        self.from_comp = from_comp
        self.to_comp = to_comp
        self.error: bool = False  # Flagged during cycle detection
        self._route_points: List[Tuple[float, float]] = []

    @property
    def from_full_id(self) -> str:
        return self.from_pin.get_full_id(self.from_comp.comp_id)

    @property
    def to_full_id(self) -> str:
        return self.to_pin.get_full_id(self.to_comp.comp_id)

    def update_routing(self):
        """Compute orthogonal routing points snapped to grid."""
        start = self.from_pin.world_pos
        end = self.to_pin.world_pos

        sx, sy = start
        ex, ey = end

        GRID = 20.0  # Grid size for snapping

        # Snap start and end to grid
        sx = round(sx / GRID) * GRID
        sy = round(sy / GRID) * GRID
        ex = round(ex / GRID) * GRID
        ey = round(ey / GRID) * GRID

        points = [(sx, sy)]

        # Determine routing based on relative positions
        if abs(sx - ex) < GRID and abs(sy - ey) < GRID:
            # Very close: direct connection
            points.append((ex, ey))
        elif abs(sy - ey) <= GRID:
            # Same row: just horizontal
            mid_x = round((sx + ex) / (2 * GRID)) * GRID
            points.append((mid_x, sy))
            points.append((ex, ey))
        elif sx + GRID < ex:
            # Output is left of input: simple L-route
            mid_x = round((sx + ex) / (2 * GRID)) * GRID
            points.append((mid_x, sy))
            points.append((mid_x, ey))
            points.append((ex, ey))
        else:
            # Output is at same X or to the right of input
            # Route: go right from output, then vertical, then left to input
            route_x = max(sx, ex) + GRID * 2
            route_x = round(route_x / GRID) * GRID
            points.append((route_x, sy))
            points.append((route_x, ey))
            points.append((ex, ey))

        self._route_points = points

    def get_route_points(self) -> List[Tuple[float, float]]:
        """Return the list of world-coordinate points for rendering."""
        return self._route_points

    def contains_point(self, wx: float, wy: float, tolerance: float = 5.0) -> bool:
        """Check if a world point is near any segment of this wire."""
        pts = self._route_points
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            # Distance from point to line segment
            dist = self._point_to_segment_distance(wx, wy, x1, y1, x2, y2)
            if dist <= tolerance:
                return True
        return False

    @staticmethod
    def _point_to_segment_distance(px, py, x1, y1, x2, y2):
        """Compute minimum distance from point to line segment."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5

    def draw(self, screen: pygame.Surface, viewport):
        """Draw the wire with orthogonal routing."""
        if not self._route_points:
            self.update_routing()

        pts = self._route_points
        if len(pts) < 2:
            return

        # Determine wire color based on signal
        signal = self.from_pin.value
        if self.error:
            color = (255, 40, 40)  # Red for cycle errors
        elif signal:
            color = (40, 200, 40)  # Green for HIGH
        else:
            color = (80, 80, 80)  # Dark gray for LOW

        width = max(1, int(2.5 * viewport.zoom))

        screen_pts = []
        for wx, wy in pts:
            sx, sy = viewport.world_to_screen(wx, wy)
            screen_pts.append((int(sx), int(sy)))

        if len(screen_pts) >= 2:
            pygame.draw.lines(screen, color, False, screen_pts, width)

            # Draw small dots at corners
            dot_radius = max(1, int(2 * viewport.zoom))
            for sp in screen_pts[1:-1]:  # Corners (not endpoints)
                pygame.draw.circle(screen, color, sp, dot_radius)

    def to_dict(self) -> dict:
        """Serialize wire to dict for JSON."""
        return {
            "id": self.wire_id,
            "from_pin": self.from_full_id,
            "to_pin": self.to_full_id
        }


class WireManager:
    """Manages all wires in the circuit."""

    def __init__(self):
        self.wires: List[Wire] = []
        self._wire_counter: int = 0
        # Map from full pin ID to wire (for input pins, only one wire allowed)
        self._input_wire_map: Dict[str, Wire] = {}

    def can_connect(self, from_pin: Pin, to_pin: Pin) -> bool:
        """Check if a connection is valid:
        - from_pin must be an output pin
        - to_pin must be an input pin
        - to_pin must not already have a wire connection
        - Cannot connect a pin to itself or same component
        """
        if from_pin.pin_type != PinType.OUTPUT:
            return False
        if to_pin.pin_type != PinType.INPUT:
            return False

        # Check that input pin isn't already connected
        # We need the full ID, but we don't have component references here
        # This is handled at a higher level
        return True

    def add_wire(self, from_pin: Pin, to_pin: Pin,
                 from_comp: Component, to_comp: Component) -> Optional[Wire]:
        """Add a wire connection. Returns the Wire or None if invalid."""
        # Check if input pin already has a connection
        to_full_id = to_pin.get_full_id(to_comp.comp_id)
        if to_full_id in self._input_wire_map:
            # Already connected - replace old wire
            old_wire = self._input_wire_map[to_full_id]
            self.remove_wire(old_wire)

        # Check for duplicate (same from->to)
        for w in self.wires:
            if w.from_full_id == from_pin.get_full_id(from_comp.comp_id) and \
               w.to_full_id == to_full_id:
                return None  # Already exists

        # Validate types
        if from_pin.pin_type != PinType.OUTPUT or to_pin.pin_type != PinType.INPUT:
            return None

        wire_id = f"wire_{self._wire_counter}"
        self._wire_counter += 1
        wire = Wire(wire_id, from_pin, to_pin, from_comp, to_comp)

        # Connect pins
        from_pin.connect(to_pin)
        to_pin.connect(from_pin)

        wire.update_routing()
        self.wires.append(wire)
        self._input_wire_map[to_full_id] = wire
        return wire

    def remove_wire(self, wire: Wire):
        """Remove a wire connection."""
        if wire in self.wires:
            self.wires.remove(wire)
            wire.from_pin.disconnect(wire.to_pin)
            wire.to_pin.disconnect(wire.from_pin)

            to_full_id = wire.to_pin.get_full_id(wire.to_comp.comp_id)
            if self._input_wire_map.get(to_full_id) == wire:
                del self._input_wire_map[to_full_id]

    def remove_wires_for_component(self, comp: Component):
        """Remove all wires connected to a component."""
        to_remove = []
        for wire in self.wires:
            if wire.from_comp == comp or wire.to_comp == comp:
                to_remove.append(wire)
        for wire in to_remove:
            self.remove_wire(wire)

    def find_wire_at_world(self, wx: float, wy: float, tolerance: float = 8.0) -> Optional[Wire]:
        """Find a wire near the given world position."""
        for wire in reversed(self.wires):  # Check topmost first
            if wire.contains_point(wx, wy, tolerance):
                return wire
        return None

    def get_wire_for_input_pin(self, comp_id: str, pin: Pin) -> Optional[Wire]:
        """Get the wire connected to a specific input pin."""
        full_id = pin.get_full_id(comp_id)
        return self._input_wire_map.get(full_id)

    def update_all_routings(self):
        """Update routing for all wires."""
        for wire in self.wires:
            wire.update_routing()

    def clear(self):
        """Remove all wires."""
        for wire in list(self.wires):
            self.remove_wire(wire)
        self._input_wire_map.clear()

    def to_list(self) -> list:
        """Serialize all wires to list of dicts."""
        return [w.to_dict() for w in self.wires]
