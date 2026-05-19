# components.py - All component classes for the logic gate simulator
import pygame
from constants import *

class Pin:
    """Represents an input or output pin on a component."""
    def __init__(self, pin_id, relative_x, relative_y, is_input):
        self.pin_id = pin_id
        self.rel_x = relative_x   # relative to component center
        self.rel_y = relative_y
        self.is_input = is_input

    def get_world_pos(self, comp_x, comp_y):
        return (comp_x + self.rel_x, comp_y + self.rel_y)


class Component:
    """Base class for all circuit components."""
    component_type = "BASE"

    def __init__(self, comp_id, x, y, label=""):
        self.comp_id = comp_id
        self.x = x
        self.y = y
        self.label = label or f"{self.component_type}_{comp_id.split('_')[-1]}"
        self.input_pins = []   # list of Pin
        self.output_pins = []  # list of Pin
        self._output_state = False  # current HIGH/LOW output
        self.config = {}
        self._setup_pins()

    def _setup_pins(self):
        """Override in subclasses to define pins."""
        pass

    def get_bounds(self):
        """Return (x, y, w, h) bounding box in world coords."""
        return (self.x - 30, self.y - 20, 60, 40)

    def contains_point(self, world_x, world_y):
        bx, by, bw, bh = self.get_bounds()
        return bx <= world_x <= bx + bw and by <= world_y <= by + bh

    def get_pin_at(self, world_x, world_y, max_dist=8):
        """Return pin if world position is near it."""
        for pin in self.input_pins + self.output_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            if abs(world_x - px) <= max_dist and abs(world_y - py) <= max_dist:
                return pin
        return None

    def evaluate(self, input_values):
        """Compute output given dict of pin_id->bool. Return dict of output pin_id->bool."""
        return {}

    @property
    def output_state(self):
        return self._output_state

    def set_output(self, state):
        self._output_state = state

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        """Render the component on screen."""
        pass

    def to_dict(self):
        return {
            "id": self.comp_id,
            "type": self.component_type,
            "position": [self.x, self.y],
            "label": self.label,
            "config": self.config
        }

    @staticmethod
    def from_dict(d, comp_id):
        comp_type = d["type"]
        x, y = d["position"]
        label = d.get("label", "")
        config = d.get("config", {})
        if comp_type == "AND":
            comp = AndGate(comp_id, x, y, label)
        elif comp_type == "OR":
            comp = OrGate(comp_id, x, y, label)
        elif comp_type == "NOT":
            comp = NotGate(comp_id, x, y, label)
        elif comp_type == "NAND":
            comp = NandGate(comp_id, x, y, label)
        elif comp_type == "NOR":
            comp = NorGate(comp_id, x, y, label)
        elif comp_type == "XOR":
            comp = XorGate(comp_id, x, y, label)
        elif comp_type == "XNOR":
            comp = XnorGate(comp_id, x, y, label)
        elif comp_type == "INPUT":
            comp = InputNode(comp_id, x, y, label)
        elif comp_type == "OUTPUT":
            comp = OutputNode(comp_id, x, y, label)
        elif comp_type == "CLOCK":
            comp = ClockGen(comp_id, x, y, label)
        elif comp_type == "SEVEN_SEGMENT":
            comp = SevenSegment(comp_id, x, y, label)
        else:
            raise ValueError(f"Unknown component type: {comp_type}")
        comp.config = config
        if comp_type == "CLOCK":
            comp.frequency = config.get("frequency", 1.0)
        return comp


