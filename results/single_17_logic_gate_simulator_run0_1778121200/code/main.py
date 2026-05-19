# main.py - Main entry point for the Logic Gate Simulator
import sys
import os
import pygame
from constants import *
from camera import Camera
from components import *
from wires import Wire
from circuit import Circuit
from io_manager import save_circuit, load_circuit, create_sample_circuits, get_samples_dir


class ToolbarButton:
    """A button in the toolbar for selecting a component type."""
    def __init__(self, x, y, w, h, comp_type, label, color=(80, 120, 180)):
        self.rect = pygame.Rect(x, y, w, h)
        self.comp_type = comp_type
        self.label = label
        self.color = color
        self.hovered = False
        self.selected = False

    def render(self, screen, font):
        bg = TOOLBAR_BUTTON_SELECTED if self.selected else (TOOLBAR_BUTTON_HOVER if self.hovered else TOOLBAR_BUTTON_BG)
        pygame.draw.rect(screen, bg, self.rect, border_radius=4)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 1, border_radius=4)

        # Color indicator
        indicator_rect = pygame.Rect(self.rect.x + 4, self.rect.y + 4, 8, self.rect.height - 8)
        pygame.draw.rect(screen, self.color, indicator_rect, border_radius=2)

        text = font.render(self.label, True, TEXT_COLOR)
        text_rect = text.get_rect(midleft=(self.rect.x + 18, self.rect.centery))
        screen.blit(text, text_rect)


class TextInput:
    """Simple text input for save/load dialogs."""
    def __init__(self):
        self.active = False
        self.text = ""
        self.prompt = ""
        self.callback = None
        self.cursor_visible = True
        self.cursor_timer = 0

    def activate(self, prompt, initial_text="", callback=None):
        self.active = True
        self.text = initial_text
        self.prompt = prompt
        self.callback = callback
        self.cursor_timer = 0

    def deactivate(self):
        self.active = False
        self.text = ""

    def handle_event(self, event):
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.callback and self.text.strip():
                    self.callback(self.text.strip())
                self.deactivate()
                return True
            elif event.key == pygame.K_ESCAPE:
                self.deactivate()
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            else:
                # Accept printable characters
                if len(self.text) < 60 and event.unicode and event.unicode.isprintable():
                    self.text += event.unicode
                    return True
        return False

    def update(self, dt):
        if self.active:
            self.cursor_timer += dt
            if self.cursor_timer > 0.5:
                self.cursor_timer = 0
                self.cursor_visible = not self.cursor_visible

    def render(self, screen, width, height):
        if not self.active:
            return
        # Darken background
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        # Dialog box
        dialog_w = 500
        dialog_h = 80
        dialog_x = (width - dialog_w) // 2
        dialog_y = height // 3
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)
        pygame.draw.rect(screen, PROPERTIES_BG, dialog_rect, border_radius=6)
        pygame.draw.rect(screen, PROPERTIES_BORDER, dialog_rect, 2, border_radius=6)

        # Prompt
        font = pygame.font.Font(None, FONT_MEDIUM)
        prompt_surf = font.render(self.prompt, True, TEXT_COLOR)
        screen.blit(prompt_surf, (dialog_x + 15, dialog_y + 10))

        # Text input
        input_y = dialog_y + 35
        input_rect = pygame.Rect(dialog_x + 15, input_y, dialog_w - 30, 30)
        pygame.draw.rect(screen, (30, 30, 30), input_rect)
        pygame.draw.rect(screen, PROPERTIES_BORDER, input_rect, 1)

        text = self.text
        if self.cursor_visible:
            text += "|"
        text_surf = font.render(text, True, TEXT_COLOR)
        screen.blit(text_surf, (input_rect.x + 8, input_rect.y + 5))

        # Help text
        font_small = pygame.font.Font(None, FONT_SMALL)
        help_surf = font_small.render("Enter to confirm, Esc to cancel", True, (150, 150, 150))
        screen.blit(help_surf, (dialog_x + 15, dialog_y + dialog_h - 18))


