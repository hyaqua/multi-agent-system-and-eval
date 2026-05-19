#!/usr/bin/env python3
"""Logic Gate Simulator - Main Entry Point.

A graphical logic gate simulator with infinite canvas, zoom/pan,
real-time simulation, cycle detection, and save/load support.
"""

import pygame
import sys
import os
import tempfile
from typing import Optional, Tuple, List

from viewport import Viewport
from components import (
    Component, Pin, PinType,
    InputNode, OutputNode, ClockGenerator, SevenSegmentDisplay,
    create_component, COMPONENT_TYPES
)
from wires import Wire, WireManager
from simulation import SimulationEngine
from toolbar import Toolbar, PropertiesPanel, TextPrompt
from file_io import (
    save_circuit, load_circuit, reconstruct_wires,
    save_sample_circuits
)


# Constants
TOOLBAR_WIDTH = 170
BG_COLOR = (245, 245, 248)
CANVAS_BG = (250, 250, 252)
FPS = 60


class LogicGateSimulator:
    """Main application class."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Logic Gate Simulator")

        self.window_width = 1280
        self.window_height = 800

        self.screen = pygame.display.set_mode((self.window_width, self.window_height),
                                               pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        # Canvas area (everything right of toolbar)
        self.canvas_rect = pygame.Rect(TOOLBAR_WIDTH, 0,
                                        self.window_width - TOOLBAR_WIDTH,
                                        self.window_height)

        # Core systems
        self.viewport = Viewport(self.canvas_rect)
        self.wire_manager = WireManager()
        self.simulation = SimulationEngine()
        self.simulation.set_wire_manager(self.wire_manager)
        self.toolbar = Toolbar(self.window_height)
        self.properties_panel = PropertiesPanel()
        self.text_prompt = TextPrompt()

        # Component tracking
        self.components: List[Component] = []
        self._next_comp_id: int = 0

        # Selection state
        self.selected_components: List[Component] = []
        self.selection_box: Optional[pygame.Rect] = None  # Screen coords
        self.selection_start: Optional[Tuple[int, int]] = None

        # Drag state
        self.dragging: bool = False
        self.drag_offset: dict = {}  # comp_id -> (offset_x, offset_y) in world coords
        self.drag_start_positions: dict = {}  # comp_id -> (x, y)

        # Wire drawing state
        self.wire_start_pin: Optional[Pin] = None
        self.wire_start_comp: Optional[Component] = None
        self.wire_mouse_pos: Optional[Tuple[float, float]] = None  # World coords

        # Placement mode
        self.placement_mode: bool = False
        self.placement_type: Optional[str] = None
        self.placement_preview_pos: Optional[Tuple[float, float]] = None

        # Panning with space+left
        self.space_held: bool = False

        # Warning message
        self.warning_message: Optional[str] = None
        self.warning_timer: float = 0.0

        # Samples directory (use temp dir for portability)
        self.samples_dir = os.path.join(tempfile.gettempdir(),
                                        "logic_gate_simulator_samples")
        # Also try project-local samples
        self._local_samples_dir = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "samples")

        # Load sample circuits
        self._init_samples()

    def _init_samples(self):
        """Ensure sample circuit files exist."""
        # Try local samples first, fall back to temp
        samples_dir = self._local_samples_dir
        try:
            os.makedirs(samples_dir, exist_ok=True)
        except (OSError, PermissionError):
            samples_dir = self.samples_dir
            try:
                os.makedirs(samples_dir, exist_ok=True)
            except Exception:
                return

        self.samples_dir = samples_dir
        half_adder_path = os.path.join(samples_dir, "half_adder.json")
        ripple_path = os.path.join(samples_dir, "ripple_counter.json")

        if not os.path.exists(half_adder_path) or not os.path.exists(ripple_path):
            try:
                save_sample_circuits(samples_dir)
            except Exception as e:
                print(f"Could not create samples: {e}")

    def get_next_id(self) -> str:
        """Generate a unique component ID."""
        cid = f"comp_{self._next_comp_id}"
        self._next_comp_id += 1
        return cid

    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds

            # Handle events
            self._handle_events()

            # Update
            self._update(dt)

            # Draw
            self._draw()

            # Flip display
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _handle_events(self):
        """Process all pending pygame events."""
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            # Text prompt consumes ALL events when active
            if self.text_prompt.active:
                self.text_prompt.handle_event(event)
                continue

            # Properties panel keyboard
            if self.properties_panel.visible:
                if event.type == pygame.KEYDOWN:
                    self.properties_panel.handle_key(event)

            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                self._handle_resize(event)

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event, mouse_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event, mouse_pos)

            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event, mouse_pos)

        # Update hover states continuously
        self.toolbar.update_hover(mouse_pos)

    def _handle_resize(self, event):
        """Handle window resize."""
        self.window_width = event.w
        self.window_height = event.h
        self.screen = pygame.display.set_mode((self.window_width, self.window_height),
                                               pygame.RESIZABLE)
        self.canvas_rect = pygame.Rect(TOOLBAR_WIDTH, 0,
                                        self.window_width - TOOLBAR_WIDTH,
                                        self.window_height)
        self.viewport.canvas_rect = self.canvas_rect
        self.toolbar.height = self.window_height

    def _handle_keydown(self, event):
        """Handle key press events."""
        if event.key == pygame.K_SPACE:
            self.space_held = True

        elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            # Delete selected components (but not if editing properties)
            if not self.properties_panel.visible:
                self._delete_selected()

        elif event.key == pygame.K_ESCAPE:
            # Cancel placement mode or deselect
            if self.placement_mode:
                self._exit_placement_mode()
            elif self.wire_start_pin:
                self._cancel_wire()
            else:
                self.selected_components.clear()
                self.properties_panel.hide()

        elif event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            # Save (Ctrl+S)
            self._prompt_save()

        elif event.key == pygame.K_o and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            # Load (Ctrl+O)
            self._prompt_load()

    def _handle_keyup(self, event):
        """Handle key release events."""
        if event.key == pygame.K_SPACE:
            self.space_held = False

    def _handle_mouse_down(self, event, mouse_pos):
        """Handle mouse button press."""
        mx, my = mouse_pos

        # Check properties panel first
        if self.properties_panel.visible:
            if self.properties_panel.handle_click(mouse_pos):
                return

        # Check toolbar click
        if self.toolbar.rect.collidepoint(mx, my):
            if event.button == 1:  # Left click
                comp_type = self.toolbar.handle_click(mouse_pos)
                if comp_type:
                    self._enter_placement_mode(comp_type)
                else:
                    self._exit_placement_mode()
            return

        # Must be on canvas
        if not self.viewport.is_in_canvas(mx, my):
            return

        wx, wy = self.viewport.screen_to_world(mx, my)

        if event.button == 1:  # Left click
            if self.space_held:
                # Pan with space+left drag
                self.viewport.start_pan(mouse_pos)
                return

            if self.placement_mode:
                # Place component
                self._place_component(wx, wy)
                return

            # Check if clicking on a pin for wire drawing
            pin, comp = self._find_pin_at_world(wx, wy)
            if pin and pin.pin_type == PinType.OUTPUT:
                # Start wire from output pin
                self.wire_start_pin = pin
                self.wire_start_comp = comp
                self.wire_mouse_pos = (wx, wy)
                return
            elif pin and pin.pin_type == PinType.INPUT and self.wire_start_pin:
                # Complete wire to input pin
                self._complete_wire(pin, comp)
                return

            # Check if clicking on a component
            clicked_comp = self._find_component_at_world(wx, wy)
            if clicked_comp:
                # Check for input node toggle
                if isinstance(clicked_comp, InputNode):
                    clicked_comp.toggle()
                    if clicked_comp not in self.selected_components:
                        self.selected_components = [clicked_comp]
                    return

                # Select/drag
                ctrl_held = pygame.key.get_mods() & pygame.KMOD_CTRL
                if ctrl_held:
                    # Toggle selection
                    if clicked_comp in self.selected_components:
                        self.selected_components.remove(clicked_comp)
                    else:
                        self.selected_components.append(clicked_comp)
                else:
                    if clicked_comp not in self.selected_components:
                        self.selected_components = [clicked_comp]
                    # Start dragging
                    self.dragging = True
                    self.drag_offset = {}
                    self.drag_start_positions = {}
                    for comp in self.selected_components:
                        self.drag_offset[comp.comp_id] = (comp.x - wx, comp.y - wy)
                        self.drag_start_positions[comp.comp_id] = (comp.x, comp.y)
                return

            # Start rubber band selection
            self.selection_start = (mx, my)
            self.selection_box = pygame.Rect(mx, my, 0, 0)
            if not pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.selected_components.clear()

        elif event.button == 2:  # Middle mouse
            # Pan
            self.viewport.start_pan(mouse_pos)

        elif event.button == 3:  # Right click
            # In placement mode, right-click cancels placement
            if self.placement_mode:
                self._exit_placement_mode()
                return

            # Cancel wire drawing
            if self.wire_start_pin:
                self._cancel_wire()
                return

            # Check for wire deletion
            wire = self.wire_manager.find_wire_at_world(wx, wy,
                tolerance=8.0 / self.viewport.zoom)
            if wire:
                self.wire_manager.remove_wire(wire)
                return

            # Check for component properties
            comp = self._find_component_at_world(wx, wy)
            if comp:
                self.properties_panel.show(comp, mouse_pos)
                return

            # Deselect all
            self.selected_components.clear()

        elif event.button == 4:  # Scroll up
            self.viewport.zoom_at_point(mouse_pos, True)
            self.wire_manager.update_all_routings()

        elif event.button == 5:  # Scroll down
            self.viewport.zoom_at_point(mouse_pos, False)
            self.wire_manager.update_all_routings()

    def _handle_mouse_up(self, event, mouse_pos):
        """Handle mouse button release."""
        if event.button == 1:
            # End selection box
            if self.selection_box:
                self._finalize_selection_box()
                self.selection_box = None
                self.selection_start = None

            # End dragging
            if self.dragging:
                self.dragging = False
                self.drag_offset.clear()
                self.drag_start_positions.clear()

        elif event.button == 2:
            self.viewport.end_pan()

    def _handle_mouse_motion(self, event, mouse_pos):
        """Handle mouse movement."""
        mx, my = mouse_pos

        # Update panning
        if self.viewport.panning:
            self.viewport.update_pan(mouse_pos)

        # Update selection box
        if self.selection_box is not None and self.selection_start:
            x1, y1 = self.selection_start
            self.selection_box = pygame.Rect(
                min(x1, mx), min(y1, my),
                abs(mx - x1), abs(my - y1)
            )

        # Update dragging
        if self.dragging and self.selected_components:
            wx, wy = self.viewport.screen_to_world(mx, my)
            for comp in self.selected_components:
                if comp.comp_id in self.drag_offset:
                    off_x, off_y = self.drag_offset[comp.comp_id]
                    comp.x = wx + off_x
                    comp.y = wy + off_y
                    comp.update_pin_positions()
            self.wire_manager.update_all_routings()

        # Update wire drawing preview
        if self.wire_start_pin and self.viewport.is_in_canvas(mx, my):
            wx, wy = self.viewport.screen_to_world(mx, my)
            self.wire_mouse_pos = (wx, wy)

        # Update placement preview
        if self.placement_mode and self.viewport.is_in_canvas(mx, my):
            wx, wy = self.viewport.screen_to_world(mx, my)
            # Snap to grid
            wx = round(wx / 20) * 20
            wy = round(wy / 20) * 20
            self.placement_preview_pos = (wx, wy)

    def _enter_placement_mode(self, comp_type: str):
        """Enter component placement mode."""
        self.placement_mode = True
        self.placement_type = comp_type
        self.placement_preview_pos = None
        self.selected_components.clear()
        self._cancel_wire()

    def _exit_placement_mode(self):
        """Exit component placement mode."""
        self.placement_mode = False
        self.placement_type = None
        self.placement_preview_pos = None
        self.toolbar.clear_selection()

    def _place_component(self, wx: float, wy: float):
        """Place a component at the given world position."""
        if not self.placement_type:
            return

        # Snap to grid
        wx = round(wx / 20) * 20
        wy = round(wy / 20) * 20

        comp_id = self.get_next_id()
        try:
            comp = create_component(self.placement_type, comp_id, wx, wy,
                                    label="")
            self.components.append(comp)
            self.simulation.add_component(comp)
        except Exception as e:
            print(f"Error creating component: {e}")

        # Stay in placement mode for multiple placements

    def _complete_wire(self, to_pin: Pin, to_comp: Component):
        """Complete a wire connection."""
        if not self.wire_start_pin or not self.wire_start_comp:
            return

        # Validate
        if self.wire_start_pin.pin_type != PinType.OUTPUT:
            self._cancel_wire()
            return
        if to_pin.pin_type != PinType.INPUT:
            self._cancel_wire()
            return
        if self.wire_start_comp == to_comp:
            self._cancel_wire()
            return

        # Add wire
        wire = self.wire_manager.add_wire(
            self.wire_start_pin, to_pin,
            self.wire_start_comp, to_comp
        )
        if wire:
            wire.update_routing()

        # Reset wire drawing state
        self._cancel_wire()

    def _cancel_wire(self):
        """Cancel wire drawing."""
        self.wire_start_pin = None
        self.wire_start_comp = None
        self.wire_mouse_pos = None

    def _delete_selected(self):
        """Delete all selected components."""
        for comp in list(self.selected_components):
            self._remove_component(comp)
        self.selected_components.clear()

    def _remove_component(self, comp: Component):
        """Remove a component and its wires."""
        self.wire_manager.remove_wires_for_component(comp)
        self.simulation.remove_component(comp)
        if comp in self.components:
            self.components.remove(comp)

    def _find_component_at_world(self, wx: float, wy: float) -> Optional[Component]:
        """Find a component at the given world position (topmost first)."""
        for comp in reversed(self.components):
            if comp.contains_point(wx, wy):
                return comp
        return None

    def _find_pin_at_world(self, wx: float, wy: float) -> Tuple[Optional[Pin], Optional[Component]]:
        """Find a pin at the given world position."""
        for comp in reversed(self.components):
            pin = comp.get_pin_at_world(wx, wy)
            if pin:
                return pin, comp
        return None, None

    def _finalize_selection_box(self):
        """Convert selection box (screen coords) to selected components (world coords)."""
        if not self.selection_box:
            return

        # Only process if box is large enough
        if self.selection_box.width < 5 and self.selection_box.height < 5:
            return

        # Convert selection box corners to world coordinates
        sx1, sy1 = self.selection_box.topleft
        sx2, sy2 = self.selection_box.bottomright

        # Only consider canvas area
        wx1, wy1 = self.viewport.screen_to_world(
            max(sx1, self.canvas_rect.x),
            max(sy1, self.canvas_rect.y)
        )
        wx2, wy2 = self.viewport.screen_to_world(
            min(sx2, self.canvas_rect.right),
            min(sy2, self.canvas_rect.bottom)
        )

        world_rect = pygame.Rect(
            min(wx1, wx2), min(wy1, wy2),
            abs(wx2 - wx1), abs(wy2 - wy1)
        )

        for comp in self.components:
            comp_rect = pygame.Rect(comp.x, comp.y, comp.width, comp.height)
            if world_rect.colliderect(comp_rect):
                if comp not in self.selected_components:
                    self.selected_components.append(comp)

    def _prompt_save(self):
        """Show save prompt."""
        center = (self.window_width // 2, self.window_height // 2)

        def on_save(filename):
            if not filename:
                return
            if not filename.endswith('.json'):
                filename += '.json'
            # Save to samples dir for easy access
            filepath = os.path.join(self.samples_dir, filename)
            try:
                os.makedirs(self.samples_dir, exist_ok=True)
            except Exception:
                pass
            success = save_circuit(self.components, self.wire_manager, filepath)
            if success:
                self.warning_message = f"Saved to {filename}"
                self.warning_timer = 3.0
            else:
                self.warning_message = "Save failed!"
                self.warning_timer = 3.0

        self.text_prompt.show("Save circuit as:", "circuit.json", on_save, center)

    def _prompt_load(self):
        """Show load prompt."""
        center = (self.window_width // 2, self.window_height // 2)

        def on_load(filename):
            if not filename:
                return
            if not filename.endswith('.json'):
                filename += '.json'
            filepath = os.path.join(self.samples_dir, filename)

            # Also try current directory
            if not os.path.exists(filepath):
                filepath = filename  # Try as given

            result = load_circuit(filepath)
            if result is None:
                self.warning_message = f"Could not load {filename}"
                self.warning_timer = 3.0
                return

            new_components, wires_data = result

            # Clear current circuit
            self._clear_circuit()

            # Add new components
            for comp in new_components:
                self.components.append(comp)
                self.simulation.add_component(comp)
                # Update ID counter
                if comp.comp_id.startswith("comp_"):
                    try:
                        num = int(comp.comp_id[5:])
                        self._next_comp_id = max(self._next_comp_id, num + 1)
                    except ValueError:
                        pass

            # Reconstruct wires
            n_wires = reconstruct_wires(new_components, wires_data, self.wire_manager)
            self.wire_manager.update_all_routings()

            self.warning_message = f"Loaded {filename} ({len(new_components)} components, {n_wires} wires)"
            self.warning_timer = 3.0

        self.text_prompt.show("Load circuit:", "circuit.json", on_load, center)

    def _clear_circuit(self):
        """Clear the entire circuit."""
        self.wire_manager.clear()
        self.simulation.clear()
        self.components.clear()
        self.selected_components.clear()
        self._next_comp_id = 0
        self.wire_start_pin = None
        self.wire_start_comp = None
        self.wire_mouse_pos = None
        self._exit_placement_mode()

    def _update(self, dt: float):
        """Update simulation and UI state."""
        # Update simulation
        self.simulation.update(dt)

        # Update warning timer
        if self.warning_timer > 0:
            self.warning_timer -= dt
            if self.warning_timer <= 0:
                self.warning_message = None

        # Update properties panel
        self.properties_panel.update(dt)

        # Check for cycle warning
        cycle_msg = self.simulation.get_cycle_warning()
        if cycle_msg:
            self.warning_message = cycle_msg
            self.warning_timer = 0.5  # Keep refreshing while cycle exists
        elif self.warning_timer <= 0 and self.warning_message and \
                "Cycle" in (self.warning_message or ""):
            self.warning_message = None

    def _draw(self):
        """Render everything."""
        self.screen.fill(BG_COLOR)

        # Draw canvas background
        pygame.draw.rect(self.screen, CANVAS_BG, self.canvas_rect)

        # Clip drawing to canvas
        self.viewport.apply_clip(self.screen)

        # Draw grid
        self.viewport.draw_grid(self.screen)

        # Draw wires (normal ones first, error ones on top)
        normal_wires = [w for w in self.wire_manager.wires if not w.error]
        error_wires = [w for w in self.wire_manager.wires if w.error]
        for wire in normal_wires:
            wire.draw(self.screen, self.viewport)
        for wire in error_wires:
            wire.draw(self.screen, self.viewport)

        # Draw wire-in-progress
        if self.wire_start_pin and self.wire_mouse_pos:
            self._draw_wire_preview()

        # Draw components (error ones on top)
        normal_comps = [c for c in self.components if not c.error]
        error_comps = [c for c in self.components if c.error]
        for comp in normal_comps:
            comp.draw(self.screen, self.viewport,
                      selected=(comp in self.selected_components))
        for comp in error_comps:
            comp.draw(self.screen, self.viewport,
                      selected=(comp in self.selected_components))

        # Draw placement preview
        if self.placement_mode and self.placement_preview_pos:
            self._draw_placement_preview()

        # Draw selection box
        if self.selection_box:
            self._draw_selection_box()

        self.viewport.remove_clip(self.screen)

        # Draw toolbar
        self.toolbar.draw(self.screen)

        # Draw properties panel
        self.properties_panel.draw(self.screen)

        # Draw text prompt
        self.text_prompt.draw(self.screen)

        # Draw corner overlay
        self._draw_overlay()

        # Draw warning message
        if self.warning_message:
            self._draw_warning()

    def _draw_wire_preview(self):
        """Draw preview of wire being created."""
        if not self.wire_start_pin or not self.wire_mouse_pos:
            return

        start = self.wire_start_pin.world_pos
        end = self.wire_mouse_pos
        GRID = 20.0

        sx, sy = round(start[0] / GRID) * GRID, round(start[1] / GRID) * GRID
        ex, ey = round(end[0] / GRID) * GRID, round(end[1] / GRID) * GRID

        if abs(sx - ex) < GRID and abs(sy - ey) < GRID:
            pts = [(sx, sy), (ex, ey)]
        elif abs(sy - ey) <= GRID:
            mid_x = round((sx + ex) / (2 * GRID)) * GRID
            pts = [(sx, sy), (mid_x, sy), (ex, ey)]
        elif sx + GRID < ex:
            mid_x = round((sx + ex) / (2 * GRID)) * GRID
            pts = [(sx, sy), (mid_x, sy), (mid_x, ey), (ex, ey)]
        else:
            route_x = max(sx, ex) + GRID * 2
            route_x = round(route_x / GRID) * GRID
            pts = [(sx, sy), (route_x, sy), (route_x, ey), (ex, ey)]

        screen_pts = []
        for wx, wy in pts:
            sx, sy = self.viewport.world_to_screen(wx, wy)
            screen_pts.append((int(sx), int(sy)))

        color = (100, 100, 200)
        width = max(1, int(2 * self.viewport.zoom))
        for i in range(len(screen_pts) - 1):
            pygame.draw.line(self.screen, color, screen_pts[i], screen_pts[i + 1], width)

    def _draw_placement_preview(self):
        """Draw ghost preview of component to be placed."""
        if not self.placement_preview_pos or not self.placement_type:
            return

        wx, wy = self.placement_preview_pos
        try:
            preview_comp = create_component(self.placement_type, "preview", wx, wy,
                                            label="")
        except Exception:
            return

        # Draw semi-transparent body
        sx, sy = self.viewport.world_to_screen(wx, wy)
        sw = preview_comp.width * self.viewport.zoom
        sh = preview_comp.height * self.viewport.zoom

        ghost_surf = pygame.Surface((max(1, int(sw)), max(1, int(sh))),
                                     pygame.SRCALPHA)
        ghost_surf.fill((100, 150, 200, 100))
        self.screen.blit(ghost_surf, (int(sx), int(sy)))

        # Draw border
        rect = pygame.Rect(int(sx), int(sy), max(1, int(sw)), max(1, int(sh)))
        pygame.draw.rect(self.screen, (60, 100, 180), rect,
                         width=max(1, int(2 * self.viewport.zoom)), border_radius=2)

        # Draw pins
        for pin in preview_comp.input_pins + preview_comp.output_pins:
            psx, psy = self.viewport.world_to_screen(pin.world_pos[0], pin.world_pos[1])
            pygame.draw.circle(self.screen, (100, 100, 180),
                               (int(psx), int(psy)),
                               max(2, int(4 * self.viewport.zoom)))

    def _draw_selection_box(self):
        """Draw rubber band selection box."""
        if not self.selection_box:
            return
        # Draw transparent fill
        surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(surf, (60, 120, 255, 40), self.selection_box)
        self.screen.blit(surf, (0, 0))
        pygame.draw.rect(self.screen, (60, 120, 255), self.selection_box, width=1)

    def _draw_overlay(self):
        """Draw coordinate and zoom indicator overlay."""
        try:
            font = pygame.font.Font(None, 18)
        except Exception:
            font = pygame.font.Font(None, 18)

        # Zoom level
        zoom_pct = int(self.viewport.zoom * 100)
        zoom_text = f"Zoom: {zoom_pct}%"
        zoom_surf = font.render(zoom_text, True, (60, 60, 80))
        zoom_rect = zoom_surf.get_rect()
        zoom_rect.bottomright = (self.window_width - 15, self.window_height - 10)
        bg_rect = zoom_rect.inflate(8, 4)
        pygame.draw.rect(self.screen, (230, 230, 235), bg_rect, border_radius=3)
        self.screen.blit(zoom_surf, zoom_rect)

        # World coords of cursor
        mx, my = pygame.mouse.get_pos()
        if self.viewport.is_in_canvas(mx, my):
            wx, wy = self.viewport.screen_to_world(mx, my)
            coord_text = f"({int(wx)}, {int(wy)})"
            coord_surf = font.render(coord_text, True, (60, 60, 80))
            coord_rect = coord_surf.get_rect()
            coord_rect.bottomright = (self.window_width - 15, self.window_height - 28)
            bg_rect = coord_rect.inflate(8, 4)
            pygame.draw.rect(self.screen, (230, 230, 235), bg_rect, border_radius=3)
            self.screen.blit(coord_surf, coord_rect)

    def _draw_warning(self):
        """Draw warning message at top of canvas."""
        if not self.warning_message:
            return

        try:
            font = pygame.font.Font(None, 22)
        except Exception:
            font = pygame.font.Font(None, 22)

        is_cycle = "Cycle" in self.warning_message
        color = (220, 40, 40) if is_cycle else (40, 40, 40)

        text_surf = font.render(self.warning_message, True, color)
        text_rect = text_surf.get_rect()
        text_rect.centerx = self.window_width // 2
        text_rect.y = 10

        # Background
        bg_rect = text_rect.inflate(20, 8)
        bg_color = (255, 220, 220) if is_cycle else (220, 240, 220)
        pygame.draw.rect(self.screen, bg_color, bg_rect, border_radius=4)
        pygame.draw.rect(self.screen, color, bg_rect, width=1, border_radius=4)
        self.screen.blit(text_surf, text_rect)


def main():
    """Entry point."""
    app = LogicGateSimulator()
    app.run()


if __name__ == "__main__":
    main()
