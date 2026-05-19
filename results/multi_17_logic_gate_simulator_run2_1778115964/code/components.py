"""Component classes: gates, I/O nodes, clock, seven-segment display."""

from __future__ import annotations

import uuid
import pygame
from typing import Optional

from config import (
    GATE_WIDTH, GATE_HEIGHT, NODE_SIZE, CLOCK_WIDTH, CLOCK_HEIGHT,
    SEVENSEG_WIDTH, SEVENSEG_HEIGHT, DEFAULT_CLOCK_FREQ,
    COLOR_HIGH, COLOR_LOW, COLOR_COMPONENT_BODY, COLOR_COMPONENT_BORDER,
    COLOR_COMPONENT_SELECTED, COLOR_CYCLE_ERROR,
    COLOR_PIN_DEFAULT, COLOR_PIN_CONNECTED_HIGH, COLOR_PIN_CONNECTED_LOW,
    PIN_RADIUS_SCREEN, COLOR_TEXT,
)
from pins import InputPin, OutputPin


class Component:
    """Base class for all circuit components."""
    type_name: str = "Component"
    default_width: int = GATE_WIDTH
    default_height: int = GATE_HEIGHT

    def __init__(self, position: pygame.Vector2 | tuple, comp_id: Optional[str] = None):
        self.id = comp_id or str(uuid.uuid4())
        self.position = pygame.Vector2(position)
        self.input_pins: list[InputPin] = []
        self.output_pins: list[OutputPin] = []
        self.selected: bool = False
        self.has_cycle_error: bool = False
        self.config: dict = {"name": self.type_name}
        self._create_pins()

    def _create_pins(self):
        """Override in subclasses to define input/output pins."""
        pass

    def evaluate(self):
        """Compute output values from input values. Override in subclasses."""
        pass

    @property
    def width(self) -> int:
        return self.default_width

    @property
    def height(self) -> int:
        return self.default_height

    @property
    def rect(self) -> pygame.Rect:
        """World-space bounding rectangle."""
        return pygame.Rect(
            self.position.x - self.width / 2,
            self.position.y - self.height / 2,
            self.width,
            self.height,
        )

    def contains_point(self, world_point: pygame.Vector2 | tuple) -> bool:
        """Check if a world point is inside this component."""
        return self.rect.collidepoint(world_point)

    def get_output_value(self, pin_name: str = "out") -> bool:
        """Get the output value for a named output pin."""
        for pin in self.output_pins:
            if pin.name == pin_name:
                return pin.value
        return False

    def get_input_value(self, pin_name: str) -> bool:
        """Get the input value for a named input pin."""
        for pin in self.input_pins:
            if pin.name == pin_name:
                return pin.value
        return False

    @property
    def display_name(self) -> str:
        return self.config.get("name", self.type_name)

    def render(self, screen: pygame.Surface, camera: 'Camera'):
        """Render the component on screen."""
        # Compute screen-space rect
        top_left = camera.world_to_screen(
            (self.position.x - self.width / 2, self.position.y - self.height / 2)
        )
        w = self.width * camera.zoom
        h = self.height * camera.zoom
        screen_rect = pygame.Rect(top_left.x, top_left.y, w, h)

        # Determine body color
        if self.has_cycle_error:
            body_color = COLOR_CYCLE_ERROR
        elif self.output_pins:
            # Use first output pin's value for body color
            val = self.output_pins[0].value
            body_color = COLOR_HIGH if val else COLOR_LOW
        else:
            body_color = COLOR_COMPONENT_BODY

        # Draw body
        self._draw_body(screen, screen_rect, body_color)

        # Draw selection highlight
        if self.selected:
            pygame.draw.rect(screen, COLOR_COMPONENT_SELECTED, screen_rect, 2)

        # Draw cycle error highlight
        if self.has_cycle_error:
            pygame.draw.rect(screen, COLOR_CYCLE_ERROR, screen_rect, 3)

        # Draw label
        font = pygame.font.Font(None, int(14 * camera.zoom))
        if font.get_height() > 0:
            label = self.display_name
            text_surf = font.render(label, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=screen_rect.center)
            screen.blit(text_surf, text_rect)

        # Draw pins
        for pin in self.input_pins:
            self._render_pin(screen, camera, pin)
        for pin in self.output_pins:
            self._render_pin(screen, camera, pin)

    def _draw_body(self, screen: pygame.Surface, rect: pygame.Rect, body_color):
        """Draw the component body shape. Override for custom shapes."""
        pygame.draw.rect(screen, body_color, rect, border_radius=3)
        pygame.draw.rect(screen, COLOR_COMPONENT_BORDER, rect, 1, border_radius=3)

    def _render_pin(self, screen: pygame.Surface, camera: 'Camera', pin: 'Pin'):
        """Render a single pin as a small circle."""
        screen_pos = camera.world_to_screen(pin.world_pos)
        radius = PIN_RADIUS_SCREEN

        # Determine pin color
        if isinstance(pin, OutputPin):
            if self.has_cycle_error:
                color = COLOR_CYCLE_ERROR
            elif pin.value:
                color = COLOR_PIN_CONNECTED_HIGH
            else:
                color = COLOR_PIN_CONNECTED_LOW
        else:  # InputPin
            if self.has_cycle_error:
                color = COLOR_CYCLE_ERROR
            elif pin.connected:
                val = pin.value
                color = COLOR_PIN_CONNECTED_HIGH if val else COLOR_PIN_CONNECTED_LOW
            else:
                color = COLOR_PIN_DEFAULT

        pygame.draw.circle(screen, color, (int(screen_pos.x), int(screen_pos.y)), radius)
        pygame.draw.circle(screen, (40, 40, 40), (int(screen_pos.x), int(screen_pos.y)), radius, 1)

    def get_pin_at_screen_pos(self, screen_pos: tuple, camera: 'Camera') -> Optional['Pin']:
        """Return a pin if the screen position hits it, else None."""
        all_pins = self.input_pins + self.output_pins
        for pin in all_pins:
            pin_screen = camera.world_to_screen(pin.world_pos)
            dx = screen_pos[0] - pin_screen.x
            dy = screen_pos[1] - pin_screen.y
            if (dx * dx + dy * dy) <= (PIN_RADIUS_SCREEN + 4) ** 2:
                return pin
        return None

    def get_output_pin_by_name(self, name: str) -> Optional[OutputPin]:
        for pin in self.output_pins:
            if pin.name == name:
                return pin
        return None

    def get_input_pin_by_name(self, name: str) -> Optional[InputPin]:
        for pin in self.input_pins:
            if pin.name == name:
                return pin
        return None


