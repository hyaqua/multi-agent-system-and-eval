"""Component definitions for logic gate simulator."""

from __future__ import annotations
import pygame
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum, auto


class PinType(Enum):
    INPUT = auto()
    OUTPUT = auto()


class Pin:
    """Represents a single input or output pin on a component."""

    def __init__(self, pin_id: str, pin_type: PinType, local_index: int):
        self.pin_id = pin_id  # Local ID like "in_0", "out_0"
        self.pin_type = pin_type
        self.local_index = local_index  # 0-based index among pins of same type
        self.connections: List['Pin'] = []  # Connected pins
        self.value: bool = False
        self.world_pos: Tuple[float, float] = (0, 0)  # Set by component

    def connect(self, other: 'Pin'):
        """Connect this pin to another pin."""
        if other not in self.connections:
            self.connections.append(other)
        if self not in other.connections:
            other.connections.append(self)

    def disconnect(self, other: 'Pin'):
        """Disconnect from another pin."""
        if other in self.connections:
            self.connections.remove(other)
        if self in other.connections:
            other.connections.remove(self)

    def disconnect_all(self):
        """Disconnect from all pins."""
        for other in list(self.connections):
            self.disconnect(other)

    def get_full_id(self, component_id: str) -> str:
        """Return fully qualified pin ID like 'comp_id:in_0'."""
        return f"{component_id}:{self.pin_id}"


