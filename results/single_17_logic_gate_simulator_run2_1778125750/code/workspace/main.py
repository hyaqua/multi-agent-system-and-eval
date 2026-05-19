"""Main application: Logic Gate Simulator."""
import sys
import math
import pygame
from pygame.locals import *

from constants import *
from models import Component, Wire
from simulation import SimulationEngine
from file_io import save_circuit, load_circuit


# ============================================================
#  Canvas Transform
# ============================================================
class CanvasTransform:
    """Manages pan/zoom for the infinite canvas."""

    def __init__(self, screen_w, screen_h):
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.screen_w = screen_w
        self.screen_h = screen_h

    def world_to_screen(self, wx, wy):
        sx = (wx - self.camera_x) * self.zoom + self.screen_w / 2
        sy = (wy - self.camera_y) * self.zoom + self.screen_h / 2
        return (sx, sy)

    def screen_to_world(self, sx, sy):
        wx = (sx - self.screen_w / 2) / self.zoom + self.camera_x
        wy = (sy - self.screen_h / 2) / self.zoom + self.camera_y
        return (wx, wy)

    def zoom_at(self, screen_x, screen_y, factor):
        """Zoom centered on screen position."""
        wx, wy = self.screen_to_world(screen_x, screen_y)
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        # Adjust camera so world point stays under cursor
        self.camera_x = wx - (screen_x - self.screen_w / 2) / self.zoom
        self.camera_y = wy - (screen_y - self.screen_h / 2) / self.zoom

    def pan(self, dx, dy):
        self.camera_x -= dx / self.zoom
        self.camera_y -= dy / self.zoom

    def resize(self, sw, sh):
        self.screen_w = sw
        self.screen_h = sh


