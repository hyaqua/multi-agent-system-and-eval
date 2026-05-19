"""Toolbar and UI elements for logic gate simulator."""

import pygame
from typing import List, Tuple, Optional, Callable
from components import COMPONENT_DISPLAY_NAMES, TOOLBAR_ORDER
from components import Component, ClockGenerator


class ToolbarButton:
    """A button in the toolbar for selecting a component type."""

    def __init__(self, rect: pygame.Rect, comp_type: str, display_name: str):
        self.rect = rect
        self.comp_type = comp_type
        self.display_name = display_name
        self.selected: bool = False
        self.hovered: bool = False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        color = (180, 190, 210) if self.selected else (220, 220, 230)
        if self.hovered:
            color = (200, 210, 230)
        if self.selected:
            color = (140, 160, 200)

        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (80, 80, 100), self.rect, width=1, border_radius=4)

        text_surf = font.render(self.display_name, True, (20, 20, 20))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


class Toolbar:
    """Left-side toolbar for selecting components."""

    WIDTH = 170

    def __init__(self, screen_height: int):
        self.width = self.WIDTH
        self.height = screen_height
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.buttons: List[ToolbarButton] = []
        self.selected_type: Optional[str] = None
        self._create_buttons()

    def _create_buttons(self):
        """Create buttons for all component types."""
        self.buttons.clear()
        y = 38  # Start below the title and separator
        btn_width = self.width - 20
        btn_height = 30
        x = 10

        for comp_type in TOOLBAR_ORDER:
            display_name = COMPONENT_DISPLAY_NAMES.get(comp_type, comp_type)
            rect = pygame.Rect(x, y, btn_width, btn_height)
            btn = ToolbarButton(rect, comp_type, display_name)
            self.buttons.append(btn)
            y += btn_height + 3

    def handle_click(self, mouse_pos: Tuple[int, int]) -> Optional[str]:
        """Handle mouse click. Returns the selected component type or None."""
        mx, my = mouse_pos
        for btn in self.buttons:
            if btn.rect.collidepoint(mx, my):
                # Toggle selection
                if self.selected_type == btn.comp_type:
                    self.selected_type = None
                else:
                    self.selected_type = btn.comp_type
                self._update_selection()
                return self.selected_type
        return None

    def _update_selection(self):
        """Update button selected states."""
        for btn in self.buttons:
            btn.selected = (btn.comp_type == self.selected_type)

    def clear_selection(self):
        """Clear the current selection."""
        self.selected_type = None
        self._update_selection()

    def update_hover(self, mouse_pos: Tuple[int, int]):
        """Update hover states."""
        mx, my = mouse_pos
        for btn in self.buttons:
            btn.hovered = btn.rect.collidepoint(mx, my)

    def draw(self, screen: pygame.Surface):
        """Draw the toolbar."""
        # Draw background
        pygame.draw.rect(screen, (190, 195, 210), self.rect)
        pygame.draw.rect(screen, (100, 100, 120), self.rect, width=1)

        # Draw title
        try:
            title_font = pygame.font.Font(None, 18)
        except Exception:
            title_font = pygame.font.Font(None, 18)
        title = title_font.render("Components", True, (20, 20, 20))
        screen.blit(title, (10, 8))

        # Draw separator
        sep_y = 30
        pygame.draw.line(screen, (120, 120, 140), (5, sep_y), (self.width - 5, sep_y), 1)

        # Draw buttons
        try:
            font = pygame.font.Font(None, 13)
        except Exception:
            font = pygame.font.Font(None, 13)
        for btn in self.buttons:
            btn.draw(screen, font)

        # Draw instructions at bottom
        try:
            inst_font = pygame.font.Font(None, 11)
        except Exception:
            inst_font = pygame.font.Font(None, 11)

        instructions = [
            "Ctrl+S: Save",
            "Ctrl+O: Load",
            "Del: Delete",
            "Space+Drag: Pan",
            "Scroll: Zoom",
            "R-click wire: Delete",
            "R-click comp: Props",
        ]
        y = self.height - 120
        for line in instructions:
            text = inst_font.render(line, True, (60, 60, 80))
            screen.blit(text, (10, y))
            y += 15


