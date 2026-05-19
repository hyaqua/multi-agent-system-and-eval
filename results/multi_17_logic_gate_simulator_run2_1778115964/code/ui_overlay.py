"""UI overlays: coordinate display, cycle warning, properties panel, file dialog."""

from __future__ import annotations

import pygame
from typing import Optional, TYPE_CHECKING

from config import (
    COLOR_OVERLAY_BG, COLOR_TEXT, COLOR_CYCLE_WARNING_BG, COLOR_CYCLE_WARNING_TEXT,
    COLOR_PROPERTIES_BG, COLOR_PROPERTIES_BORDER, COLOR_PROPERTIES_TEXT,
    COLOR_INPUT_DIALOG_BG, COLOR_INPUT_DIALOG_BORDER, COLOR_INPUT_DIALOG_TEXT,
    COLOR_HIGH, COLOR_LOW, DEFAULT_CLOCK_FREQ,
)

if TYPE_CHECKING:
    from camera import Camera
    from components import Component
    from simulation import Simulator


class UIOverlay:
    """Manages and renders various UI overlays."""

    def __init__(self):
        self.show_properties: bool = False
        self.properties_component: Optional['Component'] = None
        self.properties_panel_rect: Optional[pygame.Rect] = None

        self.show_file_dialog: bool = False
        self.file_dialog_prompt: str = ""
        self.file_dialog_text: str = ""
        self.file_dialog_callback = None  # function(filepath)

        self.show_cycle_warning: bool = False

    def open_properties(self, component: 'Component', screen_pos: tuple):
        """Open the properties panel for a component."""
        self.show_properties = True
        self.properties_component = component
        # Position panel near the click
        self.properties_panel_rect = pygame.Rect(
            screen_pos[0] + 10, screen_pos[1] + 10, 220, 120
        )

    def close_properties(self):
        """Close the properties panel."""
        self.show_properties = False
        self.properties_component = None
        self.properties_panel_rect = None

    def open_file_dialog(self, prompt: str, callback):
        """Open a text input dialog for filename entry."""
        self.show_file_dialog = True
        self.file_dialog_prompt = prompt
        self.file_dialog_text = ""
        self.file_dialog_callback = callback

    def close_file_dialog(self, confirm: bool = True):
        """Close the file dialog and optionally trigger the callback."""
        if confirm and self.file_dialog_callback and self.file_dialog_text.strip():
            self.file_dialog_callback(self.file_dialog_text.strip())
        self.show_file_dialog = False
        self.file_dialog_text = ""
        self.file_dialog_callback = None

    def handle_file_dialog_event(self, event: pygame.event.Event):
        """Handle keyboard events for the file dialog."""
        if not self.show_file_dialog:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.close_file_dialog(confirm=True)
                return True
            elif event.key == pygame.K_ESCAPE:
                self.close_file_dialog(confirm=False)
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.file_dialog_text = self.file_dialog_text[:-1]
                return True
            else:
                # Only accept printable characters and common filename chars
                if event.unicode and event.unicode.isprintable():
                    self.file_dialog_text += event.unicode
                    return True

        return False

    def handle_properties_event(self, event: pygame.event.Event, simulator: 'Simulator'):
        """Handle events for the properties panel."""
        if not self.show_properties or self.properties_component is None:
            return False

        comp = self.properties_component

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close_properties()
                return True
            elif event.key == pygame.K_BACKSPACE:
                # Edit name
                name = comp.config.get("name", "")
                comp.config["name"] = name[:-1]
                return True
            elif event.key == pygame.K_RETURN:
                self.close_properties()
                return True
            elif event.unicode and event.unicode.isprintable():
                name = comp.config.get("name", "")
                comp.config["name"] = name + event.unicode
                return True

        # Handle mouse clicks for frequency adjustment (clock)
        if event.type == pygame.MOUSEBUTTONDOWN and self.properties_panel_rect:
            if comp.type_name == "CLOCK":
                # Check for +/- button clicks
                mx, my = event.pos
                panel = self.properties_panel_rect

                # Plus button area
                plus_rect = pygame.Rect(panel.right - 60, panel.top + 60, 24, 20)
                minus_rect = pygame.Rect(panel.right - 30, panel.top + 60, 24, 20)

                freq = comp.config.get("frequency", DEFAULT_CLOCK_FREQ)

                if plus_rect.collidepoint(mx, my):
                    comp.config["frequency"] = min(1000.0, freq * 2)
                    return True
                elif minus_rect.collidepoint(mx, my):
                    comp.config["frequency"] = max(0.1, freq / 2)
                    return True

        return False

    def update_cycle_warning(self, simulator: 'Simulator'):
        """Update the cycle warning state."""
        self.show_cycle_warning = simulator.cycle_error

    def render_coordinates(self, screen: pygame.Surface, camera: 'Camera',
                           mouse_world: pygame.Vector2):
        """Render coordinate display and zoom percentage in bottom-right corner."""
        zoom_pct = int(camera.zoom * 100)
        text = f"World: ({mouse_world.x:.0f}, {mouse_world.y:.0f})  Zoom: {zoom_pct}%"

        font = pygame.font.Font(None, 20)
        text_surf = font.render(text, True, COLOR_TEXT)

        # Background
        padding = 6
        bg_rect = text_surf.get_rect(bottomright=(screen.get_width() - 10, screen.get_height() - 10))
        bg_rect.inflate_ip(padding * 2, padding * 2)

        bg = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg.fill(COLOR_OVERLAY_BG)
        screen.blit(bg, bg_rect.topleft)

        screen.blit(text_surf, text_surf.get_rect(
            bottomright=(screen.get_width() - 10 - padding, screen.get_height() - 10 - padding)
        ))

    def render_cycle_warning(self, screen: pygame.Surface):
        """Render cycle detection warning at top-center."""
        if not self.show_cycle_warning:
            return

        text = "⚠ Cycle Detected – Remove a wire in the loop ⚠"
        font = pygame.font.Font(None, 28)
        text_surf = font.render(text, True, COLOR_CYCLE_WARNING_TEXT)

        bg_rect = text_surf.get_rect(center=(screen.get_width() // 2, 30))
        bg_rect.inflate_ip(20, 10)

        bg = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg.fill((*COLOR_CYCLE_WARNING_BG, 200))
        screen.blit(bg, bg_rect.topleft)
        screen.blit(text_surf, text_surf.get_rect(center=(screen.get_width() // 2, 30)))

    def render_properties(self, screen: pygame.Surface, camera: 'Camera'):
        """Render the properties panel."""
        if not self.show_properties or self.properties_component is None or \
           self.properties_panel_rect is None:
            return

        comp = self.properties_component
        panel = self.properties_panel_rect

        # Draw panel background
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((*COLOR_PROPERTIES_BG, 230))
        screen.blit(bg, panel.topleft)
        pygame.draw.rect(screen, COLOR_PROPERTIES_BORDER, panel, 1)

        font = pygame.font.Font(None, 18)
        small_font = pygame.font.Font(None, 14)

        y = panel.top + 8
        x = panel.left + 10

        # Title
        title = f"Properties: {comp.type_name}"
        title_surf = font.render(title, True, COLOR_PROPERTIES_TEXT)
        screen.blit(title_surf, (x, y))
        y += 22

        # ID
        id_text = f"ID: {comp.id[:8]}..."
        id_surf = small_font.render(id_text, True, COLOR_PROPERTIES_TEXT)
        screen.blit(id_surf, (x, y))
        y += 18

        # Name
        name_text = f"Name: {comp.config.get('name', '')}"
        name_surf = small_font.render(name_text, True, COLOR_PROPERTIES_TEXT)
        screen.blit(name_surf, (x, y))
        y += 18

        # Clock frequency
        if comp.type_name == "CLOCK":
            freq = comp.config.get("frequency", DEFAULT_CLOCK_FREQ)
            freq_text = f"Frequency: {freq:.1f} Hz"
            freq_surf = small_font.render(freq_text, True, COLOR_PROPERTIES_TEXT)
            screen.blit(freq_surf, (x, y))

            # Draw +/- buttons
            plus_rect = pygame.Rect(panel.right - 60, panel.top + 60, 24, 20)
            minus_rect = pygame.Rect(panel.right - 30, panel.top + 60, 24, 20)

            pygame.draw.rect(screen, (80, 120, 80), plus_rect, border_radius=3)
            pygame.draw.rect(screen, (120, 80, 80), minus_rect, border_radius=3)

            plus_surf = small_font.render("+", True, COLOR_PROPERTIES_TEXT)
            minus_surf = small_font.render("-", True, COLOR_PROPERTIES_TEXT)
            screen.blit(plus_surf, plus_surf.get_rect(center=plus_rect.center))
            screen.blit(minus_surf, minus_surf.get_rect(center=minus_rect.center))

        # Hint
        hint = "Type to rename, Esc to close"
        hint_surf = small_font.render(hint, True, (140, 140, 160))
        screen.blit(hint_surf, (x, panel.bottom - 18))

    def render_file_dialog(self, screen: pygame.Surface):
        """Render the file dialog."""
        if not self.show_file_dialog:
            return

        sw, sh = screen.get_width(), screen.get_height()
        dialog_w, dialog_h = 400, 100
        dialog_rect = pygame.Rect(
            (sw - dialog_w) // 2, (sh - dialog_h) // 2,
            dialog_w, dialog_h
        )

        # Background
        bg = pygame.Surface(dialog_rect.size, pygame.SRCALPHA)
        bg.fill((*COLOR_INPUT_DIALOG_BG, 240))
        screen.blit(bg, dialog_rect.topleft)
        pygame.draw.rect(screen, COLOR_INPUT_DIALOG_BORDER, dialog_rect, 2)

        font = pygame.font.Font(None, 22)
        small_font = pygame.font.Font(None, 16)

        # Prompt
        prompt_surf = font.render(self.file_dialog_prompt, True, COLOR_INPUT_DIALOG_TEXT)
        screen.blit(prompt_surf, (dialog_rect.left + 12, dialog_rect.top + 10))

        # Text input field
        input_rect = pygame.Rect(
            dialog_rect.left + 10, dialog_rect.top + 38,
            dialog_w - 20, 28
        )
        pygame.draw.rect(screen, (40, 40, 55), input_rect)
        pygame.draw.rect(screen, COLOR_INPUT_DIALOG_BORDER, input_rect, 1)

        # Cursor and text
        display_text = self.file_dialog_text
        text_surf = font.render(display_text, True, COLOR_INPUT_DIALOG_TEXT)
        screen.blit(text_surf, (input_rect.left + 6, input_rect.top + 4))

        # Blinking cursor
        if pygame.time.get_ticks() % 800 < 400:
            cursor_x = input_rect.left + 6 + text_surf.get_width() + 1
            pygame.draw.line(screen, COLOR_INPUT_DIALOG_TEXT,
                             (cursor_x, input_rect.top + 4),
                             (cursor_x, input_rect.bottom - 4), 1)

        # Hint
        hint = "Enter: confirm  Esc: cancel"
        hint_surf = small_font.render(hint, True, (140, 140, 160))
        screen.blit(hint_surf, (dialog_rect.left + 10, dialog_rect.bottom - 20))