class TwoInputGate(Component):
    """Base for 2-input gates."""
    def _setup_pins(self):
        self.input_pins = [
            Pin("in0", -GATE_WIDTH//2, -GATE_HEIGHT//3, True),
            Pin("in1", -GATE_WIDTH//2, GATE_HEIGHT//3, True),
        ]
        self.output_pins = [
            Pin("out", GATE_WIDTH//2, 0, False),
        ]

    def get_bounds(self):
        return (self.x - GATE_WIDTH//2, self.y - GATE_HEIGHT//2, GATE_WIDTH, GATE_HEIGHT)

    def evaluate(self, input_values):
        a = input_values.get("in0", False)
        b = input_values.get("in1", False)
        result = self._gate_func(a, b)
        self._output_state = result
        return {"out": result}

    def _gate_func(self, a, b):
        raise NotImplementedError

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        sw = bw * camera.zoom
        sh = bh * camera.zoom

        # Determine body color
        if cycle_highlight:
            body_color = CYCLE_HIGHLIGHT
        elif self._output_state:
            body_color = COMPONENT_HIGH
        else:
            body_color = COMPONENT_LOW

        # Draw body
        rect = pygame.Rect(sx, sy, sw, sh)
        pygame.draw.rect(screen, body_color, rect, border_radius=int(4 * camera.zoom))
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.rect(screen, border_color, rect, max(1, int(2 * camera.zoom)), border_radius=int(4 * camera.zoom))

        # Draw label
        font = pygame.font.Font(None, int(FONT_MEDIUM * camera.zoom))
        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(center=(sx + sw/2, sy + sh/2))
        screen.blit(text, text_rect)

        # Draw type symbol
        font_small = pygame.font.Font(None, int(FONT_SMALL * camera.zoom))
        sym = font_small.render(self._symbol(), True, TEXT_COLOR)
        sym_rect = sym.get_rect(center=(sx + sw/2, sy + sh/2 + int(12 * camera.zoom)))
        screen.blit(sym, sym_rect)

        # Draw pins
        self._render_pins(screen, camera)

    def _symbol(self):
        return "?"

    def _render_pins(self, screen, camera):
        for pin in self.input_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx, sy = camera.world_to_screen(px, py)
            r = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, INPUT_PIN_COLOR, (int(sx), int(sy)), r)
        for pin in self.output_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx, sy = camera.world_to_screen(px, py)
            r = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, OUTPUT_PIN_COLOR, (int(sx), int(sy)), r)


class AndGate(TwoInputGate):
    component_type = "AND"
    def _gate_func(self, a, b): return a and b
    def _symbol(self): return "&"

class OrGate(TwoInputGate):
    component_type = "OR"
    def _gate_func(self, a, b): return a or b
    def _symbol(self): return ">=1"

class NandGate(TwoInputGate):
    component_type = "NAND"
    def _gate_func(self, a, b): return not (a and b)
    def _symbol(self): return "&~"

class NorGate(TwoInputGate):
    component_type = "NOR"
    def _gate_func(self, a, b): return not (a or b)
    def _symbol(self): return ">=1~"

class XorGate(TwoInputGate):
    component_type = "XOR"
    def _gate_func(self, a, b): return a != b
    def _symbol(self): return "=1"

class XnorGate(TwoInputGate):
    component_type = "XNOR"
    def _gate_func(self, a, b): return a == b
    def _symbol(self): return "=1~"


class NotGate(Component):
    component_type = "NOT"

    def _setup_pins(self):
        self.input_pins = [
            Pin("in0", -NOT_WIDTH//2, 0, True),
        ]
        # Output pin is at the bubble (right of the triangle)
        self.output_pins = [
            Pin("out", NOT_WIDTH//2 + 6, 0, False),
        ]

    def get_bounds(self):
        # Include bubble in bounds
        return (self.x - NOT_WIDTH//2, self.y - NOT_HEIGHT//2, NOT_WIDTH + 12, NOT_HEIGHT)

    def evaluate(self, input_values):
        a = input_values.get("in0", False)
        result = not a
        self._output_state = result
        return {"out": result}

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        sw_tri = NOT_WIDTH * camera.zoom
        sh = NOT_HEIGHT * camera.zoom

        if cycle_highlight:
            body_color = CYCLE_HIGHLIGHT
        elif self._output_state:
            body_color = COMPONENT_HIGH
        else:
            body_color = COMPONENT_LOW

        # Triangle body
        tri_left = sx
        tri_right = sx + sw_tri
        tri_mid_y = sy + sh / 2
        points = [
            (tri_left, sy),  # top-left
            (tri_right, tri_mid_y),  # right tip
            (tri_left, sy + sh),  # bottom-left
        ]
        pygame.draw.polygon(screen, body_color, points)
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.polygon(screen, border_color, points, max(1, int(2 * camera.zoom)))

        # Draw bubble at output
        bubble_r = max(3, int(5 * camera.zoom))
        bubble_x = tri_right + bubble_r
        bubble_y = tri_mid_y
        pygame.draw.circle(screen, body_color, (int(bubble_x), int(bubble_y)), bubble_r)
        pygame.draw.circle(screen, border_color, (int(bubble_x), int(bubble_y)), bubble_r, max(1, int(2 * camera.zoom)))

        # Label
        font = pygame.font.Font(None, int(FONT_MEDIUM * camera.zoom))
        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(center=(sx + sw_tri * 0.35, sy + sh/2 - int(10 * camera.zoom)))
        screen.blit(text, text_rect)

        # Symbol
        font_small = pygame.font.Font(None, int(FONT_SMALL * camera.zoom))
        sym = font_small.render("1", True, TEXT_COLOR)
        sym_rect = sym.get_rect(center=(sx + sw_tri * 0.35, sy + sh/2 + int(8 * camera.zoom)))
        screen.blit(sym, sym_rect)

        # Input pins
        for pin in self.input_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            r = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, INPUT_PIN_COLOR, (int(sx_p), int(sy_p)), r)

        # Output pin (at bubble center)
        for pin in self.output_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            r = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, OUTPUT_PIN_COLOR, (int(sx_p), int(sy_p)), r)


class InputNode(Component):
    component_type = "INPUT"

    def _setup_pins(self):
        self.output_pins = [
            Pin("out", NODE_RADIUS, 0, False),
        ]
        self._output_state = False  # default LOW

    def get_bounds(self):
        return (self.x - NODE_RADIUS, self.y - NODE_RADIUS, NODE_RADIUS*2, NODE_RADIUS*2)

    def evaluate(self, input_values):
        return {"out": self._output_state}

    def toggle(self):
        self._output_state = not self._output_state

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        r = int(NODE_RADIUS * camera.zoom)

        color = COMPONENT_HIGH if self._output_state else COMPONENT_LOW
        if cycle_highlight:
            color = CYCLE_HIGHLIGHT

        pygame.draw.circle(screen, color, (int(sx + r), int(sy + r)), r)
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.circle(screen, border_color, (int(sx + r), int(sy + r)), r, max(1, int(2 * camera.zoom)))

        # Label
        font = pygame.font.Font(None, int(FONT_SMALL * camera.zoom))
        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(center=(sx + r, sy + r + r + int(10 * camera.zoom)))
        screen.blit(text, text_rect)

        # State text
        state_text = "1" if self._output_state else "0"
        font_state = pygame.font.Font(None, int(FONT_MEDIUM * camera.zoom))
        st = font_state.render(state_text, True, (0, 0, 0) if self._output_state else TEXT_COLOR)
        st_rect = st.get_rect(center=(sx + r, sy + r))
        screen.blit(st, st_rect)

        # Output pin
        for pin in self.output_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            pr = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, OUTPUT_PIN_COLOR, (int(sx_p), int(sy_p)), pr)


class OutputNode(Component):
    component_type = "OUTPUT"

    def _setup_pins(self):
        self.input_pins = [
            Pin("in0", -NODE_RADIUS, 0, True),
        ]
        self._output_state = False

    def get_bounds(self):
        return (self.x - NODE_RADIUS, self.y - NODE_RADIUS, NODE_RADIUS*2, NODE_RADIUS*2)

    def evaluate(self, input_values):
        self._output_state = input_values.get("in0", False)
        return {}

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        r = int(NODE_RADIUS * camera.zoom)

        color = COMPONENT_HIGH if self._output_state else COMPONENT_LOW
        if cycle_highlight:
            color = CYCLE_HIGHLIGHT

        pygame.draw.circle(screen, color, (int(sx + r), int(sy + r)), r)
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.circle(screen, border_color, (int(sx + r), int(sy + r)), r, max(1, int(2 * camera.zoom)))

        # Label
        font = pygame.font.Font(None, int(FONT_SMALL * camera.zoom))
        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(center=(sx + r, sy + r + r + int(10 * camera.zoom)))
        screen.blit(text, text_rect)

        # State text
        state_text = "1" if self._output_state else "0"
        font_state = pygame.font.Font(None, int(FONT_MEDIUM * camera.zoom))
        st = font_state.render(state_text, True, (0, 0, 0) if self._output_state else TEXT_COLOR)
        st_rect = st.get_rect(center=(sx + r, sy + r))
        screen.blit(st, st_rect)

        # Input pin
        for pin in self.input_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            pr = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, INPUT_PIN_COLOR, (int(sx_p), int(sy_p)), pr)


class ClockGen(Component):
    component_type = "CLOCK"

    def __init__(self, comp_id, x, y, label=""):
        self.frequency = 1.0  # Hz
        self._timer = 0.0
        super().__init__(comp_id, x, y, label)

    def _setup_pins(self):
        self.output_pins = [
            Pin("out", CLOCK_SIZE//2 + 4, 0, False),
        ]

    def get_bounds(self):
        return (self.x - CLOCK_SIZE//2, self.y - CLOCK_SIZE//2, CLOCK_SIZE, CLOCK_SIZE)

    def evaluate(self, input_values):
        return {"out": self._output_state}

    def update_clock(self, dt):
        """Update clock state based on elapsed time."""
        if self.frequency <= 0:
            return
        period = 1.0 / self.frequency
        self._timer += dt
        while self._timer >= period / 2.0:
            self._timer -= period / 2.0
            self._output_state = not self._output_state

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        sw = bw * camera.zoom
        sh = bh * camera.zoom

        color = COMPONENT_HIGH if self._output_state else COMPONENT_LOW
        if cycle_highlight:
            color = CYCLE_HIGHLIGHT

        rect = pygame.Rect(sx, sy, sw, sh)
        pygame.draw.rect(screen, color, rect, border_radius=int(4 * camera.zoom))
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.rect(screen, border_color, rect, max(1, int(2 * camera.zoom)), border_radius=int(4 * camera.zoom))

        # Clock symbol (wave-like pattern)
        mid_y = sy + sh/2
        mid_x = sx + sw/2
        # Draw a small clock-like icon
        font = pygame.font.Font(None, int(FONT_MEDIUM * camera.zoom))
        text = font.render("CLK", True, TEXT_COLOR)
        text_rect = text.get_rect(center=(mid_x, mid_y - int(6 * camera.zoom)))
        screen.blit(text, text_rect)

        # Frequency display
        font_small = pygame.font.Font(None, int(FONT_SMALL * camera.zoom))
        freq_text = f"{self.frequency:.1f}Hz"
        ft = font_small.render(freq_text, True, TEXT_COLOR)
        ft_rect = ft.get_rect(center=(mid_x, mid_y + int(12 * camera.zoom)))
        screen.blit(ft, ft_rect)

        # Output pin
        for pin in self.output_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            pr = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, OUTPUT_PIN_COLOR, (int(sx_p), int(sy_p)), pr)

    def to_dict(self):
        d = super().to_dict()
        d["config"]["frequency"] = self.frequency
        return d


class SevenSegment(Component):
    component_type = "SEVEN_SEGMENT"

    def _setup_pins(self):
        h = SEVEN_SEG_HEIGHT
        # 7 input pins on the left side, labeled a-g
        segment_names = ["a", "b", "c", "d", "e", "f", "g"]
        spacing = h / 8.0
        for i, name in enumerate(segment_names):
            y_off = -h/2 + spacing * (i + 1)
            self.input_pins.append(Pin(f"in_{name}", -SEVEN_SEG_WIDTH//2 - 4, y_off, True))
        self._segment_states = {name: False for name in segment_names}

    def get_bounds(self):
        return (self.x - SEVEN_SEG_WIDTH//2, self.y - SEVEN_SEG_HEIGHT//2,
                SEVEN_SEG_WIDTH, SEVEN_SEG_HEIGHT)

    def evaluate(self, input_values):
        for name in ["a", "b", "c", "d", "e", "f", "g"]:
            self._segment_states[name] = input_values.get(f"in_{name}", False)
        return {}

    def render(self, screen, camera, selected=False, cycle_highlight=False):
        bx, by, bw, bh = self.get_bounds()
        sx, sy = camera.world_to_screen(bx, by)
        sw = bw * camera.zoom
        sh = bh * camera.zoom

        # Background
        color = COMPONENT_LOW
        if cycle_highlight:
            color = CYCLE_HIGHLIGHT
        rect = pygame.Rect(sx, sy, sw, sh)
        pygame.draw.rect(screen, (20, 20, 20), rect, border_radius=int(4 * camera.zoom))
        border_color = COMPONENT_SELECTED_BORDER if selected else COMPONENT_BORDER
        if cycle_highlight:
            border_color = CYCLE_HIGHLIGHT
        pygame.draw.rect(screen, border_color, rect, max(1, int(2 * camera.zoom)), border_radius=int(4 * camera.zoom))

        # Draw 7-segment display
        self._draw_segments(screen, sx, sy, sw, sh, camera.zoom)

        # Label
        font = pygame.font.Font(None, int(FONT_SMALL * max(0.5, camera.zoom)))
        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(center=(sx + sw/2, sy + sh + int(12 * camera.zoom)))
        screen.blit(text, text_rect)

        # Input pins
        for pin in self.input_pins:
            px, py = pin.get_world_pos(self.x, self.y)
            sx_p, sy_p = camera.world_to_screen(px, py)
            pr = max(2, int(PIN_RADIUS * camera.zoom))
            pygame.draw.circle(screen, INPUT_PIN_COLOR, (int(sx_p), int(sy_p)), pr)
            # Label for each pin
            seg_name = pin.pin_id.split("_")[1]
            font_pin = pygame.font.Font(None, int(8 * camera.zoom))
            pt = font_pin.render(seg_name, True, (180, 180, 180))
            pt_rect = pt.get_rect(center=(sx_p - int(12 * camera.zoom), sy_p))
            screen.blit(pt, pt_rect)

    def _draw_segments(self, screen, sx, sy, sw, sh, zoom):
        """Draw the seven segment display."""
        margin = 0.12
        x0 = sx + sw * margin
        y0 = sy + sh * margin
        x1 = sx + sw * (1 - margin)
        y1 = sy + sh * (1 - margin)
        y_mid = (y0 + y1) / 2
        seg_thick = max(3, int(8 * zoom))

        # Define segments as (name, start, end) for line drawing
        segments = {
            'a': ((x0, y0), (x1, y0)),
            'b': ((x1, y0), (x1, y_mid)),
            'c': ((x1, y_mid), (x1, y1)),
            'd': ((x0, y1), (x1, y1)),
            'e': ((x0, y_mid), (x0, y1)),
            'f': ((x0, y0), (x0, y_mid)),
            'g': ((x0, y_mid), (x1, y_mid)),
        }

        for name, (p1, p2) in segments.items():
            on = self._segment_states.get(name, False)
            if on:
                # Draw glow effect
                glow_color = (min(255, SEGMENT_ON[0] + 60),
                              min(255, SEGMENT_ON[1] + 20),
                              min(255, SEGMENT_ON[2] + 20))
                pygame.draw.line(screen, glow_color, p1, p2, seg_thick + 2)
            color = SEGMENT_ON if on else SEGMENT_OFF
            pygame.draw.line(screen, color, p1, p2, seg_thick)

        # Draw small dots for decimal point
        dp_radius = max(2, int(4 * zoom))
        dp_x = x1 + int(12 * zoom)
        dp_y = y1
        pygame.draw.circle(screen, SEGMENT_OFF, (int(dp_x), int(dp_y)), dp_radius)
