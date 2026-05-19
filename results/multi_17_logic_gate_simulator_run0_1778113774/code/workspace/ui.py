"""UI module: toolbar, selection, dragging, wiring, properties panel, overlay."""

import pygame
from constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    TOOLBAR_WIDTH, TOOLBAR_PADDING, BUTTON_HEIGHT, BUTTON_SPACING,
    COLOR_TOOLBAR_BG, COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_BUTTON_ACTIVE,
    COLOR_BUTTON_TEXT, COLOR_SELECTION, COLOR_SELECTION_FILL,
    COLOR_RUBBERBAND, COLOR_RUBBERBAND_FILL, COLOR_OVERLAY,
    COLOR_PROPERTIES_BG, COLOR_PROPERTIES_BORDER, COLOR_PROPERTIES_TEXT,
    COLOR_INPUT_FIELD, COLOR_INPUT_FIELD_BORDER,
    GRID_SPACING, PIN_RADIUS,
    TOOLBAR_COMPONENTS,
)
from canvas import snap_to_grid, Camera
from circuit import Circuit
from wires import Wire
from components import (
    Component, Pin, get_component_label, create_component,
    InputNode, ClockGenerator,
)
from file_io import save_circuit, load_circuit, get_file_dialog_save, get_file_dialog_open


