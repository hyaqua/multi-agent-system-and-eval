"""Simulation engine for logic gate simulator."""

from __future__ import annotations
from typing import List, Dict, Set, Optional, Tuple
from components import Component, Pin, PinType, InputNode, ClockGenerator
from wires import Wire, WireManager


class SimulationEngine:
    """Handles signal propagation, cycle detection, and component evaluation."""

    def __init__(self):
        self.components: List[Component] = []
        self.wire_manager: Optional[WireManager] = None
        self.cycle_components: Set[str] = set()  # Component IDs in cycles
        self.cycle_wires: Set[str] = set()  # Wire IDs in cycles
        self.evaluation_order: List[Component] = []
        self.has_cycle: bool = False

    def set_wire_manager(self, wm: WireManager):
        self.wire_manager = wm

    def add_component(self, comp: Component):
        if comp not in self.components:
            self.components.append(comp)

    def remove_component(self, comp: Component):
        if comp in self.components:
            self.components.remove(comp)

    def clear(self):
        self.components.clear()
        self.cycle_components.clear()
        self.cycle_wires.clear()
        self.evaluation_order.clear()
        self.has_cycle = False

    def update(self, dt: float):
        """Run one simulation step."""
        if not self.wire_manager:
            return

        # Step 1: Propagate values from output pins to connected input pins
        self._propagate_signals()

        # Step 2: Detect cycles and compute evaluation order
        self._detect_cycles()

        # Step 3: Update clock generators
        for comp in self.components:
            if isinstance(comp, ClockGenerator):
                comp.update(dt)

        # Step 4: Evaluate components in topological order
        # Propagate after each evaluation so downstream components see
        # updated values within the same frame
        for comp in self.evaluation_order:
            if comp.comp_id not in self.cycle_components:
                comp.evaluate()
                self._propagate_component_outputs(comp)

        # Step 5: Update error flags on components and wires
        for comp in self.components:
            comp.error = comp.comp_id in self.cycle_components
        for wire in self.wire_manager.wires:
            wire.error = wire.wire_id in self.cycle_wires

    def _propagate_component_outputs(self, comp: Component):
        """Propagate output values from a component to all connected input pins."""
        for wire in self.wire_manager.wires:
            if wire.from_comp == comp:
                wire.to_pin.value = wire.from_pin.value

    def _propagate_signals(self):
        """Copy values from output pins to connected input pins."""
        for wire in self.wire_manager.wires:
            wire.to_pin.value = wire.from_pin.value

    def _detect_cycles(self):
        """Detect combinational cycles using DFS and compute topological order."""
        self.cycle_components.clear()
        self.cycle_wires.clear()
        self.evaluation_order.clear()
        self.has_cycle = False

        # Build adjacency list: component -> list of components it drives
        # A drives B if A's output connects to B's input
        adjacency: Dict[str, List[str]] = {}
        for comp in self.components:
            adjacency[comp.comp_id] = []

        wire_from_to: Dict[str, Tuple[str, str]] = {}  # wire_id -> (from_comp_id, to_comp_id)

        if self.wire_manager:
            for wire in self.wire_manager.wires:
                from_id = wire.from_comp.comp_id
                to_id = wire.to_comp.comp_id
                adjacency.setdefault(from_id, []).append(to_id)
                adjacency.setdefault(to_id, [])
                wire_from_to[wire.wire_id] = (from_id, to_id)

        # DFS-based topological sort with cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {comp.comp_id: WHITE for comp in self.components}
        topo_order: List[str] = []
        cycles: Set[str] = set()  # Component IDs in cycles

        def dfs(node_id: str, path: List[Tuple[str, str]]) -> bool:
            """Returns True if a cycle is found. path is list of (from_id, to_id) edges."""
            color[node_id] = GRAY
            for neighbor in adjacency.get(node_id, []):
                edge = (node_id, neighbor)
                if color.get(neighbor) == GRAY:
                    # Found a cycle
                    cycles.add(node_id)
                    cycles.add(neighbor)
                    # Mark all wires in the path from neighbor to node_id
                    for e_from, e_to in path:
                        if e_from == neighbor or cycles:
                            cycles.add(e_from)
                            cycles.add(e_to)
                    # Also mark all edges in the cycle
                    return True
                elif color.get(neighbor) == WHITE:
                    if dfs(neighbor, path + [edge]):
                        cycles.add(node_id)
                        cycles.add(neighbor)
                        return True
            color[node_id] = BLACK
            topo_order.append(node_id)
            return False

        for comp in self.components:
            if color.get(comp.comp_id) == WHITE:
                dfs(comp.comp_id, [])

        # If any cycle detected, do a thorough search
        if cycles:
            self.has_cycle = True
            self.cycle_components = cycles

            # Find all wires in cycles
            for wire_id, (from_id, to_id) in wire_from_to.items():
                if from_id in cycles and to_id in cycles:
                    # Check if this wire is part of a cycle
                    # A wire is in a cycle if both endpoints are in cycles
                    # and there's a path from to_id back to from_id
                    if self._path_exists(to_id, from_id, adjacency, cycles):
                        self.cycle_wires.add(wire_id)

        # Build evaluation order (topological, reversed)
        self.evaluation_order = []
        seen = set()
        for comp_id in reversed(topo_order):
            for comp in self.components:
                if comp.comp_id == comp_id and comp_id not in seen:
                    self.evaluation_order.append(comp)
                    seen.add(comp_id)

        # Add any components not in topo order (shouldn't happen normally)
        for comp in self.components:
            if comp.comp_id not in seen:
                self.evaluation_order.append(comp)

    def _path_exists(self, start: str, end: str, adjacency: Dict[str, List[str]],
                     allowed_nodes: Set[str]) -> bool:
        """Check if there's a path from start to end using only allowed nodes."""
        visited = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node == end:
                return True
            if node in visited:
                continue
            visited.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor in allowed_nodes and neighbor not in visited:
                    stack.append(neighbor)
        return False

    def get_cycle_warning(self) -> Optional[str]:
        """Return a warning message if a cycle is detected."""
        if self.has_cycle:
            comp_names = []
            for cid in list(self.cycle_components)[:5]:
                for comp in self.components:
                    if comp.comp_id == cid:
                        comp_names.append(comp.label or comp.get_type_name())
                        break
            return f"Cycle detected! Involved: {', '.join(comp_names)}"
        return None
