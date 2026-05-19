"""Toolbar UI for selecting components to place."""

import pygame
from config import (
    TOOLBAR_WIDTH, COLOR_TOOLBAR_BG, COLOR_TOOLBAR_BUTTON,
    COLOR_TOOLBAR_BUTTON_HOVER, COLOR_TOOLBAR_BUTTON_ACTIVE,
    COLOR_TOOLBAR_TEXT, COLOR_TOOLBAR_SEPARATOR,
)
from components import GATE_TYPES, IO_TYPES, SPECIAL_TYPES


class Toolbar:
    """Vertical toolbar on the left side of the screen."""

    BUTTON_HEIGHT = 50
    BUTTON_MARGIN = 4

    def __init__(self):
        self.buttons: list[dict] = []
        self.active_type: str | None = None
        self.hovered_index: int = -1
        self.rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, 0)
        self._build_buttons()

    def _build_buttons(self):
        """Create button definitions for all component types."""
        self.buttons = []
        y = 10

        # Section: Gates
        for comp_type in GATE_TYPES:
            self.buttons.append({
                "type": comp_type,
                "label": comp_type,
                "rect": pygame.Rect(self.BUTTON_MARGIN, y,
                                    TOOLBAR_WIDTH - 2 * self.BUTTON_MARGIN, self.BUTTON_HEIGHT),
            })
            y += self.BUTTON_HEIGHT + self.BUTTON_MARGIN

        y += 4  # separator gap

        # Section: I/O
        for comp_type in IO_TYPES:
            self.buttons.append({
                "type": comp_type,
                "label": comp_type,
                "rect": pygame.Rect(self.BUTTON_MARGIN, y,
                                    TOOLBAR_WIDTH - 2 * self.BUTTON_MARGIN, self.BUTTON_HEIGHT),
            })
            y += self.BUTTON_HEIGHT + self.BUTTON_MARGIN

        y += 4

        # Section: Special
        for comp_type in SPECIAL_TYPES:
            label = "CLK" if comp_type == "CLOCK" else comp_type
            self.buttons.append({
                "type": comp_type,
                "label": label,
                "rect": pygame.Rect(self.BUTTON_MARGIN, y,
                                    TOOLBAR_WIDTH - 2 * self.BUTTON_MARGIN, self.BUTTON_HEIGHT),
            })
            y += self.BUTTON_HEIGHT + self.BUTTON_MARGIN

        self.rect.height = y + 10

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle mouse events. Returns the component type if a button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered_index = -1
            for i, btn in enumerate(self.buttons):
                if btn["rect"].collidepoint(event.pos):
                    self.hovered_index = i
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, btn in enumerate(self.buttons):
                if btn["rect"].collidepoint(event.pos):
                    if self.active_type == btn["type"]:
                        self.active_type = None  # deselect
                    else:
                        self.active_type = btn["type"]
                    return btn["type"]

        return None

    def get_placement_type(self) -> str | None:
        """Return the currently selected component type for placement."""
        return self.active_type

    def clear_selection(self):
        """Clear the active toolbar selection."""
        self.active_type = None

    def render(self, screen: pygame.Surface):
        """Render the toolbar."""
        # Draw background
        toolbar_rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, screen.get_height())
        pygame.draw.rect(screen, COLOR_TOOLBAR_BG, toolbar_rect)

        # Draw separator line on right edge
        pygame.draw.line(screen, COLOR_TOOLBAR_SEPARATOR,
                         (TOOLBAR_WIDTH - 1, 0),
                         (TOOLBAR_WIDTH - 1, screen.get_height()), 1)

        font = pygame.font.Font(None, 14)

        for i, btn in enumerate(self.buttons):
            rect = btn["rect"]
            is_active = self.active_type == btn["type"]
            is_hovered = self.hovered_index == i

            # Determine color
            if is_active:
                color = COLOR_TOOLBAR_BUTTON_ACTIVE
            elif is_hovered:
                color = COLOR_TOOLBAR_BUTTON_HOVER
            else:
                color = COLOR_TOOLBAR_BUTTON

            pygame.draw.rect(screen, color, rect, border_radius=4)

            # Draw icon (simplified)
            self._draw_icon(screen, btn["type"], rect)

            # Draw label
            label = btn["label"]
            text_surf = font.render(label, True, COLOR_TOOLBAR_TEXT)
            text_rect = text_surf.get_rect(center=(rect.centerx, rect.bottom - 8))
            screen.blit(text_surf, text_rect)

    def _draw_icon(self, screen: pygame.Surface, comp_type: str, rect: pygame.Rect):
        """Draw a simple icon representing the component type."""
        cx, cy = rect.centerx, rect.centery - 4
        w, h = 24, 16

        color = COLOR_TOOLBAR_TEXT

        if comp_type == "AND":
            r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.rect(screen, color, r, 1, border_radius=2)
        elif comp_type == "OR":
            pts = [
                (cx - w // 2, cy - h // 2),
                (cx + w // 4, cy - h // 2),
                (cx + w // 2, cy),
                (cx + w // 4, cy + h // 2),
                (cx - w // 2, cy + h // 2),
            ]
            pygame.draw.polygon(screen, color, pts, 1)
        elif comp_type == "NOT":
            pts = [
                (cx - w // 2, cy - h // 2),
                (cx - w // 2, cy + h // 2),
                (cx + w // 2 - 3, cy),
            ]
            pygame.draw.polygon(screen, color, pts, 1)
            pygame.draw.circle(screen, color, (cx + w // 2, cy), 3, 1)
        elif comp_type == "NAND":
            r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.rect(screen, color, r, 1, border_radius=2)
            pygame.draw.circle(screen, color, (cx + w // 2 + 2, cy), 3, 1)
        elif comp_type == "NOR":
            pts = [
                (cx - w // 2, cy - h // 2),
                (cx + w // 4, cy - h // 2),
                (cx + w // 2, cy),
                (cx + w // 4, cy + h // 2),
                (cx - w // 2, cy + h // 2),
            ]
            pygame.draw.polygon(screen, color, pts, 1)
            pygame.draw.circle(screen, color, (cx + w // 2 + 2, cy), 3, 1)
        elif comp_type in ("XOR", "XNOR"):
            pts = [
                (cx - w // 2 + 4, cy - h // 2),
                (cx + w // 4, cy - h // 2),
                (cx + w // 2, cy),
                (cx + w // 4, cy + h // 2),
                (cx - w // 2 + 4, cy + h // 2),
            ]
            pygame.draw.polygon(screen, color, pts, 1)
            pygame.draw.arc(screen, color,
                            pygame.Rect(cx - w // 2 - 4, cy - h // 2, 12, h),
                            3.14159 * 0.5, 3.14159 * 1.5, 1)
            if comp_type == "XNOR":
                pygame.draw.circle(screen, color, (cx + w // 2 + 2, cy), 3, 1)
        elif comp_type == "INPUT":
            r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.rect(screen, color, r, 1, border_radius=2)
            # Arrow pointing right
            arrow_x = cx + 2
            pygame.draw.line(screen, color, (arrow_x - 4, cy), (arrow_x + 4, cy), 1)
            pygame.draw.line(screen, color, (arrow_x + 1, cy - 3), (arrow_x + 4, cy), 1)
            pygame.draw.line(screen, color, (arrow_x + 1, cy + 3), (arrow_x + 4, cy), 1)
        elif comp_type == "OUTPUT":
            r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.rect(screen, color, r, 1, border_radius=2)
            # Arrow pointing left into box
            pygame.draw.line(screen, color, (cx - 4, cy), (cx + 4, cy), 1)
            pygame.draw.line(screen, color, (cx - 1, cy - 3), (cx - 4, cy), 1)
            pygame.draw.line(screen, color, (cx - 1, cy + 3), (cx - 4, cy), 1)
        elif comp_type == "CLOCK":
            r = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.rect(screen, color, r, 1, border_radius=2)
            # Clock wave symbol
            mid = cx
            pygame.draw.line(screen, color, (mid - 6, cy), (mid - 3, cy - 4), 1)
            pygame.draw.line(screen, color, (mid - 3, cy - 4), (mid, cy), 1)
            pygame.draw.line(screen, color, (mid, cy), (mid + 3, cy + 4), 1)
            pygame.draw.line(screen, color, (mid + 3, cy + 4), (mid + 6, cy), 1)
        elif comp_type == "7SEG":
            # Mini 7-seg
            sw, sh = 10, 14
            sx, sy = cx - sw // 2, cy - sh // 2
            segs = [
                ((sx + 2, sy), (sx + sw - 2, sy)),
                ((sx + sw, sy + 2), (sx + sw, sy + sh // 2 - 1)),
                ((sx + sw, sy + sh // 2 + 1), (sx + sw, sy + sh - 2)),
                ((sx + 2, sy + sh), (sx + sw - 2, sy + sh)),
                ((sx, sy + sh // 2 + 1), (sx, sy + sh - 2)),
                ((sx, sy + 2), (sx, sy + sh // 2 - 1)),
                ((sx + 2, sy + sh // 2), (sx + sw - 2, sy + sh // 2)),
            ]
            for seg in segs:
                pygame.draw.line(screen, color, seg[0], seg[1], 1)
