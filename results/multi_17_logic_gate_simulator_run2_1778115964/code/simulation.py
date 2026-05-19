"""Simulation engine: topological sort, cycle detection, state propagation."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    from components import Component
    from wires import Wire


class Simulator:
    """Holds all components and wires, runs continuous simulation."""

    def __init__(self):
        self.components: list['Component'] = []
        self.wires: list['Wire'] = []
        self.cycle_error: bool = False
        self.cycle_components: set[str] = set()
        self.cycle_wires: set[int] = set()  # indices of wires in cycle

    def add_component(self, component: 'Component'):
        self.components.append(component)

    def remove_component(self, component: 'Component'):
        """Remove a component and all connected wires."""
        # Remove connected wires first
        wires_to_remove = []
        for wire in self.wires:
            if wire.start_pin.parent_component == component or \
               wire.end_pin.parent_component == component:
                wires_to_remove.append(wire)

        for wire in wires_to_remove:
            self.remove_wire(wire)

        if component in self.components:
            self.components.remove(component)

    def add_wire(self, wire: 'Wire'):
        self.wires.append(wire)

    def remove_wire(self, wire: 'Wire'):
        """Remove a wire and clean up pin connections."""
        wire.disconnect()
        if wire in self.wires:
            self.wires.remove(wire)

    def update(self):
        """Run one simulation step: topological sort and evaluate."""
        # Reset cycle errors
        self.cycle_error = False
        self.cycle_components.clear()
        self.cycle_wires.clear()

        for comp in self.components:
            comp.has_cycle_error = False
        for wire in self.wires:
            wire.has_cycle_error = False

        # Build dependency graph
        # Component A depends on B if A's input is connected to B's output via a wire.
        comp_ids = {c.id: c for c in self.components}
        in_degree = {c.id: 0 for c in self.components}
        graph: dict[str, list[str]] = {c.id: [] for c in self.components}

        # Map from wire to (from_comp_id, to_comp_id)
        wire_deps: list[tuple[int, str, str]] = []  # (wire_index, from_id, to_id)

        for i, wire in enumerate(self.wires):
            from_comp = wire.start_pin.parent_component
            to_comp = wire.end_pin.parent_component
            if from_comp.id in comp_ids and to_comp.id in comp_ids:
                graph.setdefault(from_comp.id, []).append(to_comp.id)
                in_degree[to_comp.id] = in_degree.get(to_comp.id, 0) + 1
                wire_deps.append((i, from_comp.id, to_comp.id))

        # Kahn's algorithm for topological sort
        queue = deque([cid for cid, deg in in_degree.items() if deg == 0])
        sorted_ids = []

        while queue:
            cid = queue.popleft()
            sorted_ids.append(cid)
            for neighbor in graph.get(cid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_ids) != len(self.components):
            self.cycle_error = True
            cycle_ids = set(comp_ids.keys()) - set(sorted_ids)

            # Mark components in cycle
            for cid in cycle_ids:
                self.cycle_components.add(cid)
                if cid in comp_ids:
                    comp_ids[cid].has_cycle_error = True

            # Mark wires between cycle components
            for i, fid, tid in wire_deps:
                if fid in cycle_ids and tid in cycle_ids:
                    self.cycle_wires.add(i)
                    self.wires[i].has_cycle_error = True

            return  # Don't evaluate when there's a cycle

        # Evaluate in topological order
        for cid in sorted_ids:
            comp_ids[cid].evaluate()

    def get_component_by_id(self, comp_id: str) -> Optional['Component']:
        for c in self.components:
            if c.id == comp_id:
                return c
        return None

    def clear(self):
        """Remove all components and wires."""
        for wire in list(self.wires):
            self.remove_wire(wire)
        self.components.clear()
        self.cycle_error = False
        self.cycle_components.clear()
        self.cycle_wires.clear()
