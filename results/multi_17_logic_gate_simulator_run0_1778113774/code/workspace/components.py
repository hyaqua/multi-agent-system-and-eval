"""Component definitions for logic gates and special components."""

import math
import pygame
from constants import (
    GRID_SPACING, PIN_RADIUS, PIN_HIT_TOLERANCE,
    COMPONENT_WIDTH, COMPONENT_HEIGHT,
    INPUT_NODE_SIZE, OUTPUT_NODE_SIZE, CLOCK_SIZE,
    SEVEN_SEG_WIDTH, SEVEN_SEG_HEIGHT,
    COLOR_COMPONENT_BODY, COLOR_COMPONENT_BORDER,
    COLOR_COMPONENT_HIGH, COLOR_COMPONENT_LOW,
    COLOR_PIN, COLOR_PIN_HIGHLIGHT,
    COLOR_CYCLE_HIGHLIGHT,
    COLOR_OUTPUT_LABEL, COLOR_SEGMENT_ON, COLOR_SEGMENT_OFF,
    TYPE_AND, TYPE_OR, TYPE_NOT, TYPE_NAND, TYPE_NOR, TYPE_XOR, TYPE_XNOR,
    TYPE_INPUT, TYPE_OUTPUT, TYPE_CLOCK, TYPE_SEVEN_SEG,
    DEFAULT_CLOCK_FREQ,
)
from canvas import snap_to_grid


class Pin:
    """Represents a connection point on a component."""

    def __init__(self, pin_id: str, relative_x: float, relative_y: float, is_input: bool):
        self.pin_id = pin_id
        self.rel_x = relative_x
        self.rel_y = relative_y
        self.is_input = is_input  # True = input pin, False = output pin
        self.wire = None  # For input pins: single wire reference
        self.wires: list = []  # For output pins: list of connected wires
        self.state = False  # Current HIGH/LOW state

    def get_world_pos(self, comp_x: float, comp_y: float) -> tuple[float, float]:
        """Get world position of this pin."""
        return (comp_x + self.rel_x, comp_y + self.rel_y)

    def hit_test(self, world_x: float, world_y: float,
                 comp_x: float, comp_y: float) -> bool:
        """Check if a world point hits this pin."""
        px, py = self.get_world_pos(comp_x, comp_y)
        dist = math.hypot(world_x - px, world_y - py)
        return dist <= PIN_HIT_TOLERANCE