class PropertiesPanel:
    """Floating panel for editing component properties."""

    def __init__(self):
        self.visible: bool = False
        self.component: Optional[Component] = None
        self.rect: pygame.Rect = pygame.Rect(0, 0, 200, 120)
        self.input_text: str = ""
        self.active_field: Optional[str] = None  # 'label' or 'frequency'
        self.cursor_visible: bool = True
        self.cursor_timer: float = 0.0

    def show(self, component: Component, screen_pos: Tuple[int, int]):
        """Show the properties panel for a component."""
        self.visible = True
        self.component = component
        self.rect.x = screen_pos[0]
        self.rect.y = screen_pos[1]
        self.input_text = component.label if component.label else ""
        self.active_field = None

    def hide(self):
        self.visible = False
        self.component = None
        self.active_field = None

    def handle_click(self, mouse_pos: Tuple[int, int]) -> bool:
        """Handle click within the panel. Returns True if click was handled."""
        if not self.visible:
            return False

        mx, my = mouse_pos

        # Check if click is inside panel
        if not self.rect.collidepoint(mx, my):
            self.hide()
            return False

        # Label field area
        label_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 30,
                                  self.rect.width - 20, 25)
        if label_rect.collidepoint(mx, my):
            self.active_field = 'label'
            self.input_text = self.component.label if self.component else ""
            return True

        # If it's a clock component, show frequency field
        if isinstance(self.component, ClockGenerator):
            freq_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 65,
                                     self.rect.width - 20, 25)
            if freq_rect.collidepoint(mx, my):
                self.active_field = 'frequency'
                self.input_text = str(self.component.frequency)
                return True

        # Close button area
        close_rect = pygame.Rect(self.rect.x + self.rect.width - 25, self.rect.y + 5, 20, 20)
        if close_rect.collidepoint(mx, my):
            self.hide()
            return True

        self.active_field = None
        return True

    def handle_key(self, event: pygame.event.Event):
        """Handle keyboard input for text fields."""
        if not self.visible or not self.active_field:
            return

        if event.key == pygame.K_RETURN:
            self._apply_change()
            self.active_field = None
        elif event.key == pygame.K_ESCAPE:
            self.active_field = None
        elif event.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        else:
            # Only allow valid characters
            if self.active_field == 'frequency':
                if event.unicode in '0123456789.':
                    self.input_text += event.unicode
            else:
                if len(self.input_text) < 30 and event.unicode.isprintable():
                    self.input_text += event.unicode

    def _apply_change(self):
        """Apply the text change to the component."""
        if not self.component:
            return

        if self.active_field == 'label':
            self.component.label = self.input_text
        elif self.active_field == 'frequency' and isinstance(self.component, ClockGenerator):
            try:
                freq = float(self.input_text)
                self.component.frequency = max(0.1, min(100.0, freq))
            except ValueError:
                pass

    def update(self, dt: float):
        self.cursor_timer += dt
        if self.cursor_timer > 0.5:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

    def draw(self, screen: pygame.Surface):
        """Draw the properties panel."""
        if not self.visible or not self.component:
            return

        # Draw background
        pygame.draw.rect(screen, (240, 240, 250), self.rect, border_radius=4)
        pygame.draw.rect(screen, (60, 60, 80), self.rect, width=2, border_radius=4)

        try:
            font = pygame.font.Font(None, 16)
            small_font = pygame.font.Font(None, 14)
        except Exception:
            font = pygame.font.Font(None, 16)
            small_font = pygame.font.Font(None, 14)

        # Title
        title = font.render(f"Properties: {self.component.get_type_name()}", True, (20, 20, 20))
        screen.blit(title, (self.rect.x + 10, self.rect.y + 8))

        # Close button
        close_rect = pygame.Rect(self.rect.x + self.rect.width - 25, self.rect.y + 5, 20, 20)
        pygame.draw.rect(screen, (200, 60, 60), close_rect, border_radius=2)
        x_text = small_font.render("X", True, (255, 255, 255))
        screen.blit(x_text, (close_rect.x + 6, close_rect.y + 3))

        # Label field
        label_text = small_font.render("Label:", True, (40, 40, 60))
        screen.blit(label_text, (self.rect.x + 10, self.rect.y + 30))
        label_field_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 45,
                                        self.rect.width - 20, 22)
        field_color = (255, 255, 255) if self.active_field == 'label' else (230, 230, 235)
        pygame.draw.rect(screen, field_color, label_field_rect)
        pygame.draw.rect(screen, (100, 100, 120), label_field_rect, width=1)

        label_display = self.input_text if self.active_field == 'label' else (self.component.label or "")
        label_surf = small_font.render(label_display, True, (20, 20, 20))
        screen.blit(label_surf, (label_field_rect.x + 3, label_field_rect.y + 3))

        # Cursor
        if self.active_field == 'label' and self.cursor_visible:
            cursor_x = label_field_rect.x + 3 + label_surf.get_width()
            pygame.draw.line(screen, (0, 0, 0),
                             (cursor_x, label_field_rect.y + 3),
                             (cursor_x, label_field_rect.y + 19), 1)

        # Frequency field (only for Clock)
        if isinstance(self.component, ClockGenerator):
            y_off = 30
            freq_label = small_font.render("Frequency (Hz):", True, (40, 40, 60))
            screen.blit(freq_label, (self.rect.x + 10, self.rect.y + 65))
            freq_field_rect = pygame.Rect(self.rect.x + 10, self.rect.y + 80,
                                           self.rect.width - 20, 22)
            f_color = (255, 255, 255) if self.active_field == 'frequency' else (230, 230, 235)
            pygame.draw.rect(screen, f_color, freq_field_rect)
            pygame.draw.rect(screen, (100, 100, 120), freq_field_rect, width=1)

            freq_display = self.input_text if self.active_field == 'frequency' else str(self.component.frequency)
            freq_surf = small_font.render(freq_display, True, (20, 20, 20))
            screen.blit(freq_surf, (freq_field_rect.x + 3, freq_field_rect.y + 3))

            if self.active_field == 'frequency' and self.cursor_visible:
                cursor_x = freq_field_rect.x + 3 + freq_surf.get_width()
                pygame.draw.line(screen, (0, 0, 0),
                                 (cursor_x, freq_field_rect.y + 3),
                                 (cursor_x, freq_field_rect.y + 19), 1)