# ============================================================
#  Main Application
# ============================================================
class LogicSimulator:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 800), RESIZABLE)
        pygame.display.set_caption("Logic Gate Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', FONT_SIZE)
        self.small_font = pygame.font.SysFont('Arial', SMALL_FONT_SIZE)
        self.big_font = pygame.font.SysFont('Arial', 18)

        self.canvas = CanvasTransform(1280 - TOOLBAR_WIDTH, 800)
        self.sim = SimulationEngine()

        # UI state
        self.toolbar_rect = pygame.Rect(0, 0, TOOLBAR_WIDTH, 800)
        self.placement_mode = None  # component type to place, or None
        self.selected_comps = set()  # set of component ids
        self.dragging = False
        self.drag_start_world = (0, 0)
        self.drag_comp_offsets = {}  # comp_id -> (ox, oy)
        self.panning = False
        self.pan_start = (0, 0)
        self.rubber_band = None  # (wx1, wy1, wx2, wy2) or None
        self.rubber_start = (0, 0)

        # Wire drawing
        self.wire_start = None  # (comp_id, pin_name) output pin
        self.wire_cursor = None  # (wx, wy) current cursor

        # Properties panel
        self.properties_target = None  # component id
        self.properties_input = ''  # text being edited
        self.properties_field = 'label'  # 'label' or 'frequency'

        # Text input dialog (for save/load)
        self.text_input_active = False
        self.text_input_value = ''
        self.text_input_action = None  # 'save' or 'load'

        # Warning message
        self.warning_message = ''
        self.warning_timer = 0.0

        # Clock for placement blink
        self.placement_blink = 0.0

        # Hovered toolbar button
        self.hovered_button = None

        # For panning with space+left drag
        self.space_held = False

    # ============================================================
    #  Main loop
    # ============================================================
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0  # dt in seconds
            # Cap dt to avoid large jumps
            dt = min(dt, 0.1)

            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False

            self.update(dt)
            self.draw()
            pygame.display.flip()

        pygame.quit()

    # ============================================================
    #  Event handling
    # ============================================================
    def handle_event(self, event):
        if event.type == QUIT:
            return False

        mx, my = pygame.mouse.get_pos()

        # Text input handling
        if self.text_input_active:
            return self.handle_text_input(event)

        # Properties panel
        if self.properties_target is not None:
            return self.handle_properties_event(event)

        # Keyboard events
        if event.type == KEYDOWN:
            return self.handle_keydown(event)
        if event.type == KEYUP:
            if event.key == K_SPACE:
                self.space_held = False
            return True

        # Mouse events
        if event.type == MOUSEBUTTONDOWN:
            return self.handle_mouse_down(event, mx, my)
        if event.type == MOUSEBUTTONUP:
            return self.handle_mouse_up(event, mx, my)
        if event.type == MOUSEMOTION:
            return self.handle_mouse_motion(event, mx, my)
        if event.type == VIDEORESIZE:
            self.screen = pygame.display.set_mode((event.w, event.h), RESIZABLE)
            self.canvas.resize(event.w - TOOLBAR_WIDTH, event.h)
            self.toolbar_rect.height = event.h
            return True

        return True

    def handle_keydown(self, event):
        """Handle key presses."""
        if event.key == K_DELETE or event.key == K_BACKSPACE:
            # Delete selected components
            for comp_id in list(self.selected_comps):
                self.sim.remove_component(comp_id)
                if comp_id in self.selected_comps:
                    self.selected_comps.discard(comp_id)
            return True

        if event.key == K_ESCAPE:
            self.placement_mode = None
            self.wire_start = None
            self.selected_comps.clear()
            self.properties_target = None
            self.text_input_active = False
            return True

        if event.key == K_SPACE:
            self.space_held = True
            return True

        # Ctrl+S save
        if event.key == K_s and (pygame.key.get_mods() & KMOD_CTRL):
            self.text_input_active = True
            self.text_input_value = 'circuit.json'
            self.text_input_action = 'save'
            return True

        # Ctrl+O load
        if event.key == K_o and (pygame.key.get_mods() & KMOD_CTRL):
            self.text_input_active = True
            self.text_input_value = 'circuit.json'
            self.text_input_action = 'load'
            return True

        return True

    def handle_mouse_down(self, event, mx, my):
        if event.button == 4:  # Scroll up
            if mx > TOOLBAR_WIDTH:
                self.canvas.zoom_at(mx - TOOLBAR_WIDTH, my, 1.0 + ZOOM_STEP)
            return True
        if event.button == 5:  # Scroll down
            if mx > TOOLBAR_WIDTH:
                self.canvas.zoom_at(mx - TOOLBAR_WIDTH, my, 1.0 - ZOOM_STEP)
            return True

        # Toolbar clicks
        if mx < TOOLBAR_WIDTH:
            return self.handle_toolbar_click(event, mx, my)

        # Canvas area
        canvas_mx = mx - TOOLBAR_WIDTH
        wx, wy = self.canvas.screen_to_world(canvas_mx, my)

        if event.button == 1:  # Left click
            return self.handle_canvas_left_down(wx, wy, mx, my)
        elif event.button == 2:  # Middle click
            self.panning = True
            self.pan_start = (mx, my)
            return True
        elif event.button == 3:  # Right click
            return self.handle_canvas_right_down(wx, wy)

        return True

    def handle_mouse_up(self, event, mx, my):
        canvas_mx = mx - TOOLBAR_WIDTH
        wx, wy = self.canvas.screen_to_world(canvas_mx, my)

        if event.button == 1:
            return self.handle_canvas_left_up(wx, wy)
        elif event.button == 2:
            self.panning = False
            return True
        return True

    def handle_mouse_motion(self, event, mx, my):
        if self.text_input_active:
            return True

        canvas_mx = mx - TOOLBAR_WIDTH
        wx, wy = self.canvas.screen_to_world(canvas_mx, my)

        # Update hovered toolbar button
        if mx < TOOLBAR_WIDTH:
            self.hovered_button = self.get_toolbar_button_at(mx, my)
        else:
            self.hovered_button = None

        # Wire cursor
        if self.wire_start is not None:
            self.wire_cursor = (wx, wy)
            return True

        # Panning
        if self.panning:
            dx = mx - self.pan_start[0]
            dy = my - self.pan_start[1]
            self.canvas.pan(dx, dy)
            self.pan_start = (mx, my)
            return True

        # Space + left drag for panning
        if self.space_held and pygame.mouse.get_pressed()[0]:
            if hasattr(self, '_space_pan_prev'):
                px, py = self._space_pan_prev
                self.canvas.pan(mx - px, my - py)
            self._space_pan_prev = (mx, my)
            return True
        else:
            if hasattr(self, '_space_pan_prev'):
                del self._space_pan_prev

        # Dragging components
        if self.dragging and self.selected_comps:
            dwx = wx - self.drag_start_world[0]
            dwy = wy - self.drag_start_world[1]
            for comp_id, (ox, oy) in self.drag_comp_offsets.items():
                comp = self.sim.components.get(comp_id)
                if comp:
                    comp.x = wx + ox
                    comp.y = wy + oy
            return True

        # Rubber band
        if self.rubber_band is not None:
            self.rubber_band = (self.rubber_start[0], self.rubber_start[1], wx, wy)
            return True

        return True

    def handle_canvas_left_down(self, wx, wy, mx, my):
        """Handle left click on canvas."""
        # Check if clicking a pin
        if self.wire_start is not None:
            # Trying to complete a wire by clicking an input pin
            for comp in self.sim.components.values():
                pin_hit = comp.find_pin_at(wx, wy)
                if pin_hit and pin_hit[1]:  # is_input
                    wire = Wire(self.wire_start[0], self.wire_start[1],
                                comp.id, pin_hit[0])
                    self._compute_wire_path(wire)
                    self.sim.add_wire(wire)
                    self.wire_start = None
                    self.wire_cursor = None
                    return True
            # Clicked empty space, cancel wire
            self.wire_start = None
            self.wire_cursor = None
            return True

        # Check if clicking an output pin to start a wire
        for comp in self.sim.components.values():
            pin_hit = comp.find_pin_at(wx, wy)
            if pin_hit and not pin_hit[1]:  # is_output
                self.wire_start = (comp.id, pin_hit[0])
                self.wire_cursor = (wx, wy)
                return True

        # Placement mode: place component on empty canvas
        if self.placement_mode is not None:
            # Check we're not clicking on an existing component
            on_comp = False
            for comp in self.sim.components.values():
                if comp.contains_point(wx, wy):
                    on_comp = True
                    break
            if not on_comp:
                self.place_component(wx, wy)
                return True
            return True

        # Check if clicking a component
        clicked_comp = None
        for comp in self.sim.components.values():
            if comp.contains_point(wx, wy):
                clicked_comp = comp
                break

        if clicked_comp:
            if clicked_comp.comp_type == 'INPUT':
                # Toggle input value
                clicked_comp.output_values['out'] = 1 - clicked_comp.output_values.get('out', 0)
                # Don't return yet - allow selection too

            shift_held = pygame.key.get_mods() & KMOD_SHIFT
            if shift_held:
                # Toggle selection
                if clicked_comp.id in self.selected_comps:
                    self.selected_comps.discard(clicked_comp.id)
                else:
                    self.selected_comps.add(clicked_comp.id)
            else:
                if clicked_comp.id not in self.selected_comps:
                    self.selected_comps = {clicked_comp.id}
                # Start dragging
                self.dragging = True
                self.drag_start_world = (wx, wy)
                self.drag_comp_offsets = {}
                for cid in self.selected_comps:
                    c = self.sim.components.get(cid)
                    if c:
                        self.drag_comp_offsets[cid] = (c.x - wx, c.y - wy)
            return True

        # Clicked empty space: start rubber band or clear selection
        self.selected_comps.clear()
        self.rubber_band = (wx, wy, wx, wy)
        self.rubber_start = (wx, wy)
        return True

    def handle_canvas_left_up(self, wx, wy):
        """Handle left mouse up on canvas."""
        if self.dragging:
            self.dragging = False
            self.drag_comp_offsets = {}
            # Recompute wire paths after drag
            self._recompute_all_wire_paths()
            return True

        if self.rubber_band is not None:
            # Finalize rubber band selection
            x1, y1, x2, y2 = self.rubber_band
            rx = min(x1, x2)
            ry = min(y1, y2)
            rw = abs(x2 - x1)
            rh = abs(y2 - y1)
            self.selected_comps.clear()
            for comp in self.sim.components.values():
                if (comp.x < rx + rw and comp.x + comp.width > rx and
                    comp.y < ry + rh and comp.y + comp.height > ry):
                    self.selected_comps.add(comp.id)
            self.rubber_band = None
            return True

        return True

    def handle_canvas_right_down(self, wx, wy):
        """Handle right click on canvas."""
        # Check wires first
        wire = self.sim.find_wire_at(wx, wy)
        if wire:
            self.sim.remove_wire(wire.id)
            return True

        # Check components
        for comp in self.sim.components.values():
            if comp.contains_point(wx, wy):
                self.properties_target = comp.id
                self.properties_field = 'label'
                self.properties_input = comp.label
                return True

        return True

    def handle_toolbar_click(self, event, mx, my):
        """Handle toolbar button click."""
        button = self.get_toolbar_button_at(mx, my)
        if button:
            self.placement_mode = button
            self.wire_start = None
            self.selected_comps.clear()
        return True

    def handle_text_input(self, event):
        """Handle text input for save/load dialogs."""
        if event.type == KEYDOWN:
            if event.key == K_RETURN:
                self._execute_text_action()
                self.text_input_active = False
                return True
            if event.key == K_ESCAPE:
                self.text_input_active = False
                return True
            if event.key == K_BACKSPACE:
                self.text_input_value = self.text_input_value[:-1]
                return True
            # Ignore control keys
            if event.key in (K_LCTRL, K_RCTRL, K_LSHIFT, K_RSHIFT, K_LALT, K_RALT):
                return True
        if event.type == TEXTINPUT:
            self.text_input_value += event.text
            return True
        return True

    def handle_properties_event(self, event):
        """Handle events when properties panel is open."""
        if event.type == KEYDOWN:
            if event.key == K_RETURN:
                self._apply_properties()
                self.properties_target = None
                return True
            if event.key == K_ESCAPE:
                self.properties_target = None
                return True
            if event.key == K_BACKSPACE:
                self.properties_input = self.properties_input[:-1]
                return True
            if event.key == K_TAB:
                comp = self.sim.components.get(self.properties_target)
                if comp and comp.comp_type == 'CLOCK':
                    if self.properties_field == 'label':
                        self.properties_field = 'frequency'
                        self.properties_input = str(comp.properties.get('frequency', 1.0))
                    else:
                        self.properties_field = 'label'
                        self.properties_input = comp.label
                return True
        if event.type == TEXTINPUT:
            self.properties_input += event.text
            return True
        if event.type == MOUSEBUTTONDOWN:
            # Close if clicking outside properties area
            mx, my = pygame.mouse.get_pos()
            if not self._is_in_properties_area(mx, my):
                self._apply_properties()
                self.properties_target = None
            return True
        return True

    def _is_in_properties_area(self, mx, my):
        """Check if screen position is in the properties panel area."""
        comp = self.sim.components.get(self.properties_target)
        if not comp:
            return False
        sx, sy = self.canvas.world_to_screen(comp.x + comp.width / 2, comp.y)
        sx += TOOLBAR_WIDTH
        # Panel is drawn above the component
        panel_rect = pygame.Rect(sx - 80, sy - 90, 160, 80)
        return panel_rect.collidepoint(mx, my)

    def _apply_properties(self):
        """Apply properties changes."""
        comp = self.sim.components.get(self.properties_target)
        if not comp:
            return
        if self.properties_field == 'label':
            comp.label = self.properties_input.strip() or comp.comp_type
        elif self.properties_field == 'frequency':
            try:
                freq = float(self.properties_input)
                freq = max(0.1, min(1000, freq))
                comp.properties['frequency'] = freq
            except ValueError:
                pass

    def _execute_text_action(self):
        """Execute save or load action."""
        filename = self.text_input_value.strip()
        if not filename:
            self.warning_message = "Please enter a filename."
            self.warning_timer = 3.0
            return
        if self.text_input_action == 'save':
            try:
                save_circuit(self.sim.components, self.sim.wires, filename)
                self.warning_message = f"Saved to {filename}"
                self.warning_timer = 2.0
            except Exception as e:
                self.warning_message = f"Save failed: {e}"
                self.warning_timer = 3.0
        elif self.text_input_action == 'load':
            try:
                comps, wires = load_circuit(filename)
                self.sim.components = comps
                self.sim.wires = wires
                self._recompute_all_wire_paths()
                self.selected_comps.clear()
                self.placement_mode = None
                self.wire_start = None
                self.warning_message = f"Loaded {filename}"
                self.warning_timer = 2.0
            except Exception as e:
                self.warning_message = f"Load failed: {e}"
                self.warning_timer = 3.0

    # ============================================================
    #  Toolbar
    # ============================================================
    def get_toolbar_button_at(self, mx, my):
        """Get the component type at toolbar position, or None."""
        y = 10
        button_h = 36
        gap = 4
        for ctype in ALL_TYPES:
            rect = pygame.Rect(5, y, TOOLBAR_WIDTH - 10, button_h)
            if rect.collidepoint(mx, my):
                return ctype
            y += button_h + gap
        return None

    def get_toolbar_button_rects(self):
        """Get list of (type, rect) for all toolbar buttons."""
        result = []
        y = 10
        button_h = 36
        gap = 4
        for ctype in ALL_TYPES:
            rect = pygame.Rect(5, y, TOOLBAR_WIDTH - 10, button_h)
            result.append((ctype, rect))
            y += button_h + gap
        return result

    # ============================================================
    #  Update
    # ============================================================
    def update(self, dt):
        self.sim.step(dt)

        if self.warning_timer > 0:
            self.warning_timer -= dt
            if self.warning_timer <= 0:
                self.warning_message = ''

        self.placement_blink += dt

        # Handle placement mode: place on click
        if self.placement_mode is not None:
            mx, my = pygame.mouse.get_pos()
            if mx > TOOLBAR_WIDTH and pygame.mouse.get_pressed()[0]:
                # Check if we just clicked (handled in mouse down, so skip here to avoid double-place)
                pass

    # ============================================================
    #  Drawing
    # ============================================================
    def draw(self):
        self.screen.fill(BACKGROUND)

        # Draw toolbar
        self.draw_toolbar()

        # Draw canvas
        self.draw_canvas()

        # Draw overlay
        self.draw_overlay()

        # Draw text input dialog
        if self.text_input_active:
            self.draw_text_input_dialog()

    def draw_toolbar(self):
        """Draw the toolbar on the left."""
        pygame.draw.rect(self.screen, TOOLBAR_BG, self.toolbar_rect)

        # Title
        title = self.small_font.render("Components", True, (200, 200, 200))
        self.screen.blit(title, (8, 4))

        y = 10
        button_h = 36
        gap = 4
        for ctype in ALL_TYPES:
            rect = pygame.Rect(5, y, TOOLBAR_WIDTH - 10, button_h)
            color = TOOLBAR_BUTTON
            if ctype == self.placement_mode:
                color = TOOLBAR_BUTTON_ACTIVE
            elif ctype == self.hovered_button:
                color = TOOLBAR_BUTTON_HOVER
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, (100, 100, 120), rect, 1, border_radius=4)

            label = self.small_font.render(ctype, True, (220, 220, 220))
            self.screen.blit(label, (rect.x + 8, rect.y + rect.h // 2 - label.get_height() // 2))
            y += button_h + gap

    def draw_canvas(self):
        """Draw the infinite canvas area."""
        canvas_rect = pygame.Rect(TOOLBAR_WIDTH, 0,
                                  self.screen.get_width() - TOOLBAR_WIDTH,
                                  self.screen.get_height())
        pygame.draw.rect(self.screen, BACKGROUND, canvas_rect)

        # Clip to canvas area
        self.screen.set_clip(canvas_rect)

        # Draw grid
        self.draw_grid(canvas_rect)

        # Draw wires
        self.draw_wires()

        # Draw wire being created
        if self.wire_start is not None and self.wire_cursor is not None:
            self.draw_pending_wire()

        # Draw components
        for comp in self.sim.components.values():
            self.draw_component(comp)

        # Draw rubber band selection
        if self.rubber_band is not None:
            self.draw_rubber_band()

        # Draw selection highlights
        for cid in self.selected_comps:
            comp = self.sim.components.get(cid)
            if comp:
                self.draw_selection_box(comp)

        self.screen.set_clip(None)

    def draw_grid(self, canvas_rect):
        """Draw the dot grid background."""
        # Determine visible world area
        wx1, wy1 = self.canvas.screen_to_world(0, 0)
        wx2, wy2 = self.canvas.screen_to_world(canvas_rect.width, canvas_rect.height)

        # Align to grid
        gs = GRID_SIZE
        start_x = int(wx1 // gs) * gs
        start_y = int(wy1 // gs) * gs

        step = max(1, int(gs))  # At very zoomed out, step might be less than 1 pixel
        x = start_x
        while x <= wx2:
            y = start_y
            while y <= wy2:
                sx, sy = self.canvas.world_to_screen(x, y)
                sx += TOOLBAR_WIDTH
                # Only draw if on screen
                if 0 <= sx <= self.screen.get_width() and 0 <= sy <= self.screen.get_height():
                    # Size based on zoom
                    dot_size = max(1, int(self.canvas.zoom * 1.5))
                    pygame.draw.circle(self.screen, GRID_DOT, (int(sx), int(sy)), dot_size)
                y += gs
            x += gs

    def draw_component(self, comp):
        """Draw a single component."""
        sx, sy = self.canvas.world_to_screen(comp.x, comp.y)
        sx += TOOLBAR_WIDTH
        sw = comp.width * self.canvas.zoom
        sh = comp.height * self.canvas.zoom

        rect = pygame.Rect(sx, sy, sw, sh)

        # Component body
        body_color = COMPONENT_BODY
        if comp.id in self.sim.cycle_components:
            body_color = (180, 40, 40)

        pygame.draw.rect(self.screen, body_color, rect, border_radius=4)
        pygame.draw.rect(self.screen, COMPONENT_BORDER, rect, 2, border_radius=4)

        # For OUTPUT component, color based on value
        if comp.comp_type == 'OUTPUT':
            val = comp.input_values.get('in0', 0) if comp.input_pins else 0
            if val == 1:
                pygame.draw.rect(self.screen, PIN_HIGH, rect, border_radius=4)
                pygame.draw.rect(self.screen, COMPONENT_BORDER, rect, 2, border_radius=4)

        # Label
        label_text = self.small_font.render(comp.label, True, OUTPUT_TEXT)
        lx = sx + sw / 2 - label_text.get_width() / 2
        ly = sy + sh / 2 - label_text.get_height() / 2
        self.screen.blit(label_text, (lx, ly))

        # Draw pins
        for pin_name, rx, ry in comp.input_pins:
            px = comp.x + rx * comp.width
            py = comp.y + ry * comp.height
            psx, psy = self.canvas.world_to_screen(px, py)
            psx += TOOLBAR_WIDTH
            self._draw_pin(psx, psy, comp, pin_name, True)

        for pin_name, rx, ry in comp.output_pins:
            px = comp.x + rx * comp.width
            py = comp.y + ry * comp.height
            psx, psy = self.canvas.world_to_screen(px, py)
            psx += TOOLBAR_WIDTH
            self._draw_pin(psx, psy, comp, pin_name, False)

        # Draw seven segment display
        if comp.comp_type == 'SEVEN_SEGMENT':
            self._draw_seven_segment(comp, sx, sy, sw, sh)

    def _draw_pin(self, sx, sy, comp, pin_name, is_input):
        """Draw a pin circle."""
        r = max(2, int(PIN_RADIUS * self.canvas.zoom))

        # Determine pin state color
        val = 0
        if is_input:
            val = comp.input_values.get(pin_name, 0)
        else:
            val = comp.output_values.get(pin_name, 0)

        pin_color = PIN_HIGH if val == 1 else PIN_LOW

        if comp.id in self.sim.cycle_components:
            pin_color = CYCLE_HIGHLIGHT

        pygame.draw.circle(self.screen, PIN_HOLE, (int(sx), int(sy)), r + 1)
        pygame.draw.circle(self.screen, pin_color, (int(sx), int(sy)), r)
        pygame.draw.circle(self.screen, PIN_BORDER, (int(sx), int(sy)), r, 1)

    def _draw_seven_segment(self, comp, sx, sy, sw, sh):
        """Draw the seven segment pattern on the component."""
        # Get input values
        segs = {}
        for pin_name, _, _ in comp.input_pins:
            segs[pin_name] = comp.input_values.get(pin_name, 0)

        # Segment geometry relative to component
        # Scale based on component size
        margin = 8 * self.canvas.zoom
        seg_w = sw * 0.22
        seg_h = sh * 0.05
        gap = 3 * self.canvas.zoom

        hw = sw / 2
        hh = sh / 2
        top = sy + margin
        bot = sy + sh - margin - seg_h
        mid = sy + hh - seg_h / 2
        left = sx + margin
        right = sx + sw - margin - seg_w

        segments = {
            'a': (sx + hw - seg_w / 2, top, seg_w, seg_h),  # top horizontal
            'b': (right, top + gap, seg_h, seg_w),  # top-right vertical
            'c': (right, mid + gap, seg_h, seg_w),  # bottom-right vertical
            'd': (sx + hw - seg_w / 2, bot, seg_w, seg_h),  # bottom horizontal
            'e': (left, mid + gap, seg_h, seg_w),  # bottom-left vertical
            'f': (left, top + gap, seg_h, seg_w),  # top-left vertical
            'g': (sx + hw - seg_w / 2, mid, seg_w, seg_h),  # middle horizontal
        }

        for seg_name, (seg_x, seg_y, seg_wid, seg_hei) in segments.items():
            val = segs.get(seg_name, 0)
            color = PIN_HIGH if val == 1 else (40, 40, 40)
            seg_rect = pygame.Rect(seg_x, seg_y, seg_wid, seg_hei)
            pygame.draw.rect(self.screen, color, seg_rect, border_radius=2)

    def draw_wires(self):
        """Draw all wires."""
        for wire in self.sim.wires:
            is_cycle = wire.id in self.sim.cycle_wires
            is_high = wire.id in self.sim.high_wires

            if is_cycle:
                color = WIRE_CYCLE
                width = 3
            elif is_high:
                color = WIRE_HIGH
                width = 2
            else:
                color = WIRE_LOW
                width = 2

            points = []
            for wx, wy in wire.path:
                sx, sy = self.canvas.world_to_screen(wx, wy)
                sx += TOOLBAR_WIDTH
                points.append((sx, sy))

            if len(points) >= 2:
                pygame.draw.lines(self.screen, color, False, points,
                                  max(1, int(width * self.canvas.zoom)))

    def draw_pending_wire(self):
        """Draw the wire being created."""
        src_comp = self.sim.components.get(self.wire_start[0])
        if not src_comp:
            return
        src_pin = self.wire_start[1]
        sx, sy = src_comp.get_pin_world_pos(src_pin, False)
        ssx, ssy = self.canvas.world_to_screen(sx, sy)
        ssx += TOOLBAR_WIDTH

        ex, ey = self.wire_cursor
        esx, esy = self.canvas.world_to_screen(ex, ey)
        esx += TOOLBAR_WIDTH

        # Draw dashed line
        self._draw_dashed_line(ssx, ssy, esx, esy, WIRE_COLOR)

    def _draw_dashed_line(self, x1, y1, x2, y2, color, dash_len=8):
        """Draw a dashed line."""
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        dx /= dist
        dy /= dist
        drawn = 0
        while drawn < dist:
            seg = min(dash_len, dist - drawn)
            sx = x1 + dx * drawn
            sy = y1 + dy * drawn
            ex_ = x1 + dx * (drawn + seg)
            ey_ = y1 + dy * (drawn + seg)
            pygame.draw.line(self.screen, color, (int(sx), int(sy)), (int(ex_), int(ey_)), 1)
            drawn += dash_len * 2

    def draw_rubber_band(self):
        """Draw rubber band selection rectangle."""
        x1, y1, x2, y2 = self.rubber_band
        sx1, sy1 = self.canvas.world_to_screen(x1, y1)
        sx2, sy2 = self.canvas.world_to_screen(x2, y2)
        sx1 += TOOLBAR_WIDTH
        sy1 = sy1
        sx2 += TOOLBAR_WIDTH

        rx = min(sx1, sx2)
        ry = min(sy1, sy2)
        rw = abs(sx2 - sx1)
        rh = abs(sy1 - sy2)

        # Fill
        s = pygame.Surface((rw, rh), SRCALPHA)
        s.fill(RUBBER_BAND_FILL)
        self.screen.blit(s, (rx, ry))
        # Border
        pygame.draw.rect(self.screen, SELECTION_BOX, (rx, ry, rw, rh), 1)

    def draw_selection_box(self, comp):
        """Draw selection highlight around component."""
        sx, sy = self.canvas.world_to_screen(comp.x, comp.y)
        sx += TOOLBAR_WIDTH
        sw = comp.width * self.canvas.zoom
        sh = comp.height * self.canvas.zoom
        pygame.draw.rect(self.screen, COMPONENT_SELECTED,
                         (sx - 3, sy - 3, sw + 6, sh + 6), 2)

    def draw_overlay(self):
        """Draw overlay information."""
        # Coordinate display
        mx, my = pygame.mouse.get_pos()
        if mx > TOOLBAR_WIDTH:
            canvas_mx = mx - TOOLBAR_WIDTH
            wx, wy = self.canvas.screen_to_world(canvas_mx, my)
            coord_text = f"World: ({wx:.0f}, {wy:.0f})  Zoom: {self.canvas.zoom:.0%}"
        else:
            coord_text = f"Zoom: {self.canvas.zoom:.0%}"

        text_surf = self.small_font.render(coord_text, True, OVERLAY_TEXT)
        self.screen.blit(text_surf, (self.screen.get_width() - text_surf.get_width() - 10,
                                     self.screen.get_height() - text_surf.get_height() - 10))

        # Cycle warning
        if self.sim.cycle_components:
            warning = f"⚠ COMBINATIONAL CYCLE DETECTED ({len(self.sim.cycle_components)} components)"
            warn_surf = self.big_font.render(warning, True, WARNING_COLOR)
            wx_pos = self.screen.get_width() // 2 - warn_surf.get_width() // 2
            pygame.draw.rect(self.screen, (0, 0, 0, 180),
                             (wx_pos - 10, 5, warn_surf.get_width() + 20, warn_surf.get_height() + 10))
            self.screen.blit(warn_surf, (wx_pos, 10))

        # Warning message
        if self.warning_timer > 0 and self.warning_message:
            msg_surf = self.big_font.render(self.warning_message, True, (255, 255, 100))
            mx_pos = self.screen.get_width() // 2 - msg_surf.get_width() // 2
            pygame.draw.rect(self.screen, (0, 0, 0, 200),
                             (mx_pos - 10, 40, msg_surf.get_width() + 20, msg_surf.get_height() + 10))
            self.screen.blit(msg_surf, (mx_pos, 45))

        # Placement mode indicator
        if self.placement_mode is not None:
            hint = f"Placing: {self.placement_mode}  (Click canvas to place, Esc to cancel)"
            hint_surf = self.small_font.render(hint, True, (180, 220, 255))
            self.screen.blit(hint_surf, (TOOLBAR_WIDTH + 10, 10))

        # Properties panel
        if self.properties_target is not None:
            self.draw_properties_panel()

    def draw_properties_panel(self):
        """Draw the properties editing panel."""
        comp = self.sim.components.get(self.properties_target)
        if not comp:
            return
        sx, sy = self.canvas.world_to_screen(comp.x + comp.width / 2, comp.y)
        sx += TOOLBAR_WIDTH
        panel_w = 180
        panel_h = 90
        px = int(sx - panel_w / 2)
        py = int(sy - panel_h - 10)

        # Clamp to screen
        px = max(TOOLBAR_WIDTH + 5, min(px, self.screen.get_width() - panel_w - 5))
        py = max(5, min(py, self.screen.get_height() - panel_h - 5))

        panel_rect = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(self.screen, (40, 40, 55), panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, (120, 120, 140), panel_rect, 2, border_radius=6)

        # Title
        title = self.small_font.render(f"Properties: {comp.comp_type}", True, (200, 200, 200))
        self.screen.blit(title, (px + 8, py + 5))

        # Field name
        field_label = self.properties_field.capitalize() + ":"
        fl_surf = self.small_font.render(field_label, True, (180, 180, 180))
        self.screen.blit(fl_surf, (px + 8, py + 28))

        # Input box
        input_rect = pygame.Rect(px + 8, py + 48, panel_w - 16, 24)
        pygame.draw.rect(self.screen, (20, 20, 30), input_rect)
        pygame.draw.rect(self.screen, (150, 150, 170), input_rect, 1)
        input_text = self.small_font.render(self.properties_input + '|', True, (255, 255, 255))
        self.screen.blit(input_text, (px + 12, py + 50))

        # Hint
        hint = self.small_font.render("Enter: save  Esc: cancel", True, (140, 140, 140))
        self.screen.blit(hint, (px + 8, py + 74))

        # For CLOCK, show tab hint
        if comp.comp_type == 'CLOCK':
            tab_hint = self.small_font.render("Tab: switch field", True, (140, 140, 140))
            self.screen.blit(tab_hint, (px + 8, py + 62))

    def draw_text_input_dialog(self):
        """Draw save/load text input dialog."""
        dialog_w = 400
        dialog_h = 100
        dx = self.screen.get_width() // 2 - dialog_w // 2
        dy = self.screen.get_height() // 2 - dialog_h // 2

        dialog_rect = pygame.Rect(dx, dy, dialog_w, dialog_h)
        pygame.draw.rect(self.screen, (30, 30, 50), dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, (150, 150, 170), dialog_rect, 2, border_radius=8)

        action = "Save" if self.text_input_action == 'save' else "Load"
        title = self.big_font.render(f"{action} Circuit", True, (220, 220, 220))
        self.screen.blit(title, (dx + 10, dy + 8))

        prompt = self.small_font.render("Filename:", True, (180, 180, 180))
        self.screen.blit(prompt, (dx + 10, dy + 35))

        input_rect = pygame.Rect(dx + 80, dy + 32, dialog_w - 100, 26)
        pygame.draw.rect(self.screen, (20, 20, 30), input_rect)
        pygame.draw.rect(self.screen, (150, 150, 170), input_rect, 1)
        input_text = self.small_font.render(self.text_input_value + '|', True, (255, 255, 255))
        self.screen.blit(input_text, (dx + 84, dy + 35))

        hint = self.small_font.render("Enter: confirm  Esc: cancel", True, (140, 140, 140))
        self.screen.blit(hint, (dx + 10, dy + 70))

    # ============================================================
    #  Wire path computation
    # ============================================================
    def _compute_wire_path(self, wire):
        """Compute orthogonal path for a wire."""
        src_comp = self.sim.components.get(wire.from_comp)
        dst_comp = self.sim.components.get(wire.to_comp)
        if not src_comp or not dst_comp:
            return

        sx, sy = src_comp.get_pin_world_pos(wire.from_pin, False)
        ex, ey = dst_comp.get_pin_world_pos(wire.to_pin, True)

        # Snap to grid
        gs = GRID_SIZE
        sx = round(sx / gs) * gs
        sy = round(sy / gs) * gs
        ex = round(ex / gs) * gs
        ey = round(ey / gs) * gs

        # Orthogonal routing: go horizontal from source, then vertical, then horizontal to dest
        mid_x = (sx + ex) / 2
        mid_x = round(mid_x / gs) * gs

        path = [(sx, sy)]
        if abs(sx - ex) > gs and abs(sy - ey) > gs:
            path.append((mid_x, sy))
            path.append((mid_x, ey))
        path.append((ex, ey))
        wire.path = path

    def _recompute_all_wire_paths(self):
        """Recompute paths for all wires."""
        for wire in self.sim.wires:
            self._compute_wire_path(wire)

    # ============================================================
    #  Placement on canvas click (called when in placement mode)
    # ============================================================
    def place_component(self, wx, wy):
        """Place a component of the current placement type at world position."""
        if self.placement_mode is None:
            return
        # Snap to grid
        gs = GRID_SIZE
        wx = round(wx / gs) * gs
        wy = round(wy / gs) * gs

        comp = Component(self.placement_mode, wx, wy)
        self.sim.add_component(comp)


# ============================================================
#  Entry point
# ============================================================
def create_sample_half_adder(sim):
    """Create a half adder circuit directly."""
    # Clear
    sim.components.clear()
    sim.wires.clear()
    Component._next_id = 0
    Wire._next_id = 0

    # Input A
    a = Component('INPUT', 100, 100, 'A')
    a.output_values['out'] = 0
    sim.add_component(a)
    # Input B
    b = Component('INPUT', 100, 200, 'B')
    b.output_values['out'] = 0
    sim.add_component(b)
    # XOR for Sum
    xor_gate = Component('XOR', 300, 130, 'Sum')
    sim.add_component(xor_gate)
    # AND for Carry
    and_gate = Component('AND', 300, 230, 'Carry')
    sim.add_component(and_gate)
    # Output Sum
    sum_out = Component('OUTPUT', 500, 130, 'S')
    sim.add_component(sum_out)
    # Output Carry
    carry_out = Component('OUTPUT', 500, 230, 'C')
    sim.add_component(carry_out)

    # Wires: A -> XOR in0, B -> XOR in1
    sim.add_wire(Wire(a.id, 'out', xor_gate.id, 'in0'))
    sim.add_wire(Wire(b.id, 'out', xor_gate.id, 'in1'))
    # Wires: A -> AND in0, B -> AND in1
    sim.add_wire(Wire(a.id, 'out', and_gate.id, 'in0'))
    sim.add_wire(Wire(b.id, 'out', and_gate.id, 'in1'))
    # Wires: XOR -> Sum output, AND -> Carry output
    sim.add_wire(Wire(xor_gate.id, 'out', sum_out.id, 'in0'))
    sim.add_wire(Wire(and_gate.id, 'out', carry_out.id, 'in0'))


def create_sample_ripple_counter(sim):
    """Create a 4-bit ripple counter demonstration circuit."""
    sim.components.clear()
    sim.wires.clear()
    Component._next_id = 0
    Wire._next_id = 0

    # Clock generator
    clock = Component('CLOCK', 80, 200, 'CLK')
    clock.properties['frequency'] = 2.0
    sim.add_component(clock)

    # Chain of NOT gates as a simple frequency divider demonstration
    # (In real hardware you'd use flip-flops, but we demonstrate with gates)
    not1 = Component('NOT', 200, 170, 'N1')
    sim.add_component(not1)
    not2 = Component('NOT', 320, 170, 'N2')
    sim.add_component(not2)
    not3 = Component('NOT', 440, 170, 'N3')
    sim.add_component(not3)

    # Some gates to create different patterns
    and1 = Component('AND', 200, 280, 'A1')
    sim.add_component(and1)
    or1 = Component('OR', 320, 280, 'O1')
    sim.add_component(or1)

    # Seven segment display
    seven_seg = Component('SEVEN_SEGMENT', 560, 160, 'DISP')
    sim.add_component(seven_seg)

    # Output to monitor clock
    out_clk = Component('OUTPUT', 200, 100, 'CLK_OUT')
    sim.add_component(out_clk)

    # Wires: clock -> NOT chain and output
    sim.add_wire(Wire(clock.id, 'out', out_clk.id, 'in0'))
    sim.add_wire(Wire(clock.id, 'out', not1.id, 'in0'))
    sim.add_wire(Wire(not1.id, 'out', not2.id, 'in0'))
    sim.add_wire(Wire(not2.id, 'out', not3.id, 'in0'))

    # Connect clock and gates to seven segment display segments
    sim.add_wire(Wire(clock.id, 'out', seven_seg.id, 'a'))
    sim.add_wire(Wire(not1.id, 'out', seven_seg.id, 'b'))
    sim.add_wire(Wire(not2.id, 'out', seven_seg.id, 'c'))
    sim.add_wire(Wire(not3.id, 'out', seven_seg.id, 'd'))
    sim.add_wire(Wire(clock.id, 'out', and1.id, 'in0'))
    sim.add_wire(Wire(not1.id, 'out', and1.id, 'in1'))
    sim.add_wire(Wire(and1.id, 'out', seven_seg.id, 'e'))
    sim.add_wire(Wire(not2.id, 'out', or1.id, 'in0'))
    sim.add_wire(Wire(not3.id, 'out', or1.id, 'in1'))
    sim.add_wire(Wire(or1.id, 'out', seven_seg.id, 'f'))
    sim.add_wire(Wire(not3.id, 'out', seven_seg.id, 'g'))


def main():
    app = LogicSimulator()
    # Load a default sample
    create_sample_half_adder(app.sim)
    app._recompute_all_wire_paths()
    app.run()


if __name__ == '__main__':
    main()