class Component:
    """Base class for all circuit components."""

    type_name: str = "Generic"
    body_width: int = COMPONENT_WIDTH
    body_height: int = COMPONENT_HEIGHT

    def __init__(self, comp_id: str, x: float, y: float):
        self.comp_id = comp_id
        self.x = snap_to_grid(x)
        self.y = snap_to_grid(y)
        self.pins: list[Pin] = []
        self.outputs: dict[str, bool] = {}  # output pin_id -> state
        self.name: str = ""
        self.in_cycle = False
        self._init_pins()

    def _init_pins(self):
        """Override in subclasses to define pins."""
        pass

    def get_rect(self) -> pygame.Rect:
        """Get world-space bounding rectangle."""
        return pygame.Rect(
            self.x - self.body_width / 2,
            self.y - self.body_height / 2,
            self.body_width,
            self.body_height,
        )

    def contains_point(self, wx: float, wy: float) -> bool:
        """Check if world point is inside component body."""
        return self.get_rect().collidepoint(wx, wy)

    def evaluate(self):
        """Evaluate output based on inputs. Override in subclasses."""
        self.outputs["out"] = False

    def update(self):
        """Called each frame before evaluate. Override for clocks etc."""
        pass

    def get_pin(self, pin_id: str) -> Pin | None:
        """Find a pin by ID."""
        for pin in self.pins:
            if pin.pin_id == pin_id:
                return pin
        return None

    def get_input_state(self, pin_id: str) -> bool:
        """Get the state of an input pin (from connected wire/driver)."""
        pin = self.get_pin(pin_id)
        if pin is None or not pin.is_input:
            return False
        if pin.wire is not None:
            return pin.wire.get_state()
        return False

    def set_output_state(self, pin_id: str, state: bool):
        """Set output state and propagate to connected wires."""
        self.outputs[pin_id] = state
        pin = self.get_pin(pin_id)
        if pin is not None:
            pin.state = state
            for wire in pin.wires:
                wire.set_state(state)

    def get_output_state(self, pin_id: str = "out") -> bool:
        """Get the output state of a specific output pin."""
        return self.outputs.get(pin_id, False)

    def draw(self, surface: pygame.Surface, camera, highlight: bool = False, selected: bool = False):
        """Draw the component body, pins, and label."""
        sx, sy = camera.world_to_screen(self.x, self.y)
        w = self.body_width * camera.zoom
        h = self.body_height * camera.zoom

        # Body color based on output state
        out_state = self.outputs.get("out", False)
        if self.in_cycle:
            body_color = COLOR_CYCLE_HIGHLIGHT
        elif out_state:
            body_color = COLOR_COMPONENT_HIGH
        else:
            body_color = COLOR_COMPONENT_LOW

        # Draw body
        rect = pygame.Rect(sx - w / 2, sy - h / 2, w, h)
        pygame.draw.rect(surface, body_color, rect, border_radius=int(6 * camera.zoom))
        border_color = COLOR_PIN_HIGHLIGHT if (highlight or selected) else COLOR_COMPONENT_BORDER
        border_width = max(2, int(2.5 * camera.zoom))

        if self.in_cycle:
            border_color = COLOR_CYCLE_HIGHLIGHT

        if selected:
            border_color = (100, 180, 255)

        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=int(6 * camera.zoom))

        # Draw type label
        self._draw_label(surface, camera, sx, sy)

        # Draw pins
        for pin in self.pins:
            self._draw_pin(surface, camera, pin)

    def _draw_label(self, surface: pygame.Surface, camera, sx: float, sy: float):
        """Draw component type text."""
        font_size = max(10, int(12 * camera.zoom))
        try:
            font = pygame.font.SysFont("Arial", font_size, bold=True)
        except Exception:
            font = pygame.font.Font(None, font_size)
        label = self.type_name
        text = font.render(label, True, (255, 255, 255))
        text_rect = text.get_rect(center=(sx, sy))
        surface.blit(text, text_rect)

        # Draw name if set
        if self.name:
            name_font_size = max(8, int(10 * camera.zoom))
            try:
                name_font = pygame.font.SysFont("Arial", name_font_size)
            except Exception:
                name_font = pygame.font.Font(None, name_font_size)
            name_text = name_font.render(self.name, True, (200, 200, 255))
            name_rect = name_text.get_rect(center=(sx, sy - h * 0.55))
            surface.blit(name_text, name_rect)

    def _draw_pin(self, surface: pygame.Surface, camera, pin: Pin):
        """Draw a single pin."""
        px, py = pin.get_world_pos(self.x, self.y)
        psx, psy = camera.world_to_screen(px, py)
        r = max(3, int(PIN_RADIUS * camera.zoom))
        color = COLOR_PIN_HIGHLIGHT if pin.state else COLOR_PIN
        if pin.is_input and pin.wire is not None:
            color = COLOR_PIN_HIGHLIGHT if pin.wire.get_state() else COLOR_PIN
        pygame.draw.circle(surface, color, (int(psx), int(psy)), r)
        pygame.draw.circle(surface, (0, 0, 0), (int(psx), int(psy)), r, max(1, int(1 * camera.zoom)))

    def hit_test_pin(self, world_x: float, world_y: float) -> Pin | None:
        """Check if world point hits any pin. Returns the Pin or None."""
        for pin in self.pins:
            if pin.hit_test(world_x, world_y, self.x, self.y):
                return pin
        return None

    def get_pin_world_pos(self, pin_id: str) -> tuple[float, float] | None:
        """Get world position of a specific pin."""
        pin = self.get_pin(pin_id)
        if pin is None:
            return None
        return pin.get_world_pos(self.x, self.y)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.comp_id,
            "type": self.type_name,
            "pos": [self.x, self.y],
            "name": self.name,
            "frequency": getattr(self, 'frequency', None),
        }


# ─── Basic Gates ────────────────────────────────────────────────────────────