class PropertiesPanel:
    """Small panel for editing component properties."""
    def __init__(self):
        self.active = False
        self.component = None
        self.edit_text = ""
        self.editing_field = None  # "label" or "frequency"
        self.cursor_visible = True
        self.cursor_timer = 0

    def show(self, component, screen_x, screen_y):
        self.active = True
        self.component = component
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.edit_text = ""
        self.editing_field = None

    def hide(self):
        self.active = False
        self.component = None
        self.editing_field = None

    def handle_event(self, event, circuit):
        if not self.active or not self.component:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if click is outside panel
            mx, my = event.pos
            panel_rect = self._get_panel_rect()
            if not panel_rect.collidepoint(mx, my):
                self.hide()
                return True

            # Check field clicks
            if hasattr(self, '_label_rect') and self._label_rect.collidepoint(mx, my):
                self.editing_field = "label"
                self.edit_text = self.component.label
            elif hasattr(self, '_freq_rect') and self._freq_rect.collidepoint(mx, my):
                if isinstance(self.component, ClockGen):
                    self.editing_field = "frequency"
                    self.edit_text = str(self.component.frequency)
            else:
                self.editing_field = None

        if event.type == pygame.KEYDOWN and self.editing_field:
            if event.key == pygame.K_RETURN:
                self._apply_edit(circuit)
                self.editing_field = None
            elif event.key == pygame.K_ESCAPE:
                self.editing_field = None
            elif event.key == pygame.K_BACKSPACE:
                self.edit_text = self.edit_text[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self.edit_text) < 30:
                self.edit_text += event.unicode
            return True

        return False

    def _apply_edit(self, circuit):
        if self.editing_field == "label":
            self.component.label = self.edit_text
        elif self.editing_field == "frequency":
            try:
                freq = float(self.edit_text)
                if freq > 0:
                    self.component.frequency = freq
                    self.component.config["frequency"] = freq
            except ValueError:
                pass

    def _get_panel_rect(self):
        w = 220
        h = 120 if isinstance(self.component, ClockGen) else 80
        return pygame.Rect(self.screen_x, self.screen_y, w, h)

    def update(self, dt):
        if self.active:
            self.cursor_timer += dt
            if self.cursor_timer > 0.5:
                self.cursor_timer = 0
                self.cursor_visible = not self.cursor_visible

    def render(self, screen):
        if not self.active or not self.component:
            return

        panel_rect = self._get_panel_rect()
        # Clamp to screen
        if panel_rect.right > WINDOW_WIDTH:
            panel_rect.x = WINDOW_WIDTH - panel_rect.width - 10
        if panel_rect.bottom > WINDOW_HEIGHT:
            panel_rect.y = WINDOW_HEIGHT - panel_rect.height - 10
        if panel_rect.x < 0:
            panel_rect.x = 10
        if panel_rect.y < 0:
            panel_rect.y = 10

        pygame.draw.rect(screen, PROPERTIES_BG, panel_rect, border_radius=6)
        pygame.draw.rect(screen, PROPERTIES_BORDER, panel_rect, 2, border_radius=6)

        font = pygame.font.Font(None, FONT_MEDIUM)
        font_small = pygame.font.Font(None, FONT_SMALL)

        # Title
        title = font.render(f"Properties: {self.component.component_type}", True, TEXT_COLOR)
        screen.blit(title, (panel_rect.x + 10, panel_rect.y + 8))

        # Label field
        label_y = panel_rect.y + 30
        label_prompt = font_small.render("Label:", True, (180, 180, 180))
        screen.blit(label_prompt, (panel_rect.x + 10, label_y))

        label_rect = pygame.Rect(panel_rect.x + 70, label_y - 2, panel_rect.width - 85, 22)
        self._label_rect = label_rect
        pygame.draw.rect(screen, (30, 30, 30), label_rect)
        pygame.draw.rect(screen, PROPERTIES_BORDER, label_rect, 1)

        label_text = self.edit_text if self.editing_field == "label" else self.component.label
        if self.editing_field == "label" and self.cursor_visible:
            label_text += "|"
        text_surf = font_small.render(label_text, True, TEXT_COLOR)
        screen.blit(text_surf, (label_rect.x + 5, label_rect.y + 2))

        # Frequency field (only for Clock)
        if isinstance(self.component, ClockGen):
            freq_y = label_y + 28
            freq_prompt = font_small.render("Freq (Hz):", True, (180, 180, 180))
            screen.blit(freq_prompt, (panel_rect.x + 10, freq_y))

            freq_rect = pygame.Rect(panel_rect.x + 70, freq_y - 2, panel_rect.width - 85, 22)
            self._freq_rect = freq_rect
            pygame.draw.rect(screen, (30, 30, 30), freq_rect)
            pygame.draw.rect(screen, PROPERTIES_BORDER, freq_rect, 1)

            freq_text = self.edit_text if self.editing_field == "frequency" else str(self.component.frequency)
            if self.editing_field == "frequency" and self.cursor_visible:
                freq_text += "|"
            freq_surf = font_small.render(freq_text, True, TEXT_COLOR)
            screen.blit(freq_surf, (freq_rect.x + 5, freq_rect.y + 2))


