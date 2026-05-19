import sys
sys.dont_write_bytecode = True

"""Logic Gate Simulator – Main entry point."""

import pygame

from config import (
    GRID_SIZE, TOOLBAR_WIDTH, COLOR_BACKGROUND,
    COLOR_HIGH, COLOR_LOW,
)
from camera import Camera
from canvas import Canvas
from components import (
    COMPONENT_TYPES, InputNode, OutputNode, ClockGenerator,
)
from pins import OutputPin, InputPin
from wires import Wire
from simulation import Simulator
from toolbar import Toolbar
from selection import SelectionManager
from file_io import save_circuit, load_circuit
from ui_overlay import UIOverlay


class LogicGateSimulator:
    """Main application class."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Logic Gate Simulator")

        self.screen_width = 1200
        self.screen_height = 800
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height), pygame.RESIZABLE
        )
        self.clock = pygame.time.Clock()
        self.running = True

        # Core systems
        self.camera = Camera()
        self.simulator = Simulator()
        self.toolbar = Toolbar()
        self.selection = SelectionManager()
        self.overlay = UIOverlay()

        # Interaction state
        self.placement_mode: str | None = None  # component type to place
        self.wire_drawing: bool = False
        self.wire_start_pin: OutputPin | None = None
        self.wire_preview_end: pygame.Vector2 | None = None
        self.wire_preview_waypoints: list | None = None

        self.panning: bool = False
        self.pan_start_screen: tuple = (0, 0)
        self.space_held: bool = False
        self.middle_dragging: bool = False

        self.mouse_world = pygame.Vector2(0, 0)
        self.mouse_screen = (0, 0)

        self.current_filepath: str | None = None

        # For drag detection: was the mouse down on a selected component?
        self._drag_potential: bool = False
        self._drag_start_world: pygame.Vector2 | None = None

    # ── Main Loop ──────────────────────────────────────────────

    def run(self):
        """Run the main event loop."""
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self._handle_events()
            self._update()
            self._render()
        pygame.quit()
        sys.exit()

    # ── Event Handling ─────────────────────────────────────────

    def _handle_events(self):
        """Process all pending events."""
        for event in pygame.event.get():
            # File dialog consumes events if open
            if self.overlay.show_file_dialog:
                if self.overlay.handle_file_dialog_event(event):
                    continue

            # Properties panel consumes events if open
            if self.overlay.show_properties:
                if self.overlay.handle_properties_event(event, self.simulator):
                    continue

            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self.screen_width = event.w
                self.screen_height = event.h
                self.screen = pygame.display.set_mode(
                    (self.screen_width, self.screen_height), pygame.RESIZABLE
                )

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mousedown(event)

            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouseup(event)

            elif event.type == pygame.MOUSEMOTION:
                self._handle_mousemotion(event)

            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mousewheel(event)

            # Toolbar events
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self.toolbar.handle_event(event)
                    if result is not None:
                        self.placement_mode = self.toolbar.get_placement_type()
                        self.wire_drawing = False
                        self.wire_start_pin = None
                        self.selection.clear_selection()
                elif event.type == pygame.MOUSEMOTION:
                    self.toolbar.handle_event(event)

    def _handle_keydown(self, event: pygame.event.Event):
        """Handle key press events."""
        mods = pygame.key.get_mods()

        if event.key == pygame.K_ESCAPE:
            # Cancel current operation
            if self.wire_drawing:
                self.wire_drawing = False
                self.wire_start_pin = None
                self.wire_preview_end = None
            elif self.placement_mode:
                self.placement_mode = None
                self.toolbar.clear_selection()
            elif self.overlay.show_properties:
                self.overlay.close_properties()
            elif self.selection.rubber_banding:
                self.selection.cancel_rubber_band()
            else:
                self.selection.clear_selection()

        elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            # Delete selected components
            if self.selection.selected_components and not self.overlay.show_file_dialog:
                for comp in list(self.selection.selected_components):
                    self.simulator.remove_component(comp)
                self.selection.clear_selection()

        elif event.key == pygame.K_SPACE:
            self.space_held = True

        elif event.key == pygame.K_s and (mods & pygame.KMOD_CTRL):
            # Save
            if self.current_filepath:
                save_circuit(self.simulator, self.current_filepath)
            else:
                self.overlay.open_file_dialog("Save as:", self._save_callback)

        elif event.key == pygame.K_o and (mods & pygame.KMOD_CTRL):
            # Load
            self.overlay.open_file_dialog("Open file:", self._load_callback)

        elif event.key == pygame.K_1:
            self.placement_mode = "INPUT"
            self.toolbar.active_type = "INPUT"
            self.wire_drawing = False
        elif event.key == pygame.K_0:
            self.placement_mode = "OUTPUT"
            self.toolbar.active_type = "OUTPUT"
            self.wire_drawing = False

    def _handle_keyup(self, event: pygame.event.Event):
        """Handle key release events."""
        if event.key == pygame.K_SPACE:
            self.space_held = False

    def _handle_mousedown(self, event: pygame.event.Event):
        """Handle mouse button press."""
        self.mouse_screen = event.pos

        # Check if click is on toolbar
        if event.pos[0] < TOOLBAR_WIDTH:
            result = self.toolbar.handle_event(event)
            if result is not None:
                self.placement_mode = self.toolbar.get_placement_type()
                self.wire_drawing = False
                self.wire_start_pin = None
                self.selection.clear_selection()
            return

        world_pos = self.camera.screen_to_world(event.pos)
        self.mouse_world = world_pos

        # Close properties panel on click outside
        if self.overlay.show_properties:
            if self.overlay.properties_panel_rect and \
               not self.overlay.properties_panel_rect.collidepoint(event.pos):
                self.overlay.close_properties()

        # Middle mouse or space+left for panning
        if event.button == 2 or (event.button == 1 and self.space_held):
            self.panning = True
            self.pan_start_screen = event.pos
            if event.button == 2:
                self.middle_dragging = True
            return

        if event.button == 1:
            # Check for right-click on wire (for deletion)
            # (Handled in mouseup for click vs drag disambiguation)

            # Check for pin click (wiring)
            pin = self._find_pin_at_screen(event.pos)
            if pin is not None:
                if isinstance(pin, OutputPin):
                    # Start wire drawing
                    self.wire_drawing = True
                    self.wire_start_pin = pin
                    self.wire_preview_end = world_pos
                    self.placement_mode = None
                    self.toolbar.clear_selection()
                    return
                elif isinstance(pin, InputPin) and self.wire_drawing:
                    # Complete wire
                    if self.wire_start_pin is not None and pin.wire is None:
                        # Don't connect to same component
                        if pin.parent_component != self.wire_start_pin.parent_component:
                            wire = Wire(self.wire_start_pin, pin)
                            self.simulator.add_wire(wire)
                    self.wire_drawing = False
                    self.wire_start_pin = None
                    self.wire_preview_end = None
                    return

            # Cancel wire drawing if clicking elsewhere
            if self.wire_drawing:
                self.wire_drawing = False
                self.wire_start_pin = None
                self.wire_preview_end = None
                return

            # Placement mode
            if self.placement_mode:
                cls = COMPONENT_TYPES.get(self.placement_mode)
                if cls:
                    snapped = self._snap_to_grid(world_pos)
                    component = cls(snapped)
                    self.simulator.add_component(component)
                    # Stay in placement mode for repeated placement
                return

            # Check if clicking on a component
            clicked_comp = self._find_component_at_world(world_pos)
            if clicked_comp is not None:
                # Toggle INPUT node
                if isinstance(clicked_comp, InputNode):
                    clicked_comp.toggle()
                    return

                # Select and prepare for potential drag
                shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
                if clicked_comp in self.selection.selected_components:
                    # Clicking already-selected component: prepare for drag
                    self._drag_potential = True
                    self._drag_start_world = world_pos.copy()
                else:
                    self.selection.select(clicked_comp, add=shift_held)
                    self._drag_potential = True
                    self._drag_start_world = world_pos.copy()
                return

            # Start rubber-band selection
            self.selection.start_rubber_band(event.pos)
            return

        elif event.button == 3:
            # Right click: check for wire deletion or properties
            wire = self._find_wire_at_screen(event.pos)
            if wire is not None:
                self.simulator.remove_wire(wire)
                return

            comp = self._find_component_at_world(world_pos)
            if comp is not None:
                self.overlay.open_properties(comp, event.pos)
                return

            # Cancel placement mode
            if self.placement_mode:
                self.placement_mode = None
                self.toolbar.clear_selection()

    def _handle_mouseup(self, event: pygame.event.Event):
        """Handle mouse button release."""
        if event.button == 2:
            self.panning = False
            self.middle_dragging = False
            return

        if event.button == 1:
            if self.panning and not self.middle_dragging:
                self.panning = False
                return

            # End rubber band
            if self.selection.rubber_banding:
                shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT
                self.selection.end_rubber_band(
                    self.camera, self.simulator.components, add=shift_held
                )
                return

            # End drag
            if self.selection.dragging:
                self.selection.end_drag()
                self._drag_potential = False
                self._drag_start_world = None
                return

            self._drag_potential = False
            self._drag_start_world = None

    def _handle_mousemotion(self, event: pygame.event.Event):
        """Handle mouse movement."""
        self.mouse_screen = event.pos
        self.mouse_world = self.camera.screen_to_world(event.pos)

        toolbar_hover = event.pos[0] < TOOLBAR_WIDTH
        if event.type == pygame.MOUSEMOTION:
            self.toolbar.handle_event(event)

        # Panning
        if self.panning:
            dx = event.pos[0] - self.pan_start_screen[0]
            dy = event.pos[1] - self.pan_start_screen[1]
            self.camera.pan((dx, dy))
            self.pan_start_screen = event.pos
            return

        # Update rubber band
        if self.selection.rubber_banding:
            self.selection.update_rubber_band(event.pos)
            return

        # Wire preview
        if self.wire_drawing and self.wire_start_pin is not None:
            self.wire_preview_end = self.camera.screen_to_world(event.pos)
            return

        # Check for drag start
        if self._drag_potential and self._drag_start_world is not None:
            world_pos = self.camera.screen_to_world(event.pos)
            dist = world_pos.distance_to(self._drag_start_world)
            if dist > 5:  # threshold to start drag
                self._drag_potential = False
                if self.selection.selected_components:
                    self.selection.start_drag(self._drag_start_world)

        # Update drag
        if self.selection.dragging:
            world_pos = self.camera.screen_to_world(event.pos)
            self.selection.update_drag(world_pos, self.simulator)

    def _handle_mousewheel(self, event: pygame.event.Event):
        """Handle mouse wheel for zooming."""
        if event.pos[0] < TOOLBAR_WIDTH:
            return  # Don't zoom on toolbar
        self.camera.zoom_at_point(event.y, event.pos)

    # ── Update ─────────────────────────────────────────────────

    def _update(self):
        """Update simulation state."""
        self.simulator.update()
        self.overlay.update_cycle_warning(self.simulator)

    # ── Render ─────────────────────────────────────────────────

    def _render(self):
        """Render the entire application."""
        self.screen.fill(COLOR_BACKGROUND)

        # Draw canvas grid
        Canvas.render(self.screen, self.camera)

        # Draw wires
        for wire in self.simulator.wires:
            wire.render(self.screen, self.camera)

        # Draw wire preview
        if self.wire_drawing and self.wire_start_pin is not None and \
           self.wire_preview_end is not None:
            self._render_wire_preview()

        # Draw components
        for comp in self.simulator.components:
            comp.render(self.screen, self.camera)

        # Draw rubber-band selection
        self.selection.render_rubber_band(self.screen)

        # Draw toolbar (overlays canvas)
        self.toolbar.render(self.screen)

        # Draw overlays
        self.overlay.render_coordinates(self.screen, self.camera, self.mouse_world)
        self.overlay.render_cycle_warning(self.screen)
        self.overlay.render_properties(self.screen, self.camera)
        self.overlay.render_file_dialog(self.screen)

        # Draw placement cursor hint
        if self.placement_mode and self.mouse_screen[0] >= TOOLBAR_WIDTH:
            self._render_placement_preview()

        pygame.display.flip()

    def _render_wire_preview(self):
        """Render a preview of the wire being drawn."""
        if self.wire_start_pin is None or self.wire_preview_end is None:
            return

        start = self.wire_start_pin.world_pos
        end = self._snap_to_grid(self.wire_preview_end)

        # Simple orthogonal preview route
        from config import GRID_SIZE, COLOR_WIRE_PREVIEW
        mid_x = start.x + GRID_SIZE * 2

        waypoints = [start, pygame.Vector2(mid_x, start.y),
                     pygame.Vector2(mid_x, end.y), end]

        for i in range(len(waypoints) - 1):
            p1 = self.camera.world_to_screen(waypoints[i])
            p2 = self.camera.world_to_screen(waypoints[i + 1])
            pygame.draw.line(self.screen, COLOR_WIRE_PREVIEW,
                             (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 2)

    def _render_placement_preview(self):
        """Show a ghost of the component to be placed."""
        if not self.placement_mode:
            return
        world_pos = self._snap_to_grid(self.mouse_world)
        screen_pos = self.camera.world_to_screen(world_pos)

        cls = COMPONENT_TYPES.get(self.placement_mode)
        if cls is None:
            return

        # Draw ghost at snapped position
        w = cls.default_width * self.camera.zoom
        h = cls.default_height * self.camera.zoom
        rect = pygame.Rect(
            screen_pos.x - w / 2, screen_pos.y - h / 2, w, h
        )
        s = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        s.fill((100, 180, 255, 80))
        self.screen.blit(s, rect.topleft)
        pygame.draw.rect(self.screen, (100, 180, 255), rect, 1)

        # Draw label
        font = pygame.font.Font(None, max(10, int(14 * self.camera.zoom)))
        if font.get_height() > 0:
            label = self.placement_mode
            text_surf = font.render(label, True, (180, 200, 255))
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect)

    # ── Helper Methods ─────────────────────────────────────────

    def _snap_to_grid(self, world_pos: pygame.Vector2) -> pygame.Vector2:
        """Snap a world position to the nearest grid point."""
        return pygame.Vector2(
            round(world_pos.x / GRID_SIZE) * GRID_SIZE,
            round(world_pos.y / GRID_SIZE) * GRID_SIZE,
        )

    def _find_component_at_world(self, world_pos: pygame.Vector2):
        """Find the topmost component at a world position."""
        for comp in reversed(self.simulator.components):
            if comp.contains_point(world_pos):
                return comp
        return None

    def _find_pin_at_screen(self, screen_pos: tuple):
        """Find a pin at the given screen position."""
        for comp in self.simulator.components:
            pin = comp.get_pin_at_screen_pos(screen_pos, self.camera)
            if pin is not None:
                return pin
        return None

    def _find_wire_at_screen(self, screen_pos: tuple):
        """Find a wire at the given screen position."""
        for wire in reversed(self.simulator.wires):
            if wire.hit_test(screen_pos, self.camera):
                return wire
        return None

    def _save_callback(self, filepath: str):
        """Callback for save dialog."""
        self.current_filepath = filepath
        save_circuit(self.simulator, filepath)

    def _load_callback(self, filepath: str):
        """Callback for load dialog."""
        error = load_circuit(self.simulator, filepath)
        if error is None:
            self.current_filepath = filepath
            self.selection.clear_selection()
            self.wire_drawing = False
            self.wire_start_pin = None
            self.placement_mode = None
            self.toolbar.clear_selection()


# ── Entry Point ────────────────────────────────────────────────

def main():
    app = LogicGateSimulator()
    app.run()


if __name__ == "__main__":
    main()