class ANDGate(Component):
    type_name = TYPE_AND
    body_width = COMPONENT_WIDTH
    body_height = COMPONENT_HEIGHT

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", a and b)


class ORGate(Component):
    type_name = TYPE_OR

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", a or b)


class NOTGate(Component):
    type_name = TYPE_NOT

    def _init_pins(self):
        self.pins = [
            Pin("in", -self.body_width / 2, 0, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in")
        self.set_output_state("out", not a)


class NANDGate(Component):
    type_name = TYPE_NAND

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", not (a and b))


class NORGate(Component):
    type_name = TYPE_NOR

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", not (a or b))


class XORGate(Component):
    type_name = TYPE_XOR

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", a != b)


class XNORGate(Component):
    type_name = TYPE_XNOR

    def _init_pins(self):
        self.pins = [
            Pin("in0", -self.body_width / 2, -self.body_height / 4, True),
            Pin("in1", -self.body_width / 2, self.body_height / 4, True),
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}

    def evaluate(self):
        a = self.get_input_state("in0")
        b = self.get_input_state("in1")
        self.set_output_state("out", a == b)


# ─── Special Components ──────────────────────────────────────────────────────

class InputNode(Component):
    type_name = TYPE_INPUT
    body_width = INPUT_NODE_SIZE
    body_height = INPUT_NODE_SIZE

    def __init__(self, comp_id: str, x: float, y: float):
        self._stored_state = False
        super().__init__(comp_id, x, y)

    def _init_pins(self):
        self.pins = [
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": self._stored_state}
        self.set_output_state("out", self._stored_state)

    def evaluate(self):
        self.set_output_state("out", self._stored_state)

    def toggle(self):
        self._stored_state = not self._stored_state
        self.set_output_state("out", self._stored_state)

    def draw(self, surface: pygame.Surface, camera, highlight: bool = False, selected: bool = False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        w = self.body_width * camera.zoom
        h = self.body_height * camera.zoom

        out_state = self.outputs.get("out", False)
        body_color = COLOR_COMPONENT_HIGH if out_state else COLOR_COMPONENT_LOW

        rect = pygame.Rect(sx - w / 2, sy - h / 2, w, h)
        # Draw as rounded square
        pygame.draw.rect(surface, body_color, rect, border_radius=int(8 * camera.zoom))

        border_color = COLOR_COMPONENT_BORDER
        if selected:
            border_color = (100, 180, 255)
        elif highlight:
            border_color = COLOR_PIN_HIGHLIGHT
        border_width = max(2, int(2.5 * camera.zoom))
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=int(8 * camera.zoom))

        # Label
        font_size = max(10, int(14 * camera.zoom))
        try:
            font = pygame.font.SysFont("Arial", font_size, bold=True)
        except Exception:
            font = pygame.font.Font(None, font_size)
        label = "IN" if out_state else "IN"
        text = font.render(label, True, (255, 255, 255))
        text_rect = text.get_rect(center=(sx, sy))
        surface.blit(text, text_rect)

        if self.name:
            name_font_size = max(8, int(10 * camera.zoom))
            try:
                name_font = pygame.font.SysFont("Arial", name_font_size)
            except Exception:
                name_font = pygame.font.Font(None, name_font_size)
            name_text = name_font.render(self.name, True, (200, 200, 255))
            name_rect = name_text.get_rect(center=(sx, sy - h * 0.7))
            surface.blit(name_text, name_rect)

        # Draw pins
        for pin in self.pins:
            self._draw_pin(surface, camera, pin)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["state"] = self._stored_state
        return d


class OutputNode(Component):
    type_name = TYPE_OUTPUT
    body_width = OUTPUT_NODE_SIZE
    body_height = OUTPUT_NODE_SIZE

    def _init_pins(self):
        self.pins = [
            Pin("in", -self.body_width / 2, 0, True),
        ]
        self.outputs = {}  # Output nodes don't have outputs

    def evaluate(self):
        # Just read input, no output to set
        pass

    def get_display_state(self) -> bool:
        return self.get_input_state("in")

    def draw(self, surface: pygame.Surface, camera, highlight: bool = False, selected: bool = False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        w = self.body_width * camera.zoom
        h = self.body_height * camera.zoom

        in_state = self.get_input_state("in")
        body_color = COLOR_COMPONENT_HIGH if in_state else COLOR_COMPONENT_LOW

        rect = pygame.Rect(sx - w / 2, sy - h / 2, w, h)
        pygame.draw.rect(surface, body_color, rect, border_radius=int(8 * camera.zoom))

        border_color = COLOR_COMPONENT_BORDER
        if selected:
            border_color = (100, 180, 255)
        elif highlight:
            border_color = COLOR_PIN_HIGHLIGHT
        border_width = max(2, int(2.5 * camera.zoom))
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=int(8 * camera.zoom))

        # Label
        font_size = max(10, int(14 * camera.zoom))
        try:
            font = pygame.font.SysFont("Arial", font_size, bold=True)
        except Exception:
            font = pygame.font.Font(None, font_size)
        state_label = "1" if in_state else "0"
        text = font.render(state_label, True, (255, 255, 255))
        text_rect = text.get_rect(center=(sx, sy))
        surface.blit(text, text_rect)

        if self.name:
            name_font_size = max(8, int(10 * camera.zoom))
            try:
                name_font = pygame.font.SysFont("Arial", name_font_size)
            except Exception:
                name_font = pygame.font.Font(None, name_font_size)
            name_text = name_font.render(self.name, True, (200, 200, 255))
            name_rect = name_text.get_rect(center=(sx, sy - h * 0.7))
            surface.blit(name_text, name_rect)

        # Draw pins
        for pin in self.pins:
            self._draw_pin(surface, camera, pin)


class ClockGenerator(Component):
    type_name = TYPE_CLOCK
    body_width = CLOCK_SIZE
    body_height = CLOCK_SIZE

    def __init__(self, comp_id: str, x: float, y: float):
        self.frequency = DEFAULT_CLOCK_FREQ
        self._last_toggle_time = 0
        self._internal_state = False
        super().__init__(comp_id, x, y)

    def _init_pins(self):
        self.pins = [
            Pin("out", self.body_width / 2, 0, False),
        ]
        self.outputs = {"out": False}
        self.set_output_state("out", False)

    def evaluate(self):
        self.set_output_state("out", self._internal_state)

    def update(self):
        """Toggle based on elapsed time."""
        period_ms = int(1000.0 / self.frequency)
        half_period = period_ms // 2
        if half_period < 1:
            half_period = 1
        now = pygame.time.get_ticks()
        if now - self._last_toggle_time >= half_period:
            self._internal_state = not self._internal_state
            self._last_toggle_time = now
            self.set_output_state("out", self._internal_state)

    def draw(self, surface: pygame.Surface, camera, highlight: bool = False, selected: bool = False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        w = self.body_width * camera.zoom
        h = self.body_height * camera.zoom

        out_state = self.outputs.get("out", False)
        body_color = COLOR_COMPONENT_HIGH if out_state else COLOR_COMPONENT_LOW

        rect = pygame.Rect(sx - w / 2, sy - h / 2, w, h)
        pygame.draw.rect(surface, body_color, rect, border_radius=int(8 * camera.zoom))

        border_color = COLOR_COMPONENT_BORDER
        if selected:
            border_color = (100, 180, 255)
        elif highlight:
            border_color = COLOR_PIN_HIGHLIGHT
        border_width = max(2, int(2.5 * camera.zoom))
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=int(8 * camera.zoom))

        # Draw a waveform icon
        # Simple clock symbol: a small rectangle wave
        mid_x = sx
        mid_y = sy
        amp = h * 0.2
        period = w * 0.4

        points = [
            (mid_x - period, mid_y),
            (mid_x - period, mid_y - amp),
            (mid_x - period * 0.33, mid_y - amp),
            (mid_x - period * 0.33, mid_y + amp),
            (mid_x + period * 0.33, mid_y + amp),
            (mid_x + period * 0.33, mid_y - amp),
            (mid_x + period, mid_y - amp),
            (mid_x + period, mid_y),
        ]
        pygame.draw.lines(surface, (255, 255, 255), False,
                          [(int(px), int(py)) for (px, py) in points],
                          max(1, int(2 * camera.zoom)))

        # Frequency label
        font_size = max(8, int(10 * camera.zoom))
        try:
            font = pygame.font.SysFont("Arial", font_size)
        except Exception:
            font = pygame.font.Font(None, font_size)
        freq_text = f"{self.frequency:.1f}Hz"
        text = font.render(freq_text, True, (255, 255, 200))
        text_rect = text.get_rect(center=(sx, sy - h * 0.35))
        surface.blit(text, text_rect)

        if self.name:
            name_font_size = max(8, int(10 * camera.zoom))
            try:
                name_font = pygame.font.SysFont("Arial", name_font_size)
            except Exception:
                name_font = pygame.font.Font(None, name_font_size)
            name_text = name_font.render(self.name, True, (200, 200, 255))
            name_rect = name_text.get_rect(center=(sx, sy - h * 0.7))
            surface.blit(name_text, name_rect)

        # Draw pins
        for pin in self.pins:
            self._draw_pin(surface, camera, pin)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["frequency"] = self.frequency
        return d


class SevenSegmentDisplay(Component):
    type_name = TYPE_SEVEN_SEG
    body_width = SEVEN_SEG_WIDTH
    body_height = SEVEN_SEG_HEIGHT

    def _init_pins(self):
        # 7 input pins: a, b, c, d, e, f, g
        h = self.body_height
        w = self.body_width
        self.pins = [
            Pin("a", -w / 2, -h * 0.38, True),   # top
            Pin("b", w * 0.15, -h / 2, True),     # upper right
            Pin("c", w * 0.15, h * 0.05, True),   # lower right
            Pin("d", -w / 2, h * 0.38, True),     # bottom
            Pin("e", -w * 0.35, h * 0.05, True),  # lower left
            Pin("f", -w * 0.35, -h / 2, True),    # upper left
            Pin("g", -w / 2, 0, True),            # middle
        ]
        self.outputs = {}

    def evaluate(self):
        pass  # No outputs

    def get_segment_states(self) -> dict[str, bool]:
        """Return dict of segment letter -> bool state."""
        states = {}
        for pin in self.pins:
            states[pin.pin_id] = self.get_input_state(pin.pin_id)
        return states

    def draw(self, surface: pygame.Surface, camera, highlight: bool = False, selected: bool = False):
        sx, sy = camera.world_to_screen(self.x, self.y)
        w = self.body_width * camera.zoom
        h = self.body_height * camera.zoom

        # Background
        rect = pygame.Rect(sx - w / 2, sy - h / 2, w, h)
        pygame.draw.rect(surface, (20, 20, 25), rect, border_radius=int(6 * camera.zoom))

        border_color = COLOR_COMPONENT_BORDER
        if selected:
            border_color = (100, 180, 255)
        elif highlight:
            border_color = COLOR_PIN_HIGHLIGHT
        border_width = max(2, int(2.5 * camera.zoom))
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=int(6 * camera.zoom))

        # Draw segments
        states = self.get_segment_states()
        seg_thickness = max(2, int(0.12 * h))
        seg_length = w * 0.44
        seg_short = w * 0.3
        gap = seg_thickness * 1.2

        cx, cy = sx, sy

        # Segment positions (relative to center in screen coords)
        # Each segment is a polygon (drawn as a thick line or filled rect)
        top_y = cy - h * 0.33
        mid_y = cy
        bot_y = cy + h * 0.33
        left_x = cx - seg_length * 0.45
        right_x = cx + seg_length * 0.45

        def draw_segment(pts, on):
            color = COLOR_SEGMENT_ON if on else COLOR_SEGMENT_OFF
            if len(pts) == 4:
                pygame.draw.polygon(surface, color, [(int(p[0]), int(p[1])) for p in pts])
                pygame.draw.polygon(surface, (0, 0, 0), [(int(p[0]), int(p[1])) for p in pts],
                                    max(1, int(1 * camera.zoom)))

        def make_horiz_seg(cx, cy, length, thick):
            hl = length / 2
            ht = thick / 2
            return [
                (cx - hl, cy - ht),
                (cx + hl, cy - ht),
                (cx + hl, cy + ht),
                (cx - hl, cy + ht),
            ]

        def make_vert_seg(cx, cy, length, thick):
            vl = length / 2
            vt = thick / 2
            return [
                (cx - vt, cy - vl),
                (cx + vt, cy - vl),
                (cx + vt, cy + vl),
                (cx - vt, cy + vl),
            ]

        hseg_len = seg_length
        vseg_len = seg_length * 0.85

        # Draw segments
        draw_segment(make_horiz_seg(cx, top_y, hseg_len, seg_thickness), states.get("a", False))
        draw_segment(make_vert_seg(right_x, (top_y + mid_y) / 2, vseg_len, seg_thickness), states.get("b", False))
        draw_segment(make_vert_seg(right_x, (mid_y + bot_y) / 2, vseg_len, seg_thickness), states.get("c", False))
        draw_segment(make_horiz_seg(cx, bot_y, hseg_len, seg_thickness), states.get("d", False))
        draw_segment(make_vert_seg(left_x, (mid_y + bot_y) / 2, vseg_len, seg_thickness), states.get("e", False))
        draw_segment(make_vert_seg(left_x, (top_y + mid_y) / 2, vseg_len, seg_thickness), states.get("f", False))
        draw_segment(make_horiz_seg(cx, mid_y, hseg_len * 0.8, seg_thickness), states.get("g", False))

        # Draw pin labels
        if camera.zoom > 0.3:
            font_size = max(6, int(8 * camera.zoom))
            try:
                font = pygame.font.SysFont("Arial", font_size)
            except Exception:
                font = pygame.font.Font(None, font_size)
            for pin in self.pins:
                px, py = pin.get_world_pos(self.x, self.y)
                psx, psy = camera.world_to_screen(px, py)
                label = font.render(pin.pin_id, True, (180, 180, 200))
                label_rect = label.get_rect(center=(psx, psy - 12 * camera.zoom))
                surface.blit(label, label_rect)

        if self.name:
            name_font_size = max(8, int(10 * camera.zoom))
            try:
                name_font = pygame.font.SysFont("Arial", name_font_size)
            except Exception:
                name_font = pygame.font.Font(None, name_font_size)
            name_text = name_font.render(self.name, True, (200, 200, 255))
            name_rect = name_text.get_rect(center=(sx, sy - h * 0.65))
            surface.blit(name_text, name_rect)

        # Draw pins
        for pin in self.pins:
            self._draw_pin(surface, camera, pin)


# ─── Factory ─────────────────────────────────────────────────────────────────

def create_component(comp_type: str, comp_id: str, x: float, y: float,
                     name: str = "", frequency: float = None,
                     initial_state: bool = False) -> Component:
    """Create a component by type string."""
    cls_map = {
        TYPE_AND: ANDGate,
        TYPE_OR: ORGate,
        TYPE_NOT: NOTGate,
        TYPE_NAND: NANDGate,
        TYPE_NOR: NORGate,
        TYPE_XOR: XORGate,
        TYPE_XNOR: XNORGate,
        TYPE_INPUT: InputNode,
        TYPE_OUTPUT: OutputNode,
        TYPE_CLOCK: ClockGenerator,
        TYPE_SEVEN_SEG: SevenSegmentDisplay,
    }
    cls = cls_map.get(comp_type)
    if cls is None:
        raise ValueError(f"Unknown component type: {comp_type}")

    comp = cls(comp_id, x, y)
    comp.name = name

    if comp_type == TYPE_CLOCK and frequency is not None:
        comp.frequency = frequency

    if comp_type == TYPE_INPUT and initial_state:
        comp._stored_state = initial_state
        comp.set_output_state("out", initial_state)

    return comp


def get_component_label(comp_type: str) -> str:
    """Get a display label for a component type."""
    labels = {
        TYPE_AND: "AND",
        TYPE_OR: "OR",
        TYPE_NOT: "NOT",
        TYPE_NAND: "NAND",
        TYPE_NOR: "NOR",
        TYPE_XOR: "XOR",
        TYPE_XNOR: "XNOR",
        TYPE_INPUT: "Input",
        TYPE_OUTPUT: "Output",
        TYPE_CLOCK: "Clock",
        TYPE_SEVEN_SEG: "7-Seg",
    }
    return labels.get(comp_type, comp_type)
