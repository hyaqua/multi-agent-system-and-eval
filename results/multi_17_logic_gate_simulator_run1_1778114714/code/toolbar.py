"""Toolbar for selecting component types to place."""
import pygame
from config import (
    TOOLBAR_WIDTH, COLOR_TOOLBAR_BG, COLOR_TOOLBAR_BUTTON,
    COLOR_TOOLBAR_BUTTON_HOVER, COLOR_TOOLBAR_BUTTON_ACTIVE,
    COLOR_TOOLBAR_TEXT, FONT_SIZE_NORMAL,
)


class ToolbarButton:
    def __init__(self, rect, comp_type, label):
        self.rect = rect
        self.comp_type = comp_type
        self.label = label
        self.hovered = False
        self.active = False

    def draw(self, screen, font):
        color = COLOR_TOOLBAR_BUTTON
        if self.active:
            color = COLOR_TOOLBAR_BUTTON_ACTIVE
        elif self.hovered:
            color = COLOR_TOOLBAR_BUTTON_HOVER

        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, (100, 100, 120), self.rect, 1)

        text_surf = font.render(self.label, True, COLOR_TOOLBAR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


class Toolbar:
    """Fixed toolbar on the left side of the window."""
    BUTTONS = [
        ("AND", "AND Gate"),
        ("OR", "OR Gate"),
        ("NOT", "NOT Gate"),
        ("NAND", "NAND Gate"),
        ("NOR", "NOR Gate"),
        ("XOR", "XOR Gate"),
        ("XNOR", "XNOR Gate"),
        ("INPUT", "Input Node"),
        ("OUTPUT", "Output Node"),
        ("CLOCK", "Clock"),
        ("SEVEN_SEGMENT", "7-Segment"),
    ]

    def __init__(self, width=TOOLBAR_WIDTH):
        self.width = width
        self.buttons = []
        self.active_type = None
        self.rect = pygame.Rect(0, 0, width, 0)
        self._layout(800)  # placeholder height

    def _layout(self, window_height):
        """Layout buttons vertically."""
        self.buttons.clear()
        btn_w = self.width - 16
        btn_h = 36
        x = 8
        y = 10
        font = pygame.font.Font(None, FONT_SIZE_NORMAL)

        for comp_type, label in self.BUTTONS:
            rect = pygame.Rect(x, y, btn_w, btn_h)
            self.buttons.append(ToolbarButton(rect, comp_type, label))
            y += btn_h + 4

        self.rect.height = window_height

    def handle_event(self, event, canvas):
        """Handle mouse events on the toolbar. Returns selected type or None."""
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            for btn in self.buttons:
                btn.hovered = btn.rect.collidepoint(mx, my)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.rect.collidepoint(mx, my):
                for btn in self.buttons:
                    if btn.rect.collidepoint(mx, my):
                        # Toggle
                        if self.active_type == btn.comp_type:
                            self.active_type = None
                        else:
                            self.active_type = btn.comp_type
                        self._update_active()
                        return self.active_type
                # Clicked on toolbar but not on a button
                self.active_type = None
                self._update_active()
                return None
        return None

    def _update_active(self):
        for btn in self.buttons:
            btn.active = (btn.comp_type == self.active_type)

    def get_active_type(self):
        return self.active_type

    def set_active_type(self, comp_type):
        self.active_type = comp_type
        self._update_active()

    def draw(self, screen):
        """Draw the toolbar."""
        pygame.draw.rect(screen, COLOR_TOOLBAR_BG, self.rect)

        font = pygame.font.Font(None, FONT_SIZE_NORMAL)
        for btn in self.buttons:
            btn.draw(screen, font)

        # Title
        title_font = pygame.font.Font(None, 18)
        title_surf = title_font.render("Components", True, COLOR_TOOLBAR_TEXT)
        title_rect = title_surf.get_rect(center=(self.width // 2, self.rect.bottom - 20))
        screen.blit(title_surf, title_rect)