# ──── Basic Gates ─────────────────────────────────────────────

class ANDGate(Component):
    type_name = "AND"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = a and b

    def _draw_body(self, screen, rect, body_color):
        # AND gate: flat left, rounded right (D-shape)
        pygame.draw.rect(screen, body_color, rect, border_radius=3)
        pygame.draw.rect(screen, COLOR_COMPONENT_BORDER, rect, 1, border_radius=3)


class ORGate(Component):
    type_name = "OR"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = a or b

    def _draw_body(self, screen, rect, body_color):
        # OR gate: shield shape approximation
        points = [
            (rect.left, rect.top),
            (rect.left + rect.width * 0.6, rect.top),
            (rect.right, rect.centery),
            (rect.left + rect.width * 0.6, rect.bottom),
            (rect.left, rect.bottom),
        ]
        pygame.draw.polygon(screen, body_color, points)
        pygame.draw.polygon(screen, COLOR_COMPONENT_BORDER, points, 1)


class NOTGate(Component):
    type_name = "NOT"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in", (-self.width / 2, 0), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        self.output_pins[0].value = not self.input_pins[0].value

    def _draw_body(self, screen, rect, body_color):
        # NOT gate: triangle with small circle at output
        points = [
            (rect.left, rect.top),
            (rect.left, rect.bottom),
            (rect.right - 6, rect.centery),
        ]
        pygame.draw.polygon(screen, body_color, points)
        pygame.draw.polygon(screen, COLOR_COMPONENT_BORDER, points, 1)
        # Draw negation circle
        cx = rect.right - 3
        cy = rect.centery
        pygame.draw.circle(screen, body_color, (int(cx), int(cy)), 5)
        pygame.draw.circle(screen, COLOR_COMPONENT_BORDER, (int(cx), int(cy)), 5, 1)