class TextPrompt:
    """Simple text input overlay for save/load filenames."""

    def __init__(self):
        self.active: bool = False
        self.prompt_text: str = ""
        self.input_text: str = ""
        self.callback: Optional[Callable[[str], None]] = None
        self.rect: pygame.Rect = pygame.Rect(0, 0, 400, 100)

    def show(self, prompt: str, default: str, callback: Callable[[str], None],
             screen_center: Tuple[int, int]):
        """Show the text prompt."""
        self.active = True
        self.prompt_text = prompt
        self.input_text = default
        self.callback = callback
        self.rect.center = screen_center

    def hide(self):
        self.active = False
        self.callback = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle keyboard events. Returns True if event was consumed."""
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.callback:
                    self.callback(self.input_text)
                self.hide()
                return True
            elif event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return True
            elif len(self.input_text) < 50 and event.unicode.isprintable():
                self.input_text += event.unicode
                return True
        return False

    def draw(self, screen: pygame.Surface):
        """Draw the text prompt."""
        if not self.active:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        # Dialog box
        pygame.draw.rect(screen, (240, 240, 250), self.rect, border_radius=6)
        pygame.draw.rect(screen, (80, 80, 100), self.rect, width=2, border_radius=6)

        try:
            font = pygame.font.Font(None, 20)
            input_font = pygame.font.Font(None, 22)
        except Exception:
            font = pygame.font.Font(None, 20)
            input_font = pygame.font.Font(None, 22)

        # Prompt text
        prompt_surf = font.render(self.prompt_text, True, (20, 20, 20))
        screen.blit(prompt_surf, (self.rect.x + 15, self.rect.y + 12))

        # Input field
        field_rect = pygame.Rect(self.rect.x + 15, self.rect.y + 40,
                                  self.rect.width - 30, 30)
        pygame.draw.rect(screen, (255, 255, 255), field_rect)
        pygame.draw.rect(screen, (100, 100, 140), field_rect, width=1)

        input_surf = input_font.render(self.input_text + "_", True, (0, 0, 0))
        screen.blit(input_surf, (field_rect.x + 5, field_rect.y + 5))

        # Hint
        hint_surf = font.render("Enter to confirm, Esc to cancel", True, (100, 100, 120))
        screen.blit(hint_surf, (self.rect.x + 15, self.rect.y + 75))