class Component:
    """Base class for all circuit components."""

    # Default dimensions
    WIDTH = 80
    HEIGHT = 60
    INPUT_PIN_COUNT = 0
    OUTPUT_PIN_COUNT = 0

    # Colors
    BODY_COLOR = (200, 210, 230)
    BORDER_COLOR = (80, 80, 120)
    SELECTED_COLOR = (60, 120, 255)
    ERROR_COLOR = (255, 40, 40)
    HIGH_COLOR = (40, 200, 40)
    LOW_COLOR = (160, 160, 160)
    PIN_COLOR = (40, 40, 40)
    PIN_HOVER_COLOR = (200, 120, 40)
    TEXT_COLOR = (20, 20, 20)

    def __init__(self, comp_id: str, x: float, y: float, label: str = ""):
        self.comp_id = comp_id
        self.x = x
        self.y = y
        self.width = self.WIDTH
        self.height = self.HEIGHT
        self.label = label
        self.config: Dict[str, Any] = {}
        self.error: bool = False  # Flagged during cycle detection

        # Create pins
        self.input_pins: List[Pin] = []
        self.output_pins: List[Pin] = []
        self._create_pins()

        # Update pin positions
        self.update_pin_positions()

    def _create_pins(self):
        """Create input and output pins."""
        for i in range(self.INPUT_PIN_COUNT):
            self.input_pins.append(Pin(f"in_{i}", PinType.INPUT, i))
        for i in range(self.OUTPUT_PIN_COUNT):
            self.output_pins.append(Pin(f"out_{i}", PinType.OUTPUT, i))

    def update_pin_positions(self):
        """Update world positions of all pins based on component position and size.
        Positions are snapped to the 20px grid with collision avoidance."""
        GRID = 20.0

        def snap_to_grid(value: float) -> float:
            return round(value / GRID) * GRID

        # Input pins along left edge
        px = snap_to_grid(self.x)
        n_inputs = len(self.input_pins)
        if n_inputs > 0:
            # Compute pin Y positions and snap to grid
            pin_ys = []
            for i in range(n_inputs):
                if n_inputs == 1:
                    py = self.y + self.height / 2
                else:
                    spacing = self.height / (n_inputs + 1)
                    py = self.y + spacing * (i + 1)
                pin_ys.append(snap_to_grid(py))

            # Fix collisions: ensure unique Y positions
            pin_ys = self._ensure_unique_positions(pin_ys, GRID)

            for i, pin in enumerate(self.input_pins):
                pin.world_pos = (px, pin_ys[i])

        # Output pins along right edge
        px = snap_to_grid(self.x + self.width)
        n_outputs = len(self.output_pins)
        if n_outputs > 0:
            pin_ys = []
            for i in range(n_outputs):
                if n_outputs == 1:
                    py = self.y + self.height / 2
                else:
                    spacing = self.height / (n_outputs + 1)
                    py = self.y + spacing * (i + 1)
                pin_ys.append(snap_to_grid(py))

            pin_ys = self._ensure_unique_positions(pin_ys, GRID)

            for i, pin in enumerate(self.output_pins):
                pin.world_pos = (px, pin_ys[i])

    @staticmethod
    def _ensure_unique_positions(ys: list, grid: float) -> list:
        """Ensure all Y positions are unique by shifting duplicates."""
        # Sort with original indices
        indexed = sorted(enumerate(ys), key=lambda x: x[1])
        result = [0.0] * len(ys)

        # First pass: assign values, shifting if needed
        last_y = None
        for orig_idx, y in indexed:
            if last_y is not None and y <= last_y:
                y = last_y + grid
            result[orig_idx] = y
            last_y = y

        return result

    def get_pin_at_world(self, wx: float, wy: float, radius: float = 10.0) -> Optional[Pin]:
        """Return the pin at the given world position, if any."""
        for pin in self.input_pins + self.output_pins:
            px, py = pin.world_pos
            dist = ((wx - px) ** 2 + (wy - py) ** 2) ** 0.5
            if dist <= radius:
                return pin
        return None

    def get_pin_by_full_id(self, full_pin_id: str) -> Optional[Pin]:
        """Get a pin by its full qualified ID (comp_id:pin_id)."""
        prefix = f"{self.comp_id}:"
        if not full_pin_id.startswith(prefix):
            return None
        local_id = full_pin_id[len(prefix):]
        for pin in self.input_pins + self.output_pins:
            if pin.pin_id == local_id:
                return pin
        return None

    def contains_point(self, wx: float, wy: float) -> bool:
        """Check if world point is inside this component's body."""
        return (self.x <= wx <= self.x + self.width and
                self.y <= wy <= self.y + self.height)

    def evaluate(self) -> None:
        """Evaluate this component's output based on inputs. Override in subclasses."""
        pass

    def get_output_value(self, index: int = 0) -> bool:
        """Get the value of an output pin."""
        if 0 <= index < len(self.output_pins):
            return self.output_pins[index].value
        return False

    def get_input_value(self, index: int = 0) -> bool:
        """Get the value of an input pin."""
        if 0 <= index < len(self.input_pins):
            return self.input_pins[index].value
        return False

    def draw(self, screen: pygame.Surface, viewport, selected: bool = False):
        """Draw this component. viewport is a Viewport instance."""
        sx, sy = viewport.world_to_screen(self.x, self.y)
        sw = self.width * viewport.zoom
        sh = self.height * viewport.zoom

        # Body
        body_rect = pygame.Rect(int(sx), int(sy), max(1, int(sw)), max(1, int(sh)))

        if self.error:
            body_color = self.ERROR_COLOR
            border_color = (180, 20, 20)
        else:
            body_color = self.BODY_COLOR
            border_color = self.SELECTED_COLOR if selected else self.BORDER_COLOR

        pygame.draw.rect(screen, body_color, body_rect, border_radius=3)
        pygame.draw.rect(screen, border_color, body_rect, width=max(1, int(2 * viewport.zoom)), border_radius=3)

        # Draw label
        font_size = max(10, int(14 * viewport.zoom))
        try:
            font = pygame.font.Font(None, font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)

        display_label = self.label if self.label else self.get_type_name()
        text_surf = font.render(display_label, True, self.TEXT_COLOR)
        text_rect = text_surf.get_rect(center=(sx + sw / 2, sy + sh / 2))
        screen.blit(text_surf, text_rect)

        # Draw pins
        self._draw_pins(screen, viewport)

        # Draw output state indicator for gates
        if self.OUTPUT_PIN_COUNT > 0 and not isinstance(self, OutputNode) and not isinstance(self, SevenSegmentDisplay):
            out_val = self.get_output_value(0)
            indicator_color = self.HIGH_COLOR if out_val else self.LOW_COLOR
            indicator_radius = max(2, int(4 * viewport.zoom))
            cx = sx + sw + indicator_radius * 2
            cy = sy + sh / 2
            pygame.draw.circle(screen, indicator_color, (int(cx), int(cy)), indicator_radius)

    def _draw_pins(self, screen: pygame.Surface, viewport):
        """Draw all pins as small circles."""
        pin_radius = max(2, int(4 * viewport.zoom))
        for pin in self.input_pins:
            psx, psy = viewport.world_to_screen(pin.world_pos[0], pin.world_pos[1])
            color = self.HIGH_COLOR if pin.value else self.PIN_COLOR
            pygame.draw.circle(screen, color, (int(psx), int(psy)), pin_radius)
            pygame.draw.circle(screen, (255, 255, 255), (int(psx), int(psy)), pin_radius, width=1)
        for pin in self.output_pins:
            psx, psy = viewport.world_to_screen(pin.world_pos[0], pin.world_pos[1])
            color = self.HIGH_COLOR if pin.value else self.PIN_COLOR
            pygame.draw.circle(screen, color, (int(psx), int(psy)), pin_radius)
            pygame.draw.circle(screen, (255, 255, 255), (int(psx), int(psy)), pin_radius, width=1)

    def get_type_name(self) -> str:
        """Return human-readable type name."""
        return type(self).__name__

    def to_dict(self) -> dict:
        """Serialize component to dict for JSON."""
        return {
            "id": self.comp_id,
            "type": self.get_type_name(),
            "x": self.x,
            "y": self.y,
            "label": self.label,
            "config": self.config.copy()
        }


class ANDGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        result = True
        for pin in self.input_pins:
            result = result and pin.value
        self.output_pins[0].value = result


class ORGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        result = False
        for pin in self.input_pins:
            result = result or pin.value
        self.output_pins[0].value = result


class NOTGate(Component):
    WIDTH = 60
    INPUT_PIN_COUNT = 1
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        self.output_pins[0].value = not self.input_pins[0].value


class NANDGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        result = True
        for pin in self.input_pins:
            result = result and pin.value
        self.output_pins[0].value = not result


class NORGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        result = False
        for pin in self.input_pins:
            result = result or pin.value
        self.output_pins[0].value = not result


class XORGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        a = self.input_pins[0].value if len(self.input_pins) > 0 else False
        b = self.input_pins[1].value if len(self.input_pins) > 1 else False
        self.output_pins[0].value = a ^ b


class XNORGate(Component):
    INPUT_PIN_COUNT = 2
    OUTPUT_PIN_COUNT = 1

    def evaluate(self):
        a = self.input_pins[0].value if len(self.input_pins) > 0 else False
        b = self.input_pins[1].value if len(self.input_pins) > 1 else False
        self.output_pins[0].value = not (a ^ b)


class InputNode(Component):
    WIDTH = 40
    HEIGHT = 40
    INPUT_PIN_COUNT = 0
    OUTPUT_PIN_COUNT = 1
    BODY_COLOR = (220, 220, 180)

    def __init__(self, comp_id: str, x: float, y: float, label: str = ""):
        super().__init__(comp_id, x, y, label)
        self.output_pins[0].value = False  # Start LOW
        self.user_toggle: bool = False

    def toggle(self):
        """Toggle between HIGH and LOW."""
        self.output_pins[0].value = not self.output_pins[0].value
        self.user_toggle = True

    def evaluate(self):
        # INPUT nodes maintain their user-set value
        # But if connected to something driving them... no, they're sources
        if not self.user_toggle:
            self.output_pins[0].value = self.output_pins[0].value  # Keep current
        pass

    def draw(self, screen: pygame.Surface, viewport, selected: bool = False):
        sx, sy = viewport.world_to_screen(self.x, self.y)
        sw = self.width * viewport.zoom
        sh = self.height * viewport.zoom
        center = (int(sx + sw / 2), int(sy + sh / 2))
        radius = max(1, int(min(sw, sh) / 2))

        color = self.HIGH_COLOR if self.output_pins[0].value else self.LOW_COLOR
        border = self.SELECTED_COLOR if selected else self.BORDER_COLOR
        if self.error:
            border = self.ERROR_COLOR

        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.circle(screen, border, center, radius, width=max(1, int(2 * viewport.zoom)))

        # Label
        font_size = max(8, int(12 * viewport.zoom))
        try:
            font = pygame.font.Font(None, font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)
        display = self.label if self.label else "IN"
        val_text = "1" if self.output_pins[0].value else "0"
        full_label = f"{display}:{val_text}"
        text_surf = font.render(full_label, True, self.TEXT_COLOR)
        text_rect = text_surf.get_rect(center=(center[0], center[1] + radius + 12 * viewport.zoom))
        screen.blit(text_surf, text_rect)

        # Draw output pin
        self._draw_pins(screen, viewport)