class NANDGate(Component):
    type_name = "NAND"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = not (a and b)

    def _draw_body(self, screen, rect, body_color):
        pygame.draw.rect(screen, body_color, rect, border_radius=3)
        pygame.draw.rect(screen, COLOR_COMPONENT_BORDER, rect, 1, border_radius=3)
        # Negation dot at output
        cx = rect.right - 4
        cy = rect.centery
        pygame.draw.circle(screen, body_color, (int(cx), int(cy)), 5)
        pygame.draw.circle(screen, COLOR_COMPONENT_BORDER, (int(cx), int(cy)), 5, 1)


class NORGate(Component):
    type_name = "NOR"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = not (a or b)

    def _draw_body(self, screen, rect, body_color):
        points = [
            (rect.left, rect.top),
            (rect.left + rect.width * 0.6, rect.top),
            (rect.right - 6, rect.centery),
            (rect.left + rect.width * 0.6, rect.bottom),
            (rect.left, rect.bottom),
        ]
        pygame.draw.polygon(screen, body_color, points)
        pygame.draw.polygon(screen, COLOR_COMPONENT_BORDER, points, 1)
        cx = rect.right - 3
        cy = rect.centery
        pygame.draw.circle(screen, body_color, (int(cx), int(cy)), 5)
        pygame.draw.circle(screen, COLOR_COMPONENT_BORDER, (int(cx), int(cy)), 5, 1)


class XORGate(Component):
    type_name = "XOR"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = a != b

    def _draw_body(self, screen, rect, body_color):
        # XOR: OR shape with extra curve line on left
        points = [
            (rect.left + 8, rect.top),
            (rect.left + rect.width * 0.6, rect.top),
            (rect.right, rect.centery),
            (rect.left + rect.width * 0.6, rect.bottom),
            (rect.left + 8, rect.bottom),
        ]
        pygame.draw.polygon(screen, body_color, points)
        pygame.draw.polygon(screen, COLOR_COMPONENT_BORDER, points, 1)
        # Extra curve on left
        pygame.draw.arc(screen, COLOR_COMPONENT_BORDER,
                        pygame.Rect(rect.left - 4, rect.top, 20, rect.height),
                        3.14159 * 0.5, 3.14159 * 1.5, 1)


class XNORGate(Component):
    type_name = "XNOR"

    def _create_pins(self):
        self.input_pins = [
            InputPin("in1", (-self.width / 2, -10), self),
            InputPin("in2", (-self.width / 2, 10), self),
        ]
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        a = self.input_pins[0].value
        b = self.input_pins[1].value
        self.output_pins[0].value = a == b

    def _draw_body(self, screen, rect, body_color):
        points = [
            (rect.left + 8, rect.top),
            (rect.left + rect.width * 0.6, rect.top),
            (rect.right - 6, rect.centery),
            (rect.left + rect.width * 0.6, rect.bottom),
            (rect.left + 8, rect.bottom),
        ]
        pygame.draw.polygon(screen, body_color, points)
        pygame.draw.polygon(screen, COLOR_COMPONENT_BORDER, points, 1)
        pygame.draw.arc(screen, COLOR_COMPONENT_BORDER,
                        pygame.Rect(rect.left - 4, rect.top, 20, rect.height),
                        3.14159 * 0.5, 3.14159 * 1.5, 1)
        cx = rect.right - 3
        cy = rect.centery
        pygame.draw.circle(screen, body_color, (int(cx), int(cy)), 5)
        pygame.draw.circle(screen, COLOR_COMPONENT_BORDER, (int(cx), int(cy)), 5, 1)


