"""Selection management for components."""

from __future__ import annotations

import pygame
from typing import Optional, TYPE_CHECKING
from config import COLOR_SELECTION_RECT, COLOR_SELECTION_RECT_BORDER, GRID_SIZE

if TYPE_CHECKING:
    from components import Component
    from camera import Camera
    from simulation import Simulator


class SelectionManager:
    """Manages component selection, rubber-band selection, and dragging."""

    def __init__(self):
        self.selected_components: list['Component'] = []
        self.dragging: bool = False
        self.drag_start_world: Optional[pygame.Vector2] = None
        self.drag_start_positions: dict[str, pygame.Vector2] = {}
        self.rubber_banding: bool = False
        self.rubber_start_screen: Optional[tuple] = None
        self.rubber_end_screen: Optional[tuple] = None

    def select(self, component: 'Component', add: bool = False):
        """Select a single component."""
        if not add:
            self.clear_selection()
        if component not in self.selected_components:
            component.selected = True
            self.selected_components.append(component)

    def deselect(self, component: 'Component'):
        """Deselect a single component."""
        component.selected = False
        if component in self.selected_components:
            self.selected_components.remove(component)

    def clear_selection(self):
        """Deselect all components."""
        for comp in self.selected_components:
            comp.selected = False
        self.selected_components.clear()

    def toggle_selection(self, component: 'Component'):
        """Toggle selection of a component."""
        if component in self.selected_components:
            self.deselect(component)
        else:
            self.select(component, add=True)

    def start_drag(self, world_pos: pygame.Vector2):
        """Begin dragging selected components."""
        self.dragging = True
        self.drag_start_world = world_pos.copy()
        self.drag_start_positions = {
            comp.id: comp.position.copy()
            for comp in self.selected_components
        }

    def update_drag(self, world_pos: pygame.Vector2, simulator: 'Simulator'):
        """Move selected components based on current drag position."""
        if not self.dragging or self.drag_start_world is None:
            return

        delta = world_pos - self.drag_start_world
        # Snap delta to grid
        snapped_delta = pygame.Vector2(
            round(delta.x / GRID_SIZE) * GRID_SIZE,
            round(delta.y / GRID_SIZE) * GRID_SIZE,
        )

        for comp in self.selected_components:
            if comp.id in self.drag_start_positions:
                comp.position = self.drag_start_positions[comp.id] + snapped_delta

        # Recompute all affected wires
        self._update_wires_after_move(simulator)

    def end_drag(self):
        """Finish dragging."""
        self.dragging = False
        self.drag_start_world = None
        self.drag_start_positions.clear()

    def _update_wires_after_move(self, simulator: 'Simulator'):
        """Recompute wire routes for wires connected to selected components."""
        moved_ids = {c.id for c in self.selected_components}
        for wire in simulator.wires:
            sid = wire.start_pin.parent_component.id
            eid = wire.end_pin.parent_component.id
            if sid in moved_ids or eid in moved_ids:
                wire.recompute_route()

    def start_rubber_band(self, screen_pos: tuple):
        """Start rubber-band selection."""
        self.rubber_banding = True
        self.rubber_start_screen = screen_pos
        self.rubber_end_screen = screen_pos

    def update_rubber_band(self, screen_pos: tuple):
        """Update rubber-band rectangle."""
        if self.rubber_banding:
            self.rubber_end_screen = screen_pos

    def end_rubber_band(self, camera: 'Camera', components: list['Component'],
                         add: bool = False):
        """Finish rubber-band selection, selecting components inside the rectangle."""
        if not self.rubber_banding or self.rubber_start_screen is None or \
           self.rubber_end_screen is None:
            self.rubber_banding = False
            return

        if not add:
            self.clear_selection()

        # Convert screen rect to world rect
        sx1, sy1 = self.rubber_start_screen
        sx2, sy2 = self.rubber_end_screen
        screen_rect = pygame.Rect(
            min(sx1, sx2), min(sy1, sy2),
            abs(sx2 - sx1), abs(sy2 - sy1)
        )

        for comp in components:
            # Check if component rect overlaps with selection rect in screen space
            comp_tl = camera.world_to_screen(
                (comp.position.x - comp.width / 2, comp.position.y - comp.height / 2)
            )
            comp_br = camera.world_to_screen(
                (comp.position.x + comp.width / 2, comp.position.y + comp.height / 2)
            )
            comp_screen_rect = pygame.Rect(
                comp_tl.x, comp_tl.y,
                comp_br.x - comp_tl.x, comp_br.y - comp_tl.y
            )
            if screen_rect.colliderect(comp_screen_rect):
                self.select(comp, add=True)

        self.rubber_banding = False
        self.rubber_start_screen = None
        self.rubber_end_screen = None

    def cancel_rubber_band(self):
        """Cancel rubber-band selection."""
        self.rubber_banding = False
        self.rubber_start_screen = None
        self.rubber_end_screen = None

    def render_rubber_band(self, screen: pygame.Surface):
        """Render the rubber-band selection rectangle."""
        if not self.rubber_banding or self.rubber_start_screen is None or \
           self.rubber_end_screen is None:
            return

        sx1, sy1 = self.rubber_start_screen
        sx2, sy2 = self.rubber_end_screen
        rect = pygame.Rect(
            min(sx1, sx2), min(sy1, sy2),
            abs(sx2 - sx1), abs(sy2 - sy1)
        )

        # Draw semi-transparent fill
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill(COLOR_SELECTION_RECT)
        screen.blit(s, rect.topleft)

        # Draw border
        pygame.draw.rect(screen, COLOR_SELECTION_RECT_BORDER, rect, 1)
