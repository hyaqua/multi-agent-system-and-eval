"""Component classes for the Logic Gate Simulator."""
import math
import pygame
from config import (
    COLOR_HIGH, COLOR_LOW, COLOR_UNKNOWN, COLOR_COMPONENT_BODY,
    COLOR_COMPONENT_BORDER, COLOR_COMPONENT_SELECTED, COLOR_PIN_INPUT,
    COLOR_PIN_OUTPUT, COLOR_TEXT, COLOR_SEGMENT_ON, COLOR_SEGMENT_OFF,
    COLOR_WIRE, PIN_RADIUS, COMPONENT_SIZES, FONT_SIZE_SMALL, FONT_SIZE_NORMAL,
)


class Pin:
    """Represents a single pin on a component."""
    def __init__(self, name, local_x, local_y, is_input, label=None):
        self.name = name
        self.local_x = local_x
        self.local_y = local_y
        self.is_input = is_input
        self.label = label or name
        self.state = False  # True=HIGH, False=LOW


class Component:
    """Base class for all circuit components."""
    def __init__(self, comp_id, comp_type, x, y):
        self.id = comp_id
        self.type = comp_type
        self.x = x  # world center x
        self.y = y  # world center y
        self.pins = []
        self.label = comp_type
        self.config = {}
        self._setup_pins()

    def _setup_pins(self):
        """Override in subclasses to define pins."""
        pass

    def get_size(self):
        """Return (width, height) in world units."""
        return COMPONENT_SIZES.get(self.type, (80, 60))

    def get_rect(self):
        """Return world-space rect (left, top, width, height)."""
        w, h = self.get_size()
        return (self.x - w // 2, self.y - h // 2, w, h)

    def get_pin_world_pos(self, pin_name):
        """Return world position of a pin."""
        for pin in self.pins:
            if pin.name == pin_name:
                return (self.x + pin.local_x, self.y + pin.local_y)
        return (self.x, self.y)

    def get_pin_at_world(self, wx, wy, radius=None):
        """Return pin if world pos hits one, else None."""
        r = radius or PIN_RADIUS + 4
        for pin in self.pins:
            px = self.x + pin.local_x
            py = self.y + pin.local_y
            if math.hypot(wx - px, wy - py) <= r:
                return pin
        return None

    def contains_point(self, wx, wy):
        """Check if world point is inside component body."""
        left, top, w, h = self.get_rect()
        return left <= wx <= left + w and top <= wy <= top + h

    def evaluate(self, input_values):
        """Compute output from dict of pin_name->bool. Returns output bool."""
        return False

    def draw(self, screen, canvas, font, selected=False, cycle_members=None):
        """Draw component body, pins, and label."""
        left, top, w, h = self.get_rect()
        sx, sy = canvas.world_to_screen(left, top)
        sw, sh = w * canvas.zoom, h * canvas.zoom

        # Body
        body_rect = pygame.Rect(sx, sy, sw, sh)
        border_color = COLOR_COMPONENT_SELECTED if selected else COLOR_COMPONENT_BORDER
        if cycle_members and self.id in cycle_members:
            border_color = (255, 80, 80)
        pygame.draw.rect(screen, COLOR_COMPONENT_BODY, body_rect)
        pygame.draw.rect(screen, border_color, body_rect, 2)

        # Label
        text_surf = font.render(self.label, True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=(sx + sw // 2, sy + sh // 2))
        screen.blit(text_surf, text_rect)

        # Pins
        for pin in self.pins:
            px = self.x + pin.local_x
            py = self.y + pin.local_y
            psx, psy = canvas.world_to_screen(px, py)
            pr = int(PIN_RADIUS * canvas.zoom)
            if pr < 2:
                pr = 2

            color = COLOR_HIGH if pin.state else COLOR_LOW
            if cycle_members and self.id in cycle_members and pin.is_input:
                # Could be oscillating
                pass
            pin_color = COLOR_PIN_INPUT if pin.is_input else COLOR_PIN_OUTPUT
            pygame.draw.circle(screen, pin_color, (int(psx), int(psy)), pr)
            pygame.draw.circle(screen, color, (int(psx), int(psy)), max(pr - 2, 1))

            # Pin label
            if canvas.zoom > 0.4:
                small_font = pygame.font.Font(None, max(8, int(FONT_SIZE_SMALL * canvas.zoom)))
                lbl = small_font.render(pin.label, True, (180, 180, 200))
                offset_x = 8 * canvas.zoom if pin.is_input else -8 * canvas.zoom
                lbl_rect = lbl.get_rect(centery=psy, x=psx + offset_x)
                if pin.is_input:
                    lbl_rect.left = psx + 8 * canvas.zoom
                else:
                    lbl_rect.right = psx - 8 * canvas.zoom
                screen.blit(lbl, lbl_rect)

    def draw_properties(self, screen, font, wx, wy):
        """Override for special property rendering."""
        pass


class AndGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return input_values.get("in0", False) and input_values.get("in1", False)


class OrGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return input_values.get("in0", False) or input_values.get("in1", False)


class NotGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in", -w // 2, 0, True, "A"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return not input_values.get("in", False)


class NandGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return not (input_values.get("in0", False) and input_values.get("in1", False))


class NorGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return not (input_values.get("in0", False) or input_values.get("in1", False))


class XorGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        a = input_values.get("in0", False)
        b = input_values.get("in1", False)
        return a != b


class XnorGate(Component):
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in0", -w // 2, -h // 4, True, "A"))
        self.pins.append(Pin("in1", -w // 2, h // 4, True, "B"))
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        a = input_values.get("in0", False)
        b = input_values.get("in1", False)
        return a == b


class InputNode(Component):
    """External input that can be toggled by clicking."""
    def __init__(self, comp_id, comp_type, x, y):
        super().__init__(comp_id, comp_type, x, y)
        self.state = False  # Toggle state

    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return self.state

    def toggle(self):
        self.state = not self.state


class OutputNode(Component):
    """External output that displays its input state."""
    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("in", -w // 2, 0, True, "D"))

    def evaluate(self, input_values):
        return input_values.get("in", False)

    def draw(self, screen, canvas, font, selected=False, cycle_members=None):
        super().draw(screen, canvas, font, selected, cycle_members)
        # Show state text
        left, top, w, h = self.get_rect()
        sx, sy = canvas.world_to_screen(left, top)
        sw, sh = w * canvas.zoom, h * canvas.zoom
        state_text = "HIGH" if self.pins[0].state else "LOW"
        state_color = COLOR_HIGH if self.pins[0].state else COLOR_LOW
        state_surf = font.render(state_text, True, state_color)
        state_rect = state_surf.get_rect(center=(sx + sw // 2, sy + sh - 12 * canvas.zoom))
        screen.blit(state_surf, state_rect)


class Clock(Component):
    """Clock generator that oscillates based on time."""
    def __init__(self, comp_id, comp_type, x, y):
        super().__init__(comp_id, comp_type, x, y)
        self.config["frequency"] = 2.0  # Hz
        self.state = False

    def _setup_pins(self):
        w, h = self.get_size()
        self.pins.append(Pin("out", w // 2, 0, False, "Q"))

    def evaluate(self, input_values):
        return self.state

    def update_state(self, time_ms):
        freq = self.config.get("frequency", 2.0)
        period_ms = 500.0 / freq  # Half period in ms
        self.state = (time_ms // int(period_ms)) % 2 == 0
        self.pins[0].state = self.state

    def draw(self, screen, canvas, font, selected=False, cycle_members=None):
        super().draw(screen, canvas, font, selected, cycle_members)
        # Show frequency
        left, top, w, h = self.get_rect()
        sx, sy = canvas.world_to_screen(left, top)
        sw, sh = w * canvas.zoom, h * canvas.zoom
        freq_text = f"{self.config.get('frequency', 2.0):.1f} Hz"
        if canvas.zoom > 0.3:
            small_font = pygame.font.Font(None, max(8, int(FONT_SIZE_SMALL * canvas.zoom)))
            freq_surf = small_font.render(freq_text, True, COLOR_TEXT)
            freq_rect = freq_surf.get_rect(center=(sx + sw // 2, sy + sh - 10 * canvas.zoom))
            screen.blit(freq_surf, freq_rect)


class SevenSegment(Component):
    """Seven-segment display with 7 input pins (A-G)."""
    def __init__(self, comp_id, comp_type, x, y):
        super().__init__(comp_id, comp_type, x, y)
        self.segment_states = {chr(ord('A') + i): False for i in range(7)}

    def _setup_pins(self):
        w, h = self.get_size()
        pin_names = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        spacing = h / 8
        for i, name in enumerate(pin_names):
            y_offs = -h // 2 + spacing * (i + 1)
            self.pins.append(Pin(name, -w // 2, y_offs, True, name))

    def evaluate(self, input_values):
        for i in range(7):
            name = chr(ord('A') + i)
            self.segment_states[name] = input_values.get(name, False)
        return False

    def draw(self, screen, canvas, font, selected=False, cycle_members=None):
        super().draw(screen, canvas, font, selected, cycle_members)
        # Draw seven segment display
        left, top, w, h = self.get_rect()
        sx, sy = canvas.world_to_screen(left, top)
        sw, sh = w * canvas.zoom, h * canvas.zoom

        # Segment definitions relative to component rect (fractional)
        margin = 0.15
        seg_thick = 0.08
        # A: top horizontal
        # B: upper right vertical
        # C: lower right vertical
        # D: bottom horizontal
        # E: lower left vertical
        # F: upper left vertical
        # G: middle horizontal

        def seg_rect(fx1, fy1, fx2, fy2):
            """Get screen rect from fractional coordinates."""
            x1 = sx + fx1 * sw
            y1 = sy + fy1 * sh
            x2 = sx + fx2 * sw
            y2 = sy + fy2 * sh
            return pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

        segments = {
            'A': seg_rect(margin, margin - seg_thick / 2, 1 - margin, margin + seg_thick / 2),
            'B': seg_rect(1 - margin - seg_thick / 2, margin, 1 - margin + seg_thick / 2, 0.5),
            'C': seg_rect(1 - margin - seg_thick / 2, 0.5, 1 - margin + seg_thick / 2, 1 - margin),
            'D': seg_rect(margin, 1 - margin - seg_thick / 2, 1 - margin, 1 - margin + seg_thick / 2),
            'E': seg_rect(margin - seg_thick / 2, 0.5, margin + seg_thick / 2, 1 - margin),
            'F': seg_rect(margin - seg_thick / 2, margin, margin + seg_thick / 2, 0.5),
            'G': seg_rect(margin, 0.5 - seg_thick / 2, 1 - margin, 0.5 + seg_thick / 2),
        }

        for name, rect in segments.items():
            is_on = self.segment_states.get(name, False)
            color = COLOR_SEGMENT_ON if is_on else COLOR_SEGMENT_OFF
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (80, 40, 30) if not is_on else (255, 100, 60), rect, 1)


# Factory
COMPONENT_CLASSES = {
    "AND": AndGate,
    "OR": OrGate,
    "NOT": NotGate,
    "NAND": NandGate,
    "NOR": NorGate,
    "XOR": XorGate,
    "XNOR": XnorGate,
    "INPUT": InputNode,
    "OUTPUT": OutputNode,
    "CLOCK": Clock,
    "SEVEN_SEGMENT": SevenSegment,
}


def create_component(comp_type, comp_id, x, y, config=None):
    """Factory function to create a component."""
    cls = COMPONENT_CLASSES.get(comp_type)
    if cls is None:
        raise ValueError(f"Unknown component type: {comp_type}")
    comp = cls(comp_id, comp_type, x, y)
    if config:
        comp.config.update(config)
    return comp