class OutputNode(Component):
    WIDTH = 40
    HEIGHT = 40
    INPUT_PIN_COUNT = 1
    OUTPUT_PIN_COUNT = 0
    BODY_COLOR = (220, 200, 200)

    def __init__(self, comp_id: str, x: float, y: float, label: str = ""):
        super().__init__(comp_id, x, y, label)

    def evaluate(self):
        # Output node just reads its input; nothing to compute
        pass

    def draw(self, screen: pygame.Surface, viewport, selected: bool = False):
        sx, sy = viewport.world_to_screen(self.x, self.y)
        sw = self.width * viewport.zoom
        sh = self.height * viewport.zoom
        center = (int(sx + sw / 2), int(sy + sh / 2))
        radius = max(1, int(min(sw, sh) / 2))

        input_val = self.input_pins[0].value if self.input_pins else False
        color = self.HIGH_COLOR if input_val else self.LOW_COLOR
        border = self.SELECTED_COLOR if selected else self.BORDER_COLOR
        if self.error:
            border = self.ERROR_COLOR

        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.circle(screen, border, center, radius, width=max(1, int(2 * viewport.zoom)))

        font_size = max(8, int(12 * viewport.zoom))
        try:
            font = pygame.font.Font(None, font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)
        display = self.label if self.label else "OUT"
        val_text = "1" if input_val else "0"
        full_label = f"{display}:{val_text}"
        text_surf = font.render(full_label, True, self.TEXT_COLOR)
        text_rect = text_surf.get_rect(center=(center[0], center[1] + radius + 12 * viewport.zoom))
        screen.blit(text_surf, text_rect)

        self._draw_pins(screen, viewport)


class ClockGenerator(Component):
    WIDTH = 90
    HEIGHT = 60
    INPUT_PIN_COUNT = 0
    OUTPUT_PIN_COUNT = 1
    BODY_COLOR = (210, 210, 240)

    def __init__(self, comp_id: str, x: float, y: float, label: str = ""):
        super().__init__(comp_id, x, y, label)
        self.config["frequency"] = 1.0  # Hz
        self._accumulated_time: float = 0.0
        self._current_state: bool = False
        self.output_pins[0].value = False

    @property
    def frequency(self) -> float:
        return self.config.get("frequency", 1.0)

    @frequency.setter
    def frequency(self, val: float):
        self.config["frequency"] = max(0.1, min(100.0, val))

    def update(self, dt: float):
        """Update clock state based on elapsed time."""
        if self.frequency <= 0:
            return
        period = 1.0 / self.frequency
        half_period = period / 2.0
        self._accumulated_time += dt
        while self._accumulated_time >= period:
            self._accumulated_time -= period
        self._current_state = self._accumulated_time < half_period
        self.output_pins[0].value = self._current_state

    def evaluate(self):
        # Clock is updated via update(), nothing to do here
        pass

    def draw(self, screen: pygame.Surface, viewport, selected: bool = False):
        super().draw(screen, viewport, selected)
        # Draw frequency label
        sx, sy = viewport.world_to_screen(self.x, self.y)
        sw = self.width * viewport.zoom
        sh = self.height * viewport.zoom

        font_size = max(8, int(11 * viewport.zoom))
        try:
            font = pygame.font.Font(None, font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)
        freq_text = f"{self.frequency:.1f} Hz"
        text_surf = font.render(freq_text, True, (60, 60, 160))
        text_rect = text_surf.get_rect(center=(sx + sw / 2, sy + sh * 0.75))
        screen.blit(text_surf, text_rect)


