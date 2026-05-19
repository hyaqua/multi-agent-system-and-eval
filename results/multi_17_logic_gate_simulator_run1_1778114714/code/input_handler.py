"""Input manager: finite-state machine for mouse/keyboard modes."""
import math
import pygame
from config import (
    COLOR_SELECTION_RECT, COLOR_WIRE_PREVIEW, PIN_RADIUS, TOOLBAR_WIDTH,
)
from components import InputNode, Clock


class InputManager:
    """Handles all user input and manages interaction modes."""

    MODE_IDLE = "idle"
    MODE_PLACING = "placing"
    MODE_DRAGGING = "dragging"
    MODE_RUBBER_BAND = "rubber_band"
    MODE_WIRE_DRAWING = "wire_drawing"
    MODE_PANNING = "panning"

    def __init__(self, canvas, circuit, toolbar):
        self.canvas = canvas
        self.circuit = circuit
        self.toolbar = toolbar
        self.mode = self.MODE_IDLE

        # Selection
        self.selected_ids = set()
        self.rubber_start = None
        self.rubber_end = None

        # Dragging
        self.drag_start_world = None
        self.drag_offsets = {}  # comp_id -> (offset_x, offset_y)

        # Wire drawing
        self.wire_source_comp = None
        self.wire_source_pin = None
        self.wire_mouse_world = (0, 0)

        # Panning
        self.pan_start_screen = None
        self.pan_start_offset = None
        self.space_held = False
        self.middle_dragging = False

        # Property panel
        self.property_target = None  # component for property panel
        self.property_input = ""  # text being edited
        self.property_field = None  # "label" or "freq"

        # Text input dialog (for save/load)
        self.dialog_callback = None
        self.dialog_text = ""
        self.dialog_title = ""

    def handle_event(self, event):
        """Process a single pygame event."""
        if self.dialog_callback is not None:
            self._handle_dialog_event(event)
            return

        if self.property_target is not None:
            if self._handle_property_event(event):
                return

        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
        elif event.type == pygame.KEYUP:
            self._handle_keyup(event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mousemotion(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mousedown(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouseup(event)

    def _handle_keydown(self, event):
        """Handle key press."""
        if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            self._delete_selected()

        elif event.key == pygame.K_ESCAPE:
            self._cancel_current()
            self.selected_ids.clear()

        elif event.key == pygame.K_SPACE:
            self.space_held = True

        elif event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
            # Save - will be handled in main loop via callback
            pass
        elif event.key == pygame.K_o and (event.mod & pygame.KMOD_CTRL):
            # Load - will be handled in main loop via callback
            pass

    def _handle_keyup(self, event):
        if event.key == pygame.K_SPACE:
            self.space_held = False
            if self.mode == self.MODE_PANNING:
                self.mode = self.MODE_IDLE

    def _handle_mousemotion(self, event):
        mx, my = event.pos
        wx, wy = self.canvas.screen_to_world(mx, my)

        if self.mode == self.MODE_PANNING:
            if self.pan_start_screen:
                dx = mx - self.pan_start_screen[0]
                dy = my - self.pan_start_screen[1]
                self.canvas.offset_x = self.pan_start_offset[0] + dx
                self.canvas.offset_y = self.pan_start_offset[1] + dy

        elif self.mode == self.MODE_DRAGGING:
            if self.drag_start_world:
                dx = wx - self.drag_start_world[0]
                dy = wy - self.drag_start_world[1]
                for cid, (ox, oy) in self.drag_offsets.items():
                    for comp in self.circuit.components:
                        if comp.id == cid:
                            comp.x = ox + dx
                            comp.y = oy + dy
                            break
                # Update wire paths
                for w in self.circuit.wires:
                    w.compute_path(self.circuit.components)

        elif self.mode == self.MODE_RUBBER_BAND:
            self.rubber_end = (wx, wy)

        elif self.mode == self.MODE_WIRE_DRAWING:
            self.wire_mouse_world = (wx, wy)

    def _handle_mousedown(self, event):
        mx, my = event.pos
        wx, wy = self.canvas.screen_to_world(mx, my)

        # Check if on toolbar
        if mx < self.canvas.toolbar_width:
            if event.button == 1:
                result = self.toolbar.handle_event(event, self.canvas)
                if result:
                    self.mode = self.MODE_PLACING
                    self.selected_ids.clear()
                else:
                    self.mode = self.MODE_IDLE
            return

        # Check if on canvas
        if not self.canvas.is_on_canvas(mx, my):
            return

        # Middle mouse button for panning
        if event.button == 2:
            self.mode = self.MODE_PANNING
            self.pan_start_screen = (mx, my)
            self.pan_start_offset = (self.canvas.offset_x, self.canvas.offset_y)
            self.middle_dragging = True
            return

        # Left button
        if event.button == 1:
            # Space + left = pan
            if self.space_held:
                self.mode = self.MODE_PANNING
                self.pan_start_screen = (mx, my)
                self.pan_start_offset = (self.canvas.offset_x, self.canvas.offset_y)
                return

            if self.mode == self.MODE_PLACING:
                self._place_component(wx, wy)
                return

            if self.mode == self.MODE_WIRE_DRAWING:
                self._try_complete_wire(wx, wy)
                return

            # IDLE mode
            # Check for INPUT node toggle
            comp = self.circuit.find_component_at(wx, wy)
            if comp and isinstance(comp, InputNode):
                comp.toggle()
                return

            # Check for pin click (start wire)
            pin_comp, pin = self.circuit.find_pin_at(wx, wy)
            if pin and not pin.is_input:
                # Start wire from output pin
                self.mode = self.MODE_WIRE_DRAWING
                self.wire_source_comp = pin_comp
                self.wire_source_pin = pin
                self.wire_mouse_world = (wx, wy)
                return

            # Check for component click (selection)
            if comp:
                shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
                if shift_held:
                    if comp.id in self.selected_ids:
                        self.selected_ids.discard(comp.id)
                    else:
                        self.selected_ids.add(comp.id)
                else:
                    if comp.id not in self.selected_ids:
                        self.selected_ids = {comp.id}
                # Start dragging
                self.mode = self.MODE_DRAGGING
                self.drag_start_world = (wx, wy)
                self.drag_offsets = {}
                for cid in self.selected_ids:
                    for c in self.circuit.components:
                        if c.id == cid:
                            self.drag_offsets[cid] = (c.x, c.y)
                            break
                return

            # Click on empty space - start rubber band
            self.mode = self.MODE_RUBBER_BAND
            self.rubber_start = (wx, wy)
            self.rubber_end = (wx, wy)
            if not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                self.selected_ids.clear()

        # Right button
        if event.button == 3:
            if self.mode == self.MODE_WIRE_DRAWING:
                # Cancel wire drawing
                self.mode = self.MODE_IDLE
                self.wire_source_comp = None
                self.wire_source_pin = None
                return

            # Check for wire deletion
            wire = self.circuit.find_wire_at(wx, wy, max_dist=10 / self.canvas.zoom)
            if wire:
                self.circuit.remove_wire(wire)
                return

            # Check for component property panel
            comp = self.circuit.find_component_at(wx, wy)
            if comp:
                self.property_target = comp
                self.property_input = comp.label
                self.property_field = "label"
                return

    def _handle_mouseup(self, event):
        mx, my = event.pos
        wx, wy = self.canvas.screen_to_world(mx, my)

        if event.button == 2:
            if self.mode == self.MODE_PANNING:
                self.mode = self.MODE_IDLE
            self.middle_dragging = False

        if event.button == 1:
            if self.mode == self.MODE_DRAGGING:
                self.mode = self.MODE_IDLE
                self.drag_start_world = None
                self.drag_offsets.clear()

            elif self.mode == self.MODE_RUBBER_BAND:
                self.mode = self.MODE_IDLE
                # Select components in rubber band rect
                if self.rubber_start and self.rubber_end:
                    x1 = min(self.rubber_start[0], self.rubber_end[0])
                    y1 = min(self.rubber_start[1], self.rubber_end[1])
                    x2 = max(self.rubber_start[0], self.rubber_end[0])
                    y2 = max(self.rubber_start[1], self.rubber_end[1])

                    # If the rectangle is very small, treat as single click on empty
                    if abs(x2 - x1) < 5 and abs(y2 - y1) < 5:
                        self.selected_ids.clear()
                    else:
                        for comp in self.circuit.components:
                            if x1 <= comp.x <= x2 and y1 <= comp.y <= y2:
                                self.selected_ids.add(comp.id)
                self.rubber_start = None
                self.rubber_end = None

            elif self.mode == self.MODE_PANNING and not self.middle_dragging:
                self.mode = self.MODE_IDLE

    def _place_component(self, wx, wy):
        """Place a component at world position."""
        comp_type = self.toolbar.get_active_type()
        if comp_type:
            # Snap to grid
            gx = round(wx / 20) * 20
            gy = round(wy / 20) * 20
            self.circuit.add_component(comp_type, gx, gy)
            # Stay in placement mode (re-click toolbar to exit)
            # self.mode = self.MODE_IDLE  # Exit after placing one
            # Actually, let's stay in placement mode for multiple placements
            # but many UX conventions exit after one. Let's exit.
            self.mode = self.MODE_IDLE
            self.toolbar.set_active_type(None)

    def _try_complete_wire(self, wx, wy):
        """Try to complete wire at world position."""
        pin_comp, pin = self.circuit.find_pin_at(wx, wy)
        if pin and pin.is_input and pin_comp.id != self.wire_source_comp.id:
            wire = self.circuit.add_wire(
                self.wire_source_comp, self.wire_source_pin,
                pin_comp, pin
            )
        # Reset wire drawing state
        self.mode = self.MODE_IDLE
        self.wire_source_comp = None
        self.wire_source_pin = None

    def _cancel_current(self):
        """Cancel current mode."""
        self.mode = self.MODE_IDLE
        self.wire_source_comp = None
        self.wire_source_pin = None
        self.rubber_start = None
        self.rubber_end = None
        self.drag_start_world = None
        self.drag_offsets.clear()
        self.property_target = None
        self.toolbar.set_active_type(None)

    def _delete_selected(self):
        """Delete selected components."""
        for cid in list(self.selected_ids):
            for comp in list(self.circuit.components):
                if comp.id == cid:
                    self.circuit.remove_component(comp)
                    break
        self.selected_ids.clear()

    def _handle_dialog_event(self, event):
        """Handle events when a text dialog is open."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Confirm
                cb = self.dialog_callback
                text = self.dialog_text
                self.dialog_callback = None
                self.dialog_text = ""
                self.dialog_title = ""
                if cb:
                    cb(text)
            elif event.key == pygame.K_ESCAPE:
                self.dialog_callback = None
                self.dialog_text = ""
                self.dialog_title = ""
            elif event.key == pygame.K_BACKSPACE:
                self.dialog_text = self.dialog_text[:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    self.dialog_text += event.unicode

    def _handle_property_event(self, event):
        """Handle events when property panel is open. Returns True if handled."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Save property
                if self.property_target:
                    if self.property_field == "label":
                        self.property_target.label = self.property_input
                    elif self.property_field == "freq" and isinstance(self.property_target, Clock):
                        try:
                            freq = float(self.property_input)
                            self.property_target.config["frequency"] = max(0.1, min(1000, freq))
                        except ValueError:
                            pass
                self.property_target = None
                self.property_input = ""
                self.property_field = None
                return True
            elif event.key == pygame.K_ESCAPE:
                self.property_target = None
                self.property_input = ""
                self.property_field = None
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.property_input = self.property_input[:-1]
                return True
            elif event.key == pygame.K_TAB:
                # Switch field
                if isinstance(self.property_target, Clock):
                    if self.property_field == "label":
                        self.property_field = "freq"
                        self.property_input = str(self.property_target.config.get("frequency", 2.0))
                    else:
                        self.property_field = "label"
                        self.property_input = self.property_target.label
                return True
            else:
                if event.unicode and event.unicode.isprintable():
                    self.property_input += event.unicode
                    return True
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Click outside closes
            self.property_target = None
            self.property_input = ""
            self.property_field = None
            return True
        return False

    def show_dialog(self, title, callback, default_text=""):
        """Show a text input dialog."""
        self.dialog_title = title
        self.dialog_callback = callback
        self.dialog_text = default_text

    def is_dialog_open(self):
        return self.dialog_callback is not None

    def draw(self, screen, font):
        """Draw input-related overlays."""
        # Rubber band
        if self.mode == self.MODE_RUBBER_BAND and self.rubber_start and self.rubber_end:
            sx1, sy1 = self.canvas.world_to_screen(*self.rubber_start)
            sx2, sy2 = self.canvas.world_to_screen(*self.rubber_end)
            rect = pygame.Rect(
                min(sx1, sx2), min(sy1, sy2),
                abs(sx2 - sx1), abs(sy2 - sy1)
            )
            # Draw filled rect with alpha
            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill(COLOR_SELECTION_RECT)
            screen.blit(s, (rect.x, rect.y))
            pygame.draw.rect(screen, (100, 160, 255), rect, 1)

        # Wire preview
        if self.mode == self.MODE_WIRE_DRAWING and self.wire_source_comp and self.wire_source_pin:
            src = self.wire_source_comp.get_pin_world_pos(self.wire_source_pin.name)
            dst = self.wire_mouse_world
            if src:
                sx1, sy1 = self.canvas.world_to_screen(*src)
                sx2, sy2 = self.canvas.world_to_screen(*dst)
                pygame.draw.line(screen, COLOR_WIRE_PREVIEW, (sx1, sy1), (sx2, sy2), 2)

        # Dialog
        if self.dialog_callback is not None:
            self._draw_dialog(screen, font)

        # Property panel
        if self.property_target is not None:
            self._draw_property_panel(screen, font)

    def _draw_dialog(self, screen, font):
        """Draw the save/load text dialog."""
        w, h = 400, 120
        sx = (screen.get_width() - w) // 2
        sy = (screen.get_height() - h) // 2
        rect = pygame.Rect(sx, sy, w, h)
        pygame.draw.rect(screen, (50, 50, 60), rect)
        pygame.draw.rect(screen, (150, 150, 170), rect, 2)

        title_surf = font.render(self.dialog_title, True, (220, 220, 230))
        screen.blit(title_surf, (sx + 10, sy + 10))

        # Input field
        input_rect = pygame.Rect(sx + 10, sy + 40, w - 20, 30)
        pygame.draw.rect(screen, (30, 30, 40), input_rect)
        pygame.draw.rect(screen, (120, 120, 140), input_rect, 1)

        text_surf = font.render(self.dialog_text + "_", True, (220, 220, 230))
        screen.blit(text_surf, (sx + 15, sy + 45))

        hint = font.render("Enter to confirm, Esc to cancel", True, (160, 160, 170))
        screen.blit(hint, (sx + 10, sy + 80))

    def _draw_property_panel(self, screen, font):
        """Draw the property editing panel."""
        comp = self.property_target
        if not comp:
            return

        # Position near mouse but clamped to screen
        mx, my = pygame.mouse.get_pos()
        pw, ph = 220, 120
        px = min(mx + 10, screen.get_width() - pw - 10)
        py = min(my + 10, screen.get_height() - ph - 10)

        rect = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(screen, (50, 50, 65), rect)
        pygame.draw.rect(screen, (150, 150, 170), rect, 2)

        y_off = py + 10
        # Component type
        type_surf = font.render(f"Type: {comp.type}", True, (200, 200, 210))
        screen.blit(type_surf, (px + 10, y_off))
        y_off += 22

        # Label field
        label_text = "Name: "
        if self.property_field == "label":
            label_text += self.property_input + "_"
        else:
            label_text += self.property_input
        lbl_surf = font.render(label_text, True, (220, 220, 100) if self.property_field == "label" else (200, 200, 210))
        screen.blit(lbl_surf, (px + 10, y_off))
        y_off += 22

        # Frequency field (for clock)
        if isinstance(comp, Clock):
            freq_text = "Freq (Hz): "
            if self.property_field == "freq":
                freq_text += self.property_input + "_"
            else:
                freq_text += str(comp.config.get("frequency", 2.0))
            freq_surf = font.render(freq_text, True, (220, 220, 100) if self.property_field == "freq" else (200, 200, 210))
            screen.blit(freq_surf, (px + 10, y_off))
            y_off += 22

        # Help
        help_surf = font.render("Tab: switch field  Enter: save", True, (150, 150, 160))
        screen.blit(help_surf, (px + 10, y_off + 5))