class LogicGateSimulator:
    """Main application class."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Logic Gate Simulator")
        self.clock = pygame.time.Clock()
        self.running = True
        self.width = WINDOW_WIDTH
        self.height = WINDOW_HEIGHT

        # Camera
        self.camera = Camera(self.width, self.height, TOOLBAR_WIDTH)

        # Circuit
        self.circuit = Circuit()

        # UI
        self.toolbar_buttons = []
        self._build_toolbar()
        self.text_input = TextInput()
        self.properties_panel = PropertiesPanel()

        # Interaction state
        self.mode = "idle"  # idle, placing, wiring, dragging, rubber_band, panning
        self.placement_type = None  # Component type being placed
        self.ghost_pos = (0, 0)  # World position for placement ghost

        # Selection
        self.selected_component_ids = set()
        self.rubber_band_start = None
        self.rubber_band_end = None

        # Dragging
        self.drag_start_world = None
        self.drag_offsets = {}  # comp_id -> (offset_x, offset_y)

        # Wiring
        self.wire_start_comp = None
        self.wire_start_pin = None
        self.wire_mouse_world = (0, 0)

        # Panning
        self.pan_start_screen = None
        self.pan_start_offset = None
        self.space_held = False
        self.middle_dragging = False

        # Font
        self.font_small = pygame.font.Font(None, FONT_SMALL)
        self.font_medium = pygame.font.Font(None, FONT_MEDIUM)
        self.font_large = pygame.font.Font(None, FONT_LARGE)

        # Create sample circuits on first run
        self._ensure_samples()

        # Load default circuit (half adder) for demonstration
        sd = get_samples_dir()
        default_path = os.path.join(sd, "half_adder.json")
        if os.path.exists(default_path):
            loaded = load_circuit(default_path)
            if loaded:
                self.circuit = loaded
                self.circuit.get_highest_ids()

    def _ensure_samples(self):
        """Create sample circuits if they don't exist."""
        sd = get_samples_dir()
        samples = ["half_adder.json", "ripple_counter.json", "seven_segment_demo.json"]
        all_exist = all(os.path.exists(os.path.join(sd, s)) for s in samples)
        if not all_exist:
            create_sample_circuits()

    def _build_toolbar(self):
        """Build the toolbar buttons."""
        btn_w = TOOLBAR_WIDTH - 10
        btn_h = 36
        start_x = 5
        start_y = 10
        gap = 4

        components = [
            ("AND", "AND Gate", (60, 160, 60)),
            ("OR", "OR Gate", (60, 100, 200)),
            ("NOT", "NOT Gate", (200, 80, 80)),
            ("NAND", "NAND Gate", (160, 60, 60)),
            ("NOR", "NOR Gate", (60, 140, 200)),
            ("XOR", "XOR Gate", (200, 60, 200)),
            ("XNOR", "XNOR Gate", (160, 60, 160)),
            ("INPUT", "Input Node", (200, 200, 60)),
            ("OUTPUT", "Output Node", (60, 60, 200)),
            ("CLOCK", "Clock Gen", (200, 150, 50)),
            ("SEVEN_SEGMENT", "7-Seg Display", (200, 50, 50)),
        ]

        for i, (comp_type, label, color) in enumerate(components):
            y = start_y + i * (btn_h + gap)
            btn = ToolbarButton(start_x, y, btn_w, btn_h, comp_type, label, color)
            self.toolbar_buttons.append(btn)

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(60) / 1000.0  # delta time in seconds
            self._handle_events()
            self._update(dt)
            self._render()
        pygame.quit()
        sys.exit()

    def _handle_events(self):
        """Process all pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # Handle window resize
            if event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
                self.camera.width = self.width
                self.camera.height = self.height

            # Text input handling (highest priority for key events)
            if self.text_input.active:
                if self.text_input.handle_event(event):
                    continue

            # Properties panel
            if self.properties_panel.active:
                if self.properties_panel.handle_event(event, self.circuit):
                    continue

            # Handle key events
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            if event.type == pygame.KEYUP:
                self._handle_keyup(event)

            # Handle mouse events
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mousedown(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouseup(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mousemotion(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mousewheel(event)

    def _handle_keydown(self, event):
        """Handle key down events."""
        mods = pygame.key.get_mods()

        if event.key == pygame.K_ESCAPE:
            if self.properties_panel.active:
                self.properties_panel.hide()
            self._cancel_all_modes()

        elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            if self.selected_component_ids:
                for cid in list(self.selected_component_ids):
                    self.circuit.remove_component(cid)
                self.selected_component_ids.clear()

        elif event.key == pygame.K_SPACE:
            self.space_held = True

        elif event.key == pygame.K_s and (mods & pygame.KMOD_CTRL):
            # Save
            self.text_input.activate("Save circuit as:", "my_circuit.json",
                                     self._save_callback)

        elif event.key == pygame.K_o and (mods & pygame.KMOD_CTRL):
            # Load
            self.text_input.activate("Load circuit from:", "",
                                     self._load_callback)

        elif event.key == pygame.K_n and (mods & pygame.KMOD_CTRL):
            # New circuit
            self.circuit.clear()
            self.selected_component_ids.clear()
            self._cancel_all_modes()

    def _handle_keyup(self, event):
        if event.key == pygame.K_SPACE:
            self.space_held = False

    def _handle_mousedown(self, event):
        """Handle mouse button down."""
        mx, my = event.pos
        button = event.button

        # Check if click is on toolbar
        if mx < TOOLBAR_WIDTH:
            self._handle_toolbar_click(mx, my, button)
            return

        world_x, world_y = self.camera.screen_to_world(mx, my)

        if button == 1:  # Left click
            # Properties panel click-away
            if self.properties_panel.active:
                self.properties_panel.hide()

            # Space + left drag = panning
            if self.space_held:
                self.mode = "panning"
                self.pan_start_screen = (mx, my)
                self.pan_start_offset = (self.camera.offset_x, self.camera.offset_y)
                return

            if self.mode == "placing":
                # Place the component
                gx, gy = self.camera.snap_to_grid(world_x, world_y)
                comp = self.circuit.add_component(self.placement_type, gx, gy)
                if comp:
                    self.selected_component_ids = {comp.comp_id}
                # Stay in placement mode for multiple placements
                return

            if self.mode == "wiring":
                # Try to complete wire on an input pin
                pin_threshold = max(6, PIN_RADIUS * 2 / self.camera.zoom)
                comp, pin = self.circuit.get_pin_at(world_x, world_y, pin_threshold)
                if comp and pin and pin.is_input:
                    wire = self.circuit.add_wire(
                        self.wire_start_comp.comp_id, self.wire_start_pin.pin_id,
                        comp.comp_id, pin.pin_id
                    )
                    if wire:
                        pass  # Successfully created wire
                    self.mode = "idle"
                    self.wire_start_comp = None
                    self.wire_start_pin = None
                elif comp and pin and not pin.is_input:
                    # Clicked another output pin - restart wiring from there
                    self.wire_start_comp = comp
                    self.wire_start_pin = pin
                    self.wire_mouse_world = (world_x, world_y)
                else:
                    # Clicked empty space - cancel wiring
                    self.mode = "idle"
                    self.wire_start_comp = None
                    self.wire_start_pin = None
                return

            # Check if clicking on a pin to start wiring
            pin_threshold = max(6, PIN_RADIUS * 2 / self.camera.zoom)
            comp, pin = self.circuit.get_pin_at(world_x, world_y, pin_threshold)
            if comp and pin and not pin.is_input:
                # Start wiring from output pin
                self.mode = "wiring"
                self.wire_start_comp = comp
                self.wire_start_pin = pin
                self.wire_mouse_world = (world_x, world_y)
                return

            # Check if clicking on an input node to toggle it
            if comp and isinstance(comp, InputNode):
                if comp.contains_point(world_x, world_y):
                    shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
                    if not shift_held:
                        comp.toggle()
                    # Also select it
                    if shift_held:
                        if comp.comp_id in self.selected_component_ids:
                            self.selected_component_ids.discard(comp.comp_id)
                        else:
                            self.selected_component_ids.add(comp.comp_id)
                    else:
                        self.selected_component_ids = {comp.comp_id}
                    return

            # Check if clicking on a component
            if comp:
                shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
                if shift_held:
                    if comp.comp_id in self.selected_component_ids:
                        self.selected_component_ids.discard(comp.comp_id)
                    else:
                        self.selected_component_ids.add(comp.comp_id)
                else:
                    if comp.comp_id not in self.selected_component_ids:
                        self.selected_component_ids = {comp.comp_id}
                # Start dragging
                self.mode = "dragging"
                self.drag_start_world = (world_x, world_y)
                self.drag_offsets = {}
                for cid in self.selected_component_ids:
                    c = self.circuit.components.get(cid)
                    if c:
                        self.drag_offsets[cid] = (c.x - world_x, c.y - world_y)
                return

            # Start rubber band selection
            self.mode = "rubber_band"
            self.rubber_band_start = (world_x, world_y)
            self.rubber_band_end = (world_x, world_y)
            if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                self.selected_component_ids.clear()

        elif button == 2:  # Middle mouse - pan
            self.middle_dragging = True
            self.mode = "panning"
            self.pan_start_screen = (mx, my)
            self.pan_start_offset = (self.camera.offset_x, self.camera.offset_y)

        elif button == 3:  # Right click
            # Close properties panel if open
            if self.properties_panel.active:
                self.properties_panel.hide()

            if self.mode == "placing":
                self.mode = "idle"
                self.placement_type = None
                for btn in self.toolbar_buttons:
                    btn.selected = False
                return

            if self.mode == "wiring":
                self.mode = "idle"
                self.wire_start_comp = None
                self.wire_start_pin = None
                return

            # Check wire right-click for deletion
            wire_id = self.circuit.get_wire_at(world_x, world_y)
            if wire_id:
                self.circuit.remove_wire(wire_id)
                return

            # Check component right-click for properties
            comp = self.circuit.get_component_at(world_x, world_y)
            if comp:
                self.properties_panel.show(comp, mx, my)
                return

    def _handle_mouseup(self, event):
        """Handle mouse button up."""
        mx, my = event.pos
        button = event.button

        if button == 1:
            if self.mode == "rubber_band":
                # Finalize rubber band selection
                world_x, world_y = self.camera.screen_to_world(mx, my)
                self.rubber_band_end = (world_x, world_y)
                self._apply_rubber_band()
                self.rubber_band_start = None
                self.rubber_band_end = None
                self.mode = "idle"

            elif self.mode == "dragging":
                # Snap to grid after drag
                for cid in self.selected_component_ids:
                    comp = self.circuit.components.get(cid)
                    if comp:
                        gx, gy = self.camera.snap_to_grid(comp.x, comp.y)
                        comp.x = gx
                        comp.y = gy
                self.mode = "idle"
                self.drag_offsets.clear()

        elif button == 2:
            if self.middle_dragging:
                self.middle_dragging = False
                if self.mode == "panning":
                    self.mode = "idle"

    def _handle_mousemotion(self, event):
        """Handle mouse motion."""
        mx, my = event.pos
        world_x, world_y = self.camera.screen_to_world(mx, my)

        # Update toolbar hover states
        for btn in self.toolbar_buttons:
            btn.hovered = btn.rect.collidepoint(mx, my)

        if self.mode == "placing":
            self.ghost_pos = self.camera.snap_to_grid(world_x, world_y)

        elif self.mode == "wiring":
            self.wire_mouse_world = (world_x, world_y)

        elif self.mode == "dragging":
            for cid in list(self.selected_component_ids):
                comp = self.circuit.components.get(cid)
                if comp and cid in self.drag_offsets:
                    ox, oy = self.drag_offsets[cid]
                    comp.x = world_x + ox
                    comp.y = world_y + oy

        elif self.mode == "rubber_band":
            self.rubber_band_end = (world_x, world_y)

        elif self.mode == "panning" or self.middle_dragging:
            if self.pan_start_screen and self.pan_start_offset:
                dx = mx - self.pan_start_screen[0]
                dy = my - self.pan_start_screen[1]
                self.camera.offset_x = self.pan_start_offset[0] + dx / self.camera.zoom
                self.camera.offset_y = self.pan_start_offset[1] + dy / self.camera.zoom

        # Space + left drag panning
        if self.space_held and pygame.mouse.get_pressed()[0]:
            if self.mode not in ("panning", "dragging", "rubber_band"):
                # Just started space+drag
                if self.pan_start_screen is None:
                    self.pan_start_screen = (mx, my)
                    self.pan_start_offset = (self.camera.offset_x, self.camera.offset_y)
                    self.mode = "panning"
            if self.mode == "panning" and self.pan_start_screen:
                dx = mx - self.pan_start_screen[0]
                dy = my - self.pan_start_screen[1]
                self.camera.offset_x = self.pan_start_offset[0] + dx / self.camera.zoom
                self.camera.offset_y = self.pan_start_offset[1] + dy / self.camera.zoom
        elif self.mode == "panning" and not pygame.mouse.get_pressed()[0] and not self.middle_dragging:
            if not self.space_held:
                self.mode = "idle"
                self.pan_start_screen = None

    def _handle_mousewheel(self, event):
        """Handle scroll wheel zoom."""
        mx, my = pygame.mouse.get_pos()
        if mx < TOOLBAR_WIDTH:
            return
        factor = 1.1 if event.y > 0 else 0.9
        self.camera.zoom_at(mx, my, factor)

    def _handle_toolbar_click(self, mx, my, button):
        """Handle clicks on the toolbar."""
        if button != 1:
            return
        for btn in self.toolbar_buttons:
            if btn.rect.collidepoint(mx, my):
                # Select this component type for placement
                for b in self.toolbar_buttons:
                    b.selected = (b == btn)
                if btn.selected and self.mode == "placing" and self.placement_type == btn.comp_type:
                    # Clicking same button again exits placement mode
                    self.mode = "idle"
                    self.placement_type = None
                    btn.selected = False
                else:
                    self.mode = "placing"
                    self.placement_type = btn.comp_type
                    self.selected_component_ids.clear()
                return

    def _cancel_all_modes(self):
        """Cancel all interaction modes."""
        self.mode = "idle"
        self.placement_type = None
        self.wire_start_comp = None
        self.wire_start_pin = None
        self.rubber_band_start = None
        self.rubber_band_end = None
        self.drag_offsets.clear()
        self.pan_start_screen = None
        self.middle_dragging = False
        self.space_held = False
        for btn in self.toolbar_buttons:
            btn.selected = False

    def _apply_rubber_band(self):
        """Select components within the rubber band rectangle."""
        if not self.rubber_band_start or not self.rubber_band_end:
            return
        x1, y1 = self.rubber_band_start
        x2, y2 = self.rubber_band_end
        rx = min(x1, x2)
        ry = min(y1, y2)
        rw = abs(x2 - x1)
        rh = abs(y2 - y1)
        rect = pygame.Rect(rx, ry, rw, rh)

        for comp in self.circuit.components.values():
            bx, by, bw, bh = comp.get_bounds()
            comp_rect = pygame.Rect(bx, by, bw, bh)
            if rect.colliderect(comp_rect):
                self.selected_component_ids.add(comp.comp_id)

    def _update(self, dt):
        """Update simulation and UI."""
        # Update simulation
        self.circuit.simulate(dt)

        # Update UI
        self.text_input.update(dt)
        self.properties_panel.update(dt)

    def _render(self):
        """Render everything."""
        self.screen.fill(BG_COLOR)

        # Draw grid on canvas area
        self._draw_grid()

        # Draw wires
        cycle_wires = self.circuit.cycle_wires if self.circuit.has_cycle else set()
        for wire_id, wire in self.circuit.wires.items():
            highlight = wire_id in cycle_wires
            wire.render(self.screen, self.camera, self.circuit.components, highlight)

        # Draw wiring preview
        if self.mode == "wiring" and self.wire_start_comp and self.wire_start_pin:
            self._draw_wire_preview()

        # Draw components
        for comp in self.circuit.components.values():
            selected = comp.comp_id in self.selected_component_ids
            cycle_highlight = comp.comp_id in self.circuit.cycle_components
            comp.render(self.screen, self.camera, selected, cycle_highlight)

        # Draw placement ghost
        if self.mode == "placing" and self.placement_type:
            self._draw_placement_ghost()

        # Draw rubber band
        if self.mode == "rubber_band" and self.rubber_band_start and self.rubber_band_end:
            self._draw_rubber_band()

        # Draw toolbar
        self._draw_toolbar()

        # Draw overlay info
        self._draw_overlay()

        # Draw properties panel
        self.properties_panel.render(self.screen)

        # Draw text input dialog
        self.text_input.render(self.screen, self.width, self.height)

        # Draw cycle warning
        if self.circuit.has_cycle:
            self._draw_cycle_warning()

        pygame.display.flip()

    def _draw_grid(self):
        """Draw the dot-grid background on the canvas."""
        canvas_rect = pygame.Rect(TOOLBAR_WIDTH, 0, self.width - TOOLBAR_WIDTH, self.height)
        pygame.draw.rect(self.screen, BG_COLOR, canvas_rect)

        # Calculate visible world area
        x1_w, y1_w, x2_w, y2_w = self.camera.get_visible_rect()
        grid = GRID_SIZE

        # Find grid lines in view
        start_x = int(x1_w // grid) * grid
        start_y = int(y1_w // grid) * grid

        dot_size = max(1, int(1.5 * self.camera.zoom))
        for wx in range(int(start_x), int(x2_w + grid), grid):
            for wy in range(int(start_y), int(y2_w + grid), grid):
                sx, sy = self.camera.world_to_screen(wx, wy)
                if TOOLBAR_WIDTH <= sx < self.width and 0 <= sy < self.height:
                    pygame.draw.circle(self.screen, GRID_DOT_COLOR, (int(sx), int(sy)), dot_size)

        # Draw origin crosshair
        ox, oy = self.camera.world_to_screen(0, 0)
        if TOOLBAR_WIDTH <= ox < self.width and 0 <= oy < self.height:
            pygame.draw.line(self.screen, (100, 100, 100), (TOOLBAR_WIDTH, int(oy)), (self.width, int(oy)), 1)
            pygame.draw.line(self.screen, (100, 100, 100), (int(ox), 0), (int(ox), self.height), 1)

    def _draw_wire_preview(self):
        """Draw a preview of the wire being created."""
        pin = self.wire_start_pin
        comp = self.wire_start_comp
        px, py = pin.get_world_pos(comp.x, comp.y)
        mx, my = self.wire_mouse_world

        # Simple L-shaped preview
        mid_x = px + GRID_SIZE * 2
        path = [(px, py), (mid_x, py), (mid_x, my), (mx, my)]

        for i in range(len(path) - 1):
            s1 = self.camera.world_to_screen(path[i][0], path[i][1])
            s2 = self.camera.world_to_screen(path[i+1][0], path[i+1][1])
            pygame.draw.line(self.screen, WIRE_PREVIEW_COLOR, s1, s2, max(2, int(3 * self.camera.zoom)))

        # Draw a dot at the end
        ex, ey = self.camera.world_to_screen(mx, my)
        pygame.draw.circle(self.screen, WIRE_PREVIEW_COLOR, (int(ex), int(ey)), max(3, int(4 * self.camera.zoom)))

    def _draw_placement_ghost(self):
        """Draw a ghost of the component being placed."""
        gx, gy = self.ghost_pos
        sx, sy = self.camera.world_to_screen(gx, gy)

        # Create a temporary component for rendering
        if self.placement_type == "AND":
            w, h = GATE_WIDTH, GATE_HEIGHT
        elif self.placement_type == "NOT":
            w, h = NOT_WIDTH, NOT_HEIGHT
        elif self.placement_type in ("OR", "NAND", "NOR", "XOR", "XNOR"):
            w, h = GATE_WIDTH, GATE_HEIGHT
        elif self.placement_type in ("INPUT", "OUTPUT"):
            w, h = NODE_RADIUS * 2, NODE_RADIUS * 2
        elif self.placement_type == "CLOCK":
            w, h = CLOCK_SIZE, CLOCK_SIZE
        elif self.placement_type == "SEVEN_SEGMENT":
            w, h = SEVEN_SEG_WIDTH, SEVEN_SEG_HEIGHT
        else:
            w, h = GATE_WIDTH, GATE_HEIGHT

        rect = pygame.Rect(sx - w * self.camera.zoom / 2, sy - h * self.camera.zoom / 2,
                           w * self.camera.zoom, h * self.camera.zoom)
        ghost_surf = pygame.Surface((int(rect.width), int(rect.height)), pygame.SRCALPHA)
        ghost_surf.fill((100, 180, 255, 80))
        self.screen.blit(ghost_surf, (rect.x, rect.y))
        pygame.draw.rect(self.screen, (100, 180, 255), rect, 2)

        # Draw label
        font = pygame.font.Font(None, int(FONT_MEDIUM * self.camera.zoom))
        label = font.render(self.placement_type, True, (200, 220, 255))
        label_rect = label.get_rect(center=(sx, sy))
        self.screen.blit(label, label_rect)

    def _draw_rubber_band(self):
        """Draw the rubber band selection rectangle."""
        x1, y1 = self.rubber_band_start
        x2, y2 = self.rubber_band_end

        sx1, sy1 = self.camera.world_to_screen(x1, y1)
        sx2, sy2 = self.camera.world_to_screen(x2, y2)

        rx = min(sx1, sx2)
        ry = min(sy1, sy2)
        rw = abs(sx2 - sx1)
        rh = abs(sy2 - sy1)

        # Fill
        band_surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
        band_surf.fill((100, 180, 255, 40))
        self.screen.blit(band_surf, (rx, ry))
        # Border
        pygame.draw.rect(self.screen, RUBBER_BAND_BORDER, (rx, ry, rw, rh), 1)

    def _draw_toolbar(self):
        """Draw the toolbar panel."""
        # Background
        toolbar_rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, self.height)
        pygame.draw.rect(self.screen, TOOLBAR_BG, toolbar_rect)
        pygame.draw.line(self.screen, (80, 80, 80), (TOOLBAR_WIDTH - 1, 0), (TOOLBAR_WIDTH - 1, self.height), 2)

        # Title
        title = self.font_medium.render("Components", True, TEXT_COLOR)
        self.screen.blit(title, (8, 8))

        # Buttons
        for btn in self.toolbar_buttons:
            btn.render(self.screen, self.font_small)

        # Help text at bottom
        help_y = self.height - 120
        help_lines = [
            "Ctrl+S: Save",
            "Ctrl+O: Load",
            "Ctrl+N: New",
            "Del: Delete",
            "Space+Drag: Pan",
            "Scroll: Zoom",
            "RClick wire: Delete",
            "RClick comp: Props",
        ]
        for i, line in enumerate(help_lines):
            help_surf = self.font_small.render(line, True, (150, 150, 150))
            self.screen.blit(help_surf, (8, help_y + i * 16))

    def _draw_overlay(self):
        """Draw coordinate and zoom overlay."""
        mx, my = pygame.mouse.get_pos()
        if mx >= TOOLBAR_WIDTH:
            wx, wy = self.camera.screen_to_world(mx, my)
            coord_text = f"X: {wx:.0f}  Y: {wy:.0f}"
        else:
            coord_text = ""

        zoom_text = f"Zoom: {self.camera.zoom*100:.0f}%"

        font = pygame.font.Font(None, FONT_MEDIUM)

        # Background for overlay
        texts = []
        if coord_text:
            texts.append(coord_text)
        texts.append(zoom_text)

        if texts:
            max_w = 0
            total_h = 0
            for t in texts:
                s = font.render(t, True, TEXT_COLOR)
                max_w = max(max_w, s.get_width())
                total_h += s.get_height() + 2

            pad = 8
            overlay_rect = pygame.Rect(self.width - max_w - pad - 10, self.height - total_h - pad - 10,
                                        max_w + pad * 2, total_h + pad)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), overlay_rect, border_radius=4)
            pygame.draw.rect(self.screen, (80, 80, 80), overlay_rect, 1, border_radius=4)

            y = overlay_rect.y + pad // 2
            for t in texts:
                s = font.render(t, True, TEXT_COLOR)
                self.screen.blit(s, (overlay_rect.x + pad, y))
                y += s.get_height() + 2

    def _draw_cycle_warning(self):
        """Draw a warning message when cycles are detected."""
        warning_text = "⚠ CYCLE DETECTED - Combinational loop found!"
        font = pygame.font.Font(None, FONT_XL)
        text_surf = font.render(warning_text, True, WARNING_COLOR)
        text_rect = text_surf.get_rect(center=(self.width // 2, 30))
        # Background
        bg_rect = text_rect.inflate(20, 10)
        pygame.draw.rect(self.screen, (40, 0, 0), bg_rect, border_radius=4)
        pygame.draw.rect(self.screen, WARNING_COLOR, bg_rect, 2, border_radius=4)
        self.screen.blit(text_surf, text_rect)

    def _save_callback(self, filename):
        """Callback for save dialog."""
        if not filename.lower().endswith('.json'):
            filename += '.json'
        sd = get_samples_dir()
        filepath = os.path.join(sd, filename)
        save_circuit(self.circuit, filepath)
        print(f"Circuit saved to {filepath}")

    def _load_callback(self, filename):
        """Callback for load dialog."""
        if not filename.lower().endswith('.json'):
            filename += '.json'

        sd = get_samples_dir()
        # Check in multiple locations
        paths_to_try = [
            filename,
            os.path.join(sd, filename),
        ]
        for filepath in paths_to_try:
            if os.path.exists(filepath):
                loaded = load_circuit(filepath)
                if loaded:
                    self.circuit = loaded
                    self.circuit.get_highest_ids()
                    self.selected_component_ids.clear()
                    self._cancel_all_modes()
                    print(f"Loaded circuit from {filepath}")
                    return
        print(f"File not found: {filename}")


if __name__ == "__main__":
    simulator = LogicGateSimulator()
    simulator.run()