class UI:
    """Manages all user interaction."""

    def __init__(self, circuit: Circuit, camera: Camera):
        self.circuit = circuit
        self.camera = camera

        # Toolbar state
        self.toolbar_rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, WINDOW_HEIGHT)
        self.placement_mode = False
        self.placement_type: str | None = None

        # Selection state
        self.selected_ids: set[str] = set()
        self.dragging = False
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
        self.drag_started = False

        # Rubber band selection
        self.rubber_banding = False
        self.rubber_band_start: tuple[float, float] = (0, 0)
        self.rubber_band_end: tuple[float, float] = (0, 0)

        # Wiring state
        self.wiring = False
        self.wire_start_comp_id: str | None = None
        self.wire_start_pin_id: str | None = None
        self.wire_start_pos: tuple[float, float] | None = None
        self.wire_mouse_world: tuple[float, float] = (0, 0)

        # Panning
        self.panning = False
        self.pan_start: tuple[float, float] = (0, 0)
        self.space_held = False

        # Properties panel
        self.show_properties = False
        self.properties_comp_id: str | None = None
        self.properties_editing_name = False
        self.properties_name_buffer = ""
        self.properties_editing_freq = False
        self.properties_freq_buffer = ""

        # Overlay text
        self.mouse_world_x = 0.0
        self.mouse_world_y = 0.0

        # Hover tracking
        self.hovered_button_idx: int | None = None

    # ─── Drawing ──────────────────────────────────────────────────────────

    def draw_toolbar(self, surface: pygame.Surface):
        """Draw the component toolbar."""
        # Background
        pygame.draw.rect(surface, COLOR_TOOLBAR_BG, self.toolbar_rect)

        y = TOOLBAR_PADDING + 20
        font_size = 14
        try:
            font = pygame.font.SysFont("Arial", font_size, bold=True)
        except Exception:
            font = pygame.font.Font(None, font_size)

        # Title
        title = font.render("Components", True, COLOR_BUTTON_TEXT)
        title_rect = title.get_rect(center=(TOOLBAR_WIDTH / 2, y))
        surface.blit(title, title_rect)
        y += 30

        button_width = TOOLBAR_WIDTH - 2 * TOOLBAR_PADDING

        for i, comp_type in enumerate(TOOLBAR_COMPONENTS):
            btn_rect = pygame.Rect(
                TOOLBAR_PADDING, y,
                button_width, BUTTON_HEIGHT,
            )

            # Determine color
            if self.placement_mode and self.placement_type == comp_type:
                color = COLOR_BUTTON_ACTIVE
            elif self.hovered_button_idx == i:
                color = COLOR_BUTTON_HOVER
            else:
                color = COLOR_BUTTON

            pygame.draw.rect(surface, color, btn_rect, border_radius=4)
            pygame.draw.rect(surface, (100, 100, 110), btn_rect, 1, border_radius=4)

            label = get_component_label(comp_type)
            text = font.render(label, True, COLOR_BUTTON_TEXT)
            text_rect = text.get_rect(center=btn_rect.center)
            surface.blit(text, text_rect)

            y += BUTTON_HEIGHT + BUTTON_SPACING

    def draw_placement_preview(self, surface: pygame.Surface):
        """Draw preview of component being placed."""
        if not self.placement_mode or self.placement_type is None:
            return

        wx = snap_to_grid(self.mouse_world_x)
        wy = snap_to_grid(self.mouse_world_y)

        # Don't draw preview over toolbar
        sx, sy = self.camera.world_to_screen(wx, wy)
        if sx < TOOLBAR_WIDTH + 10:
            return

        # Create a temporary component for preview
        temp = create_component(self.placement_type, "_preview_", wx, wy)
        temp.draw(surface, self.camera, highlight=True)

    def draw_selection_highlight(self, surface: pygame.Surface):
        """Draw selection highlight on selected components."""
        for comp_id in self.selected_ids:
            comp = self.circuit.get_component_by_id(comp_id)
            if comp:
                # We don't redraw the component, just draw an extra highlight border
                pass  # Selection is drawn in the component's own draw method

    def draw_rubber_band(self, surface: pygame.Surface):
        """Draw rubber band selection rectangle."""
        if not self.rubber_banding:
            return

        x1, y1 = self.rubber_band_start
        x2, y2 = self.rubber_band_end
        rect = pygame.Rect(
            min(x1, x2), min(y1, y2),
            abs(x2 - x1), abs(y2 - y1),
        )

        # Create a semi-transparent surface for fill
        fill_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill_surf.fill(COLOR_RUBBERBAND_FILL)
        surface.blit(fill_surf, rect.topleft)

        pygame.draw.rect(surface, COLOR_RUBBERBAND, rect, 1)

    def draw_wire_preview(self, surface: pygame.Surface):
        """Draw preview wire during wiring."""
        if not self.wiring or self.wire_start_pos is None:
            return

        # Create a temporary wire for preview
        temp_wire = Wire("", "", "", "")
        temp_wire.update_routing(self.wire_start_pos, self.wire_mouse_world)
        temp_wire.draw(surface, self.camera, preview=True)

    def draw_cycle_warning(self, surface: pygame.Surface):
        """Draw cycle warning message."""
        msg = self.circuit.get_cycle_message()
        if msg is None:
            return

        try:
            font = pygame.font.SysFont("Arial", 20, bold=True)
        except Exception:
            font = pygame.font.Font(None, 20)
        text = font.render(msg, True, (255, 80, 80))
        text_rect = text.get_rect(center=(WINDOW_WIDTH / 2, 25))
        surface.blit(text, text_rect)

    def draw_overlay(self, surface: pygame.Surface):
        """Draw coordinate and zoom overlay."""
        wx = self.mouse_world_x
        wy = self.mouse_world_y
        zoom_pct = int(self.camera.zoom * 100)

        text = f"X: {wx:.0f}  Y: {wy:.0f}  Zoom: {zoom_pct}%"
        try:
            font = pygame.font.SysFont("Arial", 13)
        except Exception:
            font = pygame.font.Font(None, 13)

        # Draw semi-transparent background
        text_surf = font.render(text, True, (220, 220, 220))
        text_rect = text_surf.get_rect()
        text_rect.bottomright = (WINDOW_WIDTH - 15, WINDOW_HEIGHT - 15)

        bg_rect = text_rect.inflate(10, 6)
        bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 140))
        surface.blit(bg_surf, bg_rect.topleft)
        surface.blit(text_surf, text_rect)

    def draw_properties_panel(self, surface: pygame.Surface):
        """Draw properties panel for selected component."""
        if not self.show_properties or self.properties_comp_id is None:
            return

        comp = self.circuit.get_component_by_id(self.properties_comp_id)
        if comp is None:
            self.show_properties = False
            return

        # Position panel near the component on screen
        sx, sy = self.camera.world_to_screen(comp.x, comp.y)
        panel_x = sx + 60 * self.camera.zoom
        panel_y = sy - 40 * self.camera.zoom

        # Clamp to screen
        panel_w = 220
        panel_h = 120
        if panel_x + panel_w > WINDOW_WIDTH:
            panel_x = sx - panel_w - 60 * self.camera.zoom
        if panel_y + panel_h > WINDOW_HEIGHT:
            panel_y = WINDOW_HEIGHT - panel_h - 10
        if panel_y < 10:
            panel_y = 10
        if panel_x < TOOLBAR_WIDTH + 10:
            panel_x = TOOLBAR_WIDTH + 10

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # Background
        pygame.draw.rect(surface, COLOR_PROPERTIES_BG, panel_rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_PROPERTIES_BORDER, panel_rect, 2, border_radius=6)

        try:
            font = pygame.font.SysFont("Arial", 13)
            small_font = pygame.font.SysFont("Arial", 11)
        except Exception:
            font = pygame.font.Font(None, 13)
            small_font = pygame.font.Font(None, 11)

        y = panel_y + 8

        # Name field
        name_label = font.render("Name:", True, COLOR_PROPERTIES_TEXT)
        surface.blit(name_label, (panel_x + 8, y))
        y += 22

        # Name input field
        name_field_rect = pygame.Rect(panel_x + 8, y, panel_w - 16, 22)
        name_color = COLOR_INPUT_FIELD_BORDER if self.properties_editing_name else COLOR_INPUT_FIELD
        pygame.draw.rect(surface, name_color, name_field_rect, border_radius=3)
        pygame.draw.rect(surface, COLOR_PROPERTIES_BORDER, name_field_rect, 1, border_radius=3)

        display_name = self.properties_name_buffer if self.properties_editing_name else (comp.name or "")
        if not self.properties_editing_name and not comp.name:
            display_name = "(unnamed)"

        name_text = small_font.render(display_name, True, COLOR_PROPERTIES_TEXT)
        surface.blit(name_text, (panel_x + 12, y + 3))

        y += 30

        # Frequency field (only for clock)
        if isinstance(comp, ClockGenerator):
            freq_label = font.render("Frequency (Hz):", True, COLOR_PROPERTIES_TEXT)
            surface.blit(freq_label, (panel_x + 8, y))
            y += 22

            freq_field_rect = pygame.Rect(panel_x + 8, y, panel_w - 16, 22)
            freq_color = COLOR_INPUT_FIELD_BORDER if self.properties_editing_freq else COLOR_INPUT_FIELD
            pygame.draw.rect(surface, freq_color, freq_field_rect, border_radius=3)
            pygame.draw.rect(surface, COLOR_PROPERTIES_BORDER, freq_field_rect, 1, border_radius=3)

            display_freq = self.properties_freq_buffer if self.properties_editing_freq else f"{comp.frequency:.1f}"
            freq_text = small_font.render(display_freq, True, COLOR_PROPERTIES_TEXT)
            surface.blit(freq_text, (panel_x + 12, y + 3))

    # ─── Hit Testing ──────────────────────────────────────────────────────

    def get_toolbar_button(self, screen_x: float, screen_y: float) -> int | None:
        """Get toolbar button index at screen position."""
        if screen_x > TOOLBAR_WIDTH:
            return None

        y = TOOLBAR_PADDING + 20 + 30  # title + spacing
        button_width = TOOLBAR_WIDTH - 2 * TOOLBAR_PADDING

        for i in range(len(TOOLBAR_COMPONENTS)):
            btn_rect = pygame.Rect(
                TOOLBAR_PADDING, y,
                button_width, BUTTON_HEIGHT,
            )
            if btn_rect.collidepoint(screen_x, screen_y):
                return i
            y += BUTTON_HEIGHT + BUTTON_SPACING
        return None

    def is_over_toolbar(self, screen_x: float, screen_y: float) -> bool:
        return screen_x <= TOOLBAR_WIDTH

    def is_over_canvas(self, screen_x: float, screen_y: float) -> bool:
        return screen_x > TOOLBAR_WIDTH

    # ─── Event Handling ───────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event):
        """Process a Pygame event."""
        if event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(event)
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_mouse_wheel(event)
        elif event.type == pygame.KEYDOWN:
            self._handle_key_down(event)
        elif event.type == pygame.KEYUP:
            self._handle_key_up(event)

    def _handle_mouse_motion(self, event: pygame.event.Event):
        sx, sy = event.pos
        wx, wy = self.camera.screen_to_world(sx, sy)
        self.mouse_world_x = wx
        self.mouse_world_y = wy

        # Update hovered button
        self.hovered_button_idx = self.get_toolbar_button(sx, sy)

        # Panning
        if self.panning:
            dx = sx - self.pan_start[0]
            dy = sy - self.pan_start[1]
            self.camera.pan(dx, dy)
            self.pan_start = (sx, sy)
            return

        # Rubber band update
        if self.rubber_banding:
            self.rubber_band_end = (sx, sy)
            return

        # Wiring update
        if self.wiring:
            self.wire_mouse_world = (wx, wy)
            return

        # Dragging
        if self.dragging and self.selected_ids:
            if not self.drag_started:
                self.drag_started = True
            # Move selected components
            for comp_id in self.selected_ids:
                comp = self.circuit.get_component_by_id(comp_id)
                if comp:
                    new_x = wx - self.drag_offset_x
                    new_y = wy - self.drag_offset_y
                    # We need per-component offsets
                    pass
            # For single drag, compute offset relative to first selected
            self._drag_selected(wx, wy)

    def _handle_mouse_down(self, event: pygame.event.Event):
        sx, sy = event.pos
        wx, wy = self.camera.screen_to_world(sx, sy)

        # Right-click: properties or wire deletion
        if event.button == 3:
            if self.wiring:
                self.wiring = False
                return

            if self.placement_mode:
                self.placement_mode = False
                self.placement_type = None
                return

            # Check wire hit first
            wire = self.circuit.get_wire_at(wx, wy)
            if wire:
                self.circuit.remove_wire_by_ref(wire)
                return

            # Check component hit for properties
            if self.is_over_canvas(sx, sy):
                comp = self.circuit.get_component_at(wx, wy)
                if comp:
                    self._open_properties(comp)
                    return
            return

        # Left-click
        if event.button == 1:
            # Check if over toolbar
            if self.is_over_toolbar(sx, sy):
                btn_idx = self.get_toolbar_button(sx, sy)
                if btn_idx is not None:
                    comp_type = TOOLBAR_COMPONENTS[btn_idx]
                    if self.placement_mode and self.placement_type == comp_type:
                        self.placement_mode = False
                        self.placement_type = None
                    else:
                        self.placement_mode = True
                        self.placement_type = comp_type
                        self.selected_ids.clear()
                return

            # Over canvas
            # Close properties if open
            if self.show_properties:
                # Check if click is outside properties panel
                self._close_properties()

            # Placement mode
            if self.placement_mode and self.placement_type is not None:
                self._place_component(wx, wy)
                return

            # Check if middle-click is being used for panning (handled by button 2)

            # Check pin hit for wiring
            comp, pin = self.circuit.get_pin_at(wx, wy)
            if comp and pin:
                if not pin.is_input:
                    # Start wiring from output pin
                    self.wiring = True
                    self.wire_start_comp_id = comp.comp_id
                    self.wire_start_pin_id = pin.pin_id
                    self.wire_start_pos = pin.get_world_pos(comp.x, comp.y)
                    self.selected_ids.clear()
                    return
                else:
                    # If wiring, try to complete connection
                    if self.wiring and self.wire_start_comp_id is not None:
                        self._complete_wire(comp, pin)
                        return

            # Check component hit for selection
            if self.is_over_canvas(sx, sy):
                comp = self.circuit.get_component_at(wx, wy)
                if comp:
                    # Toggle input node
                    if isinstance(comp, InputNode):
                        # Check if we clicked on the component (not just its pin)
                        if comp.contains_point(wx, wy):
                            # Check if we're already wiring and clicked an input node
                            if not self.wiring:
                                # Only toggle if not holding shift (for multi-select)
                                mods = pygame.key.get_mods()
                                if mods & pygame.KMOD_SHIFT:
                                    if comp.comp_id in self.selected_ids:
                                        self.selected_ids.discard(comp.comp_id)
                                    else:
                                        self.selected_ids.add(comp.comp_id)
                                else:
                                    comp.toggle()
                                    self.circuit._dirty = True  # Force re-evaluation
                                return

                    # Handle selection
                    mods = pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        if comp.comp_id in self.selected_ids:
                            self.selected_ids.discard(comp.comp_id)
                        else:
                            self.selected_ids.add(comp.comp_id)
                    else:
                        if comp.comp_id not in self.selected_ids:
                            self.selected_ids.clear()
                            self.selected_ids.add(comp.comp_id)
                        # Start dragging
                        self.dragging = True
                        self.drag_started = False
                        self.drag_offset_x = wx - comp.x
                        self.drag_offset_y = wy - comp.y
                    return

                # Nothing hit - start rubber band or clear selection
                if not self.wiring:
                    self.selected_ids.clear()
                    self.rubber_banding = True
                    self.rubber_band_start = (sx, sy)
                    self.rubber_band_end = (sx, sy)

        # Middle-click: start panning
        if event.button == 2:
            self.panning = True
            self.pan_start = (sx, sy)
            return

        # Mouse button 4/5 (scroll wheel side buttons) - can be used for zoom
        if event.button == 4:
            self.camera.zoom_at(sx, sy, 1)
        if event.button == 5:
            self.camera.zoom_at(sx, sy, -1)

    def _handle_mouse_up(self, event: pygame.event.Event):
        sx, sy = event.pos
        wx, wy = self.camera.screen_to_world(sx, sy)

        if event.button == 2:
            self.panning = False

        if event.button == 1:
            # End rubber band
            if self.rubber_banding:
                self._finish_rubber_band()
                self.rubber_banding = False

            # End dragging
            if self.dragging:
                self.dragging = False
                self.drag_started = False

    def _handle_mouse_wheel(self, event: pygame.event.Event):
        sx, sy = pygame.mouse.get_pos()
        direction = event.y  # 1 for up, -1 for down
        self.camera.zoom_at(sx, sy, direction)

    def _handle_key_down(self, event: pygame.event.Event):
        # Properties text input
        if self.show_properties:
            if self.properties_editing_name:
                if event.key == pygame.K_RETURN:
                    self._commit_properties_name()
                elif event.key == pygame.K_ESCAPE:
                    self.properties_editing_name = False
                    self.properties_name_buffer = ""
                elif event.key == pygame.K_BACKSPACE:
                    self.properties_name_buffer = self.properties_name_buffer[:-1]
                else:
                    if event.unicode.isprintable():
                        self.properties_name_buffer += event.unicode
                return

            if self.properties_editing_freq:
                if event.key == pygame.K_RETURN:
                    self._commit_properties_freq()
                elif event.key == pygame.K_ESCAPE:
                    self.properties_editing_freq = False
                    self.properties_freq_buffer = ""
                elif event.key == pygame.K_BACKSPACE:
                    self.properties_freq_buffer = self.properties_freq_buffer[:-1]
                else:
                    if event.unicode.isprintable() and event.unicode in "0123456789.":
                        self.properties_freq_buffer += event.unicode
                return

        # Global hotkeys
        if event.key == pygame.K_DELETE:
            self._delete_selected()
            return

        if event.key == pygame.K_SPACE:
            self.space_held = True
            return

        if event.key == pygame.K_ESCAPE:
            if self.wiring:
                self.wiring = False
            elif self.placement_mode:
                self.placement_mode = False
                self.placement_type = None
            elif self.show_properties:
                self._close_properties()
            else:
                self.selected_ids.clear()
            return

        # Ctrl+S save
        if event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._save_circuit()
            return

        # Ctrl+O open
        if event.key == pygame.K_o and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._load_circuit()
            return

    def _handle_key_up(self, event: pygame.event.Event):
        if event.key == pygame.K_SPACE:
            self.space_held = False
            # Also stop panning if we were using space+left drag
            if self.panning and not pygame.mouse.get_pressed()[1]:
                self.panning = False

    # ─── Actions ──────────────────────────────────────────────────────────

    def _place_component(self, wx: float, wy: float):
        """Place a component at world position."""
        comp_id = self.circuit.generate_id()
        comp = create_component(self.placement_type, comp_id, wx, wy)
        self.circuit.add_component(comp)
        # Don't exit placement mode - allow placing multiple
        # But select the newly placed component
        self.selected_ids.clear()
        self.selected_ids.add(comp_id)

    def _complete_wire(self, dest_comp: Component, dest_pin: Pin):
        """Complete a wire connection."""
        if not dest_pin.is_input:
            return

        # Don't connect to self
        if self.wire_start_comp_id == dest_comp.comp_id:
            self.wiring = False
            return

        # Get start pin world position
        start_comp = self.circuit.get_component_by_id(self.wire_start_comp_id)
        if start_comp is None:
            self.wiring = False
            return

        from_pos = start_comp.get_pin_world_pos(self.wire_start_pin_id)
        to_pos = dest_comp.get_pin_world_pos(dest_pin.pin_id)

        if from_pos is None or to_pos is None:
            self.wiring = False
            return

        wire = Wire(
            from_component_id=self.wire_start_comp_id,
            from_pin_id=self.wire_start_pin_id,
            to_component_id=dest_comp.comp_id,
            to_pin_id=dest_pin.pin_id,
        )
        wire.update_routing(from_pos, to_pos)
        self.circuit.add_wire(wire)

        self.wiring = False
        self.wire_start_comp_id = None
        self.wire_start_pin_id = None
        self.wire_start_pos = None

    def _drag_selected(self, wx: float, wy: float):
        """Drag all selected components."""
        if not self.selected_ids:
            return

        # Use the offset from the first drag
        for comp_id in self.selected_ids:
            comp = self.circuit.get_component_by_id(comp_id)
            if comp:
                new_x = wx - self.drag_offset_x
                new_y = wy - self.drag_offset_y
                self.circuit.move_component(comp_id, new_x, new_y)

    def _finish_rubber_band(self):
        """Complete rubber band selection."""
        x1, y1 = self.rubber_band_start
        x2, y2 = self.rubber_band_end
        rect = pygame.Rect(
            min(x1, x2), min(y1, y2),
            abs(x2 - x1), abs(y2 - y1),
        )

        # Convert to world coordinates
        wx1, wy1 = self.camera.screen_to_world(rect.left, rect.top)
        wx2, wy2 = self.camera.screen_to_world(rect.right, rect.bottom)
        world_rect = pygame.Rect(
            min(wx1, wx2), min(wy1, wy2),
            abs(wx2 - wx1), abs(wy2 - wy1),
        )

        self.selected_ids.clear()
        for comp in self.circuit.components:
            if world_rect.colliderect(comp.get_rect()):
                self.selected_ids.add(comp.comp_id)

    def _delete_selected(self):
        """Delete all selected components."""
        for comp_id in list(self.selected_ids):
            self.circuit.remove_component(comp_id)
        self.selected_ids.clear()

    def _open_properties(self, comp: Component):
        """Open properties panel for a component."""
        self.show_properties = True
        self.properties_comp_id = comp.comp_id
        self.properties_name_buffer = comp.name or ""
        self.properties_editing_name = False
        self.properties_editing_freq = False
        self.properties_freq_buffer = ""
        if isinstance(comp, ClockGenerator):
            self.properties_freq_buffer = f"{comp.frequency:.1f}"

    def _close_properties(self):
        """Close and commit properties panel."""
        self._commit_properties_name()
        self._commit_properties_freq()
        self.show_properties = False
        self.properties_comp_id = None
        self.properties_editing_name = False
        self.properties_editing_freq = False

    def _commit_properties_name(self):
        """Apply name from buffer."""
        if self.properties_comp_id is None:
            return
        comp = self.circuit.get_component_by_id(self.properties_comp_id)
        if comp:
            comp.name = self.properties_name_buffer.strip()
        self.properties_editing_name = False

    def _commit_properties_freq(self):
        """Apply frequency from buffer."""
        if self.properties_comp_id is None:
            return
        comp = self.circuit.get_component_by_id(self.properties_comp_id)
        if comp and isinstance(comp, ClockGenerator):
            try:
                freq = float(self.properties_freq_buffer)
                if freq > 0:
                    comp.frequency = freq
                    comp._last_toggle_time = pygame.time.get_ticks()
            except ValueError:
                pass
        self.properties_editing_freq = False

    def _save_circuit(self):
        """Save circuit to file."""
        filepath = get_file_dialog_save()
        if filepath:
            save_circuit(self.circuit, filepath)

    def _load_circuit(self):
        """Load circuit from file."""
        filepath = get_file_dialog_open()
        if filepath:
            load_circuit(self.circuit, filepath)
            self.selected_ids.clear()
            self.wiring = False
            self.placement_mode = False
            self.placement_type = None
            self.show_properties = False

    # ─── Update (called each frame) ───────────────────────────────────────

    def update(self):
        """Per-frame update. Checks for space+left-click panning."""
        # Handle space+left drag for panning
        if self.space_held:
            mouse_pressed = pygame.mouse.get_pressed()
            if mouse_pressed[0] and not self.panning:
                # Start panning with space+left click
                sx, sy = pygame.mouse.get_pos()
                if sx > TOOLBAR_WIDTH:
                    self.panning = True
                    self.pan_start = (sx, sy)
            elif not mouse_pressed[0] and self.panning:
                self.panning = False

    def is_panning(self) -> bool:
        return self.panning

    def is_dragging(self) -> bool:
        return self.dragging