# ──── I/O Nodes ───────────────────────────────────────────────

class InputNode(Component):
    type_name = "INPUT"
    default_width = NODE_SIZE
    default_height = NODE_SIZE

    def _create_pins(self):
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]
        # Start HIGH by default (toggleable)
        self.output_pins[0].value = False

    def evaluate(self):
        # State is toggled by clicking; keep current value
        pass

    def toggle(self):
        self.output_pins[0].value = not self.output_pins[0].value

    def _draw_body(self, screen, rect, body_color):
        # Draw as a small box with label "IN"
        pygame.draw.rect(screen, body_color, rect, border_radius=3)
        border_color = COLOR_COMPONENT_SELECTED if self.selected else COLOR_COMPONENT_BORDER
        pygame.draw.rect(screen, border_color, rect, 1, border_radius=3)
        # Draw "IN" text
        font = pygame.font.Font(None, max(12, int(14 * min(2, camera_zoom := 1))))
        # We'll handle text in render method; here just draw shape

    def render(self, screen, camera):
        super().render(screen, camera)
        # Add "IN" and toggle state indicator
        top_left = camera.world_to_screen(
            (self.position.x - self.width / 2, self.position.y - self.height / 2)
        )
        w = self.width * camera.zoom
        h = self.height * camera.zoom
        screen_rect = pygame.Rect(top_left.x, top_left.y, w, h)
        font_size = max(10, int(12 * camera.zoom))
        font = pygame.font.Font(None, font_size)
        if font.get_height() > 0:
            label = "IN"
            text_surf = font.render(label, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(screen_rect.centerx, screen_rect.centery - 6))
            screen.blit(text_surf, text_rect)
            val_text = "1" if self.output_pins[0].value else "0"
            val_surf = font.render(val_text, True,
                                   COLOR_HIGH if self.output_pins[0].value else COLOR_LOW)
            val_rect = val_surf.get_rect(center=(screen_rect.centerx, screen_rect.centery + 8))
            screen.blit(val_surf, val_rect)


class OutputNode(Component):
    type_name = "OUTPUT"
    default_width = NODE_SIZE
    default_height = NODE_SIZE

    def _create_pins(self):
        self.input_pins = [
            InputPin("in", (-self.width / 2, 0), self),
        ]

    def evaluate(self):
        # Just reads input; no outputs to drive
        pass

    def render(self, screen, camera):
        super().render(screen, camera)
        top_left = camera.world_to_screen(
            (self.position.x - self.width / 2, self.position.y - self.height / 2)
        )
        w = self.width * camera.zoom
        h = self.height * camera.zoom
        screen_rect = pygame.Rect(top_left.x, top_left.y, w, h)
        font_size = max(10, int(12 * camera.zoom))
        font = pygame.font.Font(None, font_size)
        if font.get_height() > 0:
            label = "OUT"
            text_surf = font.render(label, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(screen_rect.centerx, screen_rect.centery - 6))
            screen.blit(text_surf, text_rect)
            val = self.input_pins[0].value
            val_text = "1" if val else "0"
            val_surf = font.render(val_text, True, COLOR_HIGH if val else COLOR_LOW)
            val_rect = val_surf.get_rect(center=(screen_rect.centerx, screen_rect.centery + 8))
            screen.blit(val_surf, val_rect)


# ──── Clock Generator ─────────────────────────────────────────