class SevenSegmentDisplay(Component):
    WIDTH = 70
    HEIGHT = 170  # Tall enough for 7 input pins on 20px grid
    INPUT_PIN_COUNT = 7  # a, b, c, d, e, f, g
    OUTPUT_PIN_COUNT = 0
    BODY_COLOR = (30, 30, 30)

    # Segment definitions: each segment is a polygon relative to (0,0) at origin
    # Standard 7-segment layout (scaled to fit WIDTH x HEIGHT)
    # We'll draw segments manually in draw()

    def __init__(self, comp_id: str, x: float, y: float, label: str = ""):
        super().__init__(comp_id, x, y, label)
        self.input_pins[0].pin_id = "in_a"
        self.input_pins[1].pin_id = "in_b"
        self.input_pins[2].pin_id = "in_c"
        self.input_pins[3].pin_id = "in_d"
        self.input_pins[4].pin_id = "in_e"
        self.input_pins[5].pin_id = "in_f"
        self.input_pins[6].pin_id = "in_g"

    def evaluate(self):
        # Nothing to compute; display is purely visual
        pass

    def _get_segment_value(self, index: int) -> bool:
        if index < len(self.input_pins):
            return self.input_pins[index].value
        return False

    def draw(self, screen: pygame.Surface, viewport, selected: bool = False):
        sx, sy = viewport.world_to_screen(self.x, self.y)
        sw = self.width * viewport.zoom
        sh = self.height * viewport.zoom

        body_rect = pygame.Rect(int(sx), int(sy), max(1, int(sw)), max(1, int(sh)))
        border_color = self.SELECTED_COLOR if selected else self.BORDER_COLOR
        if self.error:
            border_color = self.ERROR_COLOR

        pygame.draw.rect(screen, self.BODY_COLOR, body_rect, border_radius=2)
        pygame.draw.rect(screen, border_color, body_rect, width=max(1, int(2 * viewport.zoom)), border_radius=2)

        # Draw 7-segment pattern
        self._draw_segments(screen, sx, sy, sw, sh, viewport.zoom)

        # Draw label
        font_size = max(8, int(11 * viewport.zoom))
        try:
            font = pygame.font.Font(None, font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)
        display = self.label if self.label else "7SEG"
        text_surf = font.render(display, True, (200, 200, 200))
        text_rect = text_surf.get_rect(center=(sx + sw / 2, sy + sh + 10 * viewport.zoom))
        screen.blit(text_surf, text_rect)

        self._draw_pins(screen, viewport)

    def _draw_segments(self, screen, sx, sy, sw, sh, zoom):
        """Draw the 7-segment display pattern."""
        margin = 8 * zoom
        seg_width = max(2, int(4 * zoom))
        seg_length = sw * 0.45
        seg_gap = 1.5 * zoom

        # Colors
        on_color = (255, 40, 40)  # Red when ON
        off_color = (50, 20, 20)  # Dim when OFF

        # Segment positions relative to (sx, sy)
        cx = sx + sw / 2
        top_y = sy + margin
        mid_y = sy + sh / 2
        bot_y = sy + sh - margin
        left_x = sx + margin
        right_x = sx + sw - margin

        # Horizontal segments: a (top), g (middle), d (bottom)
        h_segs = [
            (0, cx, top_y),  # a - top
            (6, cx, mid_y),  # g - middle
            (3, cx, bot_y),  # d - bottom
        ]
        # Vertical segments (top half): f (left-top), b (right-top)
        # Vertical segments (bottom half): e (left-bottom), c (right-bottom)
        v_segs_top = [
            (5, left_x, top_y, mid_y),  # f - left top
            (1, right_x, top_y, mid_y),  # b - right top
        ]
        v_segs_bot = [
            (4, left_x, mid_y, bot_y),  # e - left bottom
            (2, right_x, mid_y, bot_y),  # c - right bottom
        ]

        for idx, seg_cx, seg_cy in h_segs:
            val = self._get_segment_value(idx)
            color = on_color if val else off_color
            half_len = seg_length / 2
            pts = [
                (int(seg_cx - half_len), int(seg_cy - seg_width / 2)),
                (int(seg_cx + half_len), int(seg_cy - seg_width / 2)),
                (int(seg_cx + half_len - seg_gap), int(seg_cy)),
                (int(seg_cx - half_len + seg_gap), int(seg_cy)),
            ]
            pygame.draw.polygon(screen, color, pts)

        for idx, seg_x, seg_yt, seg_yb in v_segs_top:
            val = self._get_segment_value(idx)
            color = on_color if val else off_color
            half_w = seg_width / 2
            pts = [
                (int(seg_x - half_w), int(seg_yt + seg_gap)),
                (int(seg_x + half_w), int(seg_yt + seg_gap)),
                (int(seg_x + half_w), int(seg_yb)),
                (int(seg_x - half_w), int(seg_yb)),
            ]
            pygame.draw.polygon(screen, color, pts)

        for idx, seg_x, seg_yt, seg_yb in v_segs_bot:
            val = self._get_segment_value(idx)
            color = on_color if val else off_color
            half_w = seg_width / 2
            pts = [
                (int(seg_x - half_w), int(seg_yt)),
                (int(seg_x + half_w), int(seg_yt)),
                (int(seg_x + half_w), int(seg_yb - seg_gap)),
                (int(seg_x - half_w), int(seg_yb - seg_gap)),
            ]
            pygame.draw.polygon(screen, color, pts)