class ClockGenerator(Component):
    type_name = "CLOCK"
    default_width = CLOCK_WIDTH
    default_height = CLOCK_HEIGHT

    def __init__(self, position, comp_id=None):
        super().__init__(position, comp_id)
        self.config.setdefault("frequency", DEFAULT_CLOCK_FREQ)
        self._start_ticks = pygame.time.get_ticks()

    def _create_pins(self):
        self.output_pins = [
            OutputPin("out", (self.width / 2, 0), self),
        ]

    def evaluate(self):
        freq = self.config.get("frequency", DEFAULT_CLOCK_FREQ)
        elapsed = (pygame.time.get_ticks() - self._start_ticks) / 1000.0
        if freq <= 0:
            self.output_pins[0].value = False
            return
        period = 1.0 / freq
        self.output_pins[0].value = int(elapsed / period) % 2 == 0

    def render(self, screen, camera):
        super().render(screen, camera)
        top_left = camera.world_to_screen(
            (self.position.x - self.width / 2, self.position.y - self.height / 2)
        )
        w = self.width * camera.zoom
        h = self.height * camera.zoom
        screen_rect = pygame.Rect(top_left.x, top_left.y, w, h)
        font_size = max(10, int(10 * camera.zoom))
        font = pygame.font.Font(None, font_size)
        if font.get_height() > 0:
            freq = self.config.get("frequency", DEFAULT_CLOCK_FREQ)
            label = f"{freq:.1f} Hz"
            text_surf = font.render(label, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(screen_rect.centerx, screen_rect.centery + 8))
            screen.blit(text_surf, text_rect)


# ──── Seven Segment Display ───────────────────────────────────

class SevenSegmentDisplay(Component):
    type_name = "7SEG"
    default_width = SEVENSEG_WIDTH
    default_height = SEVENSEG_HEIGHT

    def _create_pins(self):
        # 7 input pins: a, b, c, d, e, f, g
        pin_names = ["a", "b", "c", "d", "e", "f", "g"]
        spacing = self.height / 8
        for i, name in enumerate(pin_names):
            y_offset = -self.height / 2 + spacing * (i + 1)
            self.input_pins.append(
                InputPin(name, (-self.width / 2, y_offset), self)
            )

    def evaluate(self):
        # No outputs; just for display
        pass

    def get_segment_state(self, seg: str) -> bool:
        for pin in self.input_pins:
            if pin.name == seg:
                return pin.value
        return False

    def render(self, screen, camera):
        super().render(screen, camera)

        # Draw the 7-segment pattern
        top_left = camera.world_to_screen(
            (self.position.x - self.width / 2, self.position.y - self.height / 2)
        )
        w = self.width * camera.zoom
        h = self.height * camera.zoom

        # Define segment geometry in screen space
        margin = 0.15
        seg_w = w * 0.5
        seg_h = h * 0.16
        thick = max(2, int(seg_h * 0.8))

        cx = top_left.x + w / 2
        cy = top_left.y + h / 2
        left = cx - seg_w / 2
        right = cx + seg_w / 2
        top = cy - seg_h * 3
        bottom = cy + seg_h * 3

        segments = {
            'a': ((left, top), (right, top)),
            'b': ((right, top), (right, cy)),
            'c': ((right, cy), (right, bottom)),
            'd': ((left, bottom), (right, bottom)),
            'e': ((left, cy), (left, bottom)),
            'f': ((left, top), (left, cy)),
            'g': ((left, cy), (right, cy)),
        }

        for seg_name, (p1, p2) in segments.items():
            val = self.get_segment_state(seg_name)
            color = COLOR_HIGH if val else (50, 50, 50)
            pygame.draw.line(screen, color, p1, p2, thick)


# ──── Component Registry ──────────────────────────────────────

COMPONENT_TYPES: dict[str, type] = {
    "AND": ANDGate,
    "OR": ORGate,
    "NOT": NOTGate,
    "NAND": NANDGate,
    "NOR": NORGate,
    "XOR": XORGate,
    "XNOR": XNORGate,
    "INPUT": InputNode,
    "OUTPUT": OutputNode,
    "CLOCK": ClockGenerator,
    "7SEG": SevenSegmentDisplay,
}

# Categories for toolbar organization
GATE_TYPES = ["AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"]
IO_TYPES = ["INPUT", "OUTPUT"]
SPECIAL_TYPES = ["CLOCK", "7SEG"]
ALL_COMPONENT_TYPES = GATE_TYPES + IO_TYPES + SPECIAL_TYPES