# Registry of component types
COMPONENT_TYPES = {
    "ANDGate": ANDGate,
    "ORGate": ORGate,
    "NOTGate": NOTGate,
    "NANDGate": NANDGate,
    "NORGate": NORGate,
    "XORGate": XORGate,
    "XNORGate": XNORGate,
    "InputNode": InputNode,
    "OutputNode": OutputNode,
    "ClockGenerator": ClockGenerator,
    "SevenSegmentDisplay": SevenSegmentDisplay,
}

# Display names for toolbar
COMPONENT_DISPLAY_NAMES = {
    "ANDGate": "AND",
    "ORGate": "OR",
    "NOTGate": "NOT",
    "NANDGate": "NAND",
    "NORGate": "NOR",
    "XORGate": "XOR",
    "XNORGate": "XNOR",
    "InputNode": "INPUT",
    "OutputNode": "OUTPUT",
    "ClockGenerator": "CLOCK",
    "SevenSegmentDisplay": "7-SEG",
}

# Toolbar order
TOOLBAR_ORDER = [
    "InputNode", "OutputNode", "ClockGenerator",
    "ANDGate", "ORGate", "NOTGate",
    "NANDGate", "NORGate", "XORGate", "XNORGate",
    "SevenSegmentDisplay",
]


def create_component(comp_type: str, comp_id: str, x: float, y: float, label: str = "") -> Component:
    """Factory function to create a component by type name."""
    cls = COMPONENT_TYPES.get(comp_type)
    if cls is None:
        raise ValueError(f"Unknown component type: {comp_type}")
    comp = cls(comp_id, x, y, label)
    return comp


def create_component_from_dict(data: dict) -> Component:
    """Create a component from a serialized dict."""
    comp = create_component(data["type"], data["id"], data["x"], data["y"], data.get("label", ""))
    if "config" in data:
        comp.config.update(data["config"])
        # Special handling for clock frequency
        if data["type"] == "ClockGenerator" and "frequency" in data.get("config", {}):
            comp.frequency = data["config"]["frequency"]
    return comp
