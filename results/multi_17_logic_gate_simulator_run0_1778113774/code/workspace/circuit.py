"""Circuit model: components, wires, topological evaluation, cycle detection."""

from collections import deque
import components as comp_module
from components import Component, InputNode, ClockGenerator, Pin
from wires import Wire
from canvas import snap_to_grid


class Circuit:
    """Manages all components and wires, runs simulation."""

    def __init__(self):
        self.components: list[Component] = []
        self.wires: list[Wire] = []
        self._id_counter = 0
        self._dirty = True  # Need to rebuild dependency graph
        self._eval_order: list[Component] = []
        self._cycle_nodes: set[str] = set()  # component IDs in cycles
        self._cycle_wires: set[int] = set()  # indices of wires in cycles

    def generate_id(self) -> str:
        """Generate a unique component ID."""
        self._id_counter += 1
        return f"comp_{self._id_counter}"

    def set_id_counter(self, value: int):
        """Set the ID counter (after loading)."""
        self._id_counter = value

    def get_id_counter(self) -> int:
        return self._id_counter

    def add_component(self, comp: Component):
        """Add a component to the circuit."""
        self.components.append(comp)
        self._dirty = True

    def remove_component(self, comp_id: str):
        """Remove a component and all its connected wires."""
        comp = self.get_component_by_id(comp_id)
        if comp is None:
            return

        # Remove all wires connected to this component's pins
        wires_to_remove = []
        for i, wire in enumerate(self.wires):
            if wire.from_comp_id == comp_id or wire.to_comp_id == comp_id:
                wires_to_remove.append(i)

        # Remove from pins
        for pin in comp.pins:
            if pin.is_input:
                if pin.wire is not None:
                    # Also clean up the driver side
                    self._remove_wire_from_output(pin.wire)
                pin.wire = None
            else:
                for wire in pin.wires:
                    self._remove_wire_from_input(wire)
                pin.wires.clear()

        # Remove wires (in reverse order)
        for i in sorted(wires_to_remove, reverse=True):
            self.wires.pop(i)

        self.components.remove(comp)
        self._dirty = True

    def _remove_wire_from_output(self, wire: Wire):
        """Remove wire from the output pin that drives it."""
        driver = self.get_component_by_id(wire.from_comp_id)
        if driver:
            pin = driver.get_pin(wire.from_pin_id)
            if pin and wire in pin.wires:
                pin.wires.remove(wire)

    def _remove_wire_from_input(self, wire: Wire):
        """Remove wire from the input pin it feeds."""
        dest = self.get_component_by_id(wire.to_comp_id)
        if dest:
            pin = dest.get_pin(wire.to_pin_id)
            if pin and pin.wire == wire:
                pin.wire = None

    def add_wire(self, wire: Wire):
        """Add a wire to the circuit."""
        # Check if input pin already has a wire
        dest = self.get_component_by_id(wire.to_comp_id)
        if dest:
            pin = dest.get_pin(wire.to_pin_id)
            if pin and pin.wire is not None:
                # Remove existing wire
                self.remove_wire_by_ref(pin.wire)

        # Connect pins
        driver = self.get_component_by_id(wire.from_comp_id)
        if driver:
            pin = driver.get_pin(wire.from_pin_id)
            if pin:
                pin.wires.append(wire)

        if dest:
            pin = dest.get_pin(wire.to_pin_id)
            if pin:
                pin.wire = wire

        self.wires.append(wire)
        self._dirty = True

    def remove_wire_by_ref(self, wire: Wire):
        """Remove a specific wire."""
        if wire in self.wires:
            self.wires.remove(wire)
            self._remove_wire_from_output(wire)
            self._remove_wire_from_input(wire)
            self._dirty = True

    def remove_wire_at(self, world_x: float, world_y: float) -> Wire | None:
        """Remove wire hit by world coordinates. Returns the removed wire or None."""
        for wire in self.wires:
            if wire.hit_test(world_x, world_y):
                self.remove_wire_by_ref(wire)
                return wire
        return None

    def get_wire_at(self, world_x: float, world_y: float) -> Wire | None:
        """Get wire at world coordinates."""
        for wire in self.wires:
            if wire.hit_test(world_x, world_y):
                return wire
        return None

    def get_component_by_id(self, comp_id: str) -> Component | None:
        """Find component by ID."""
        for comp in self.components:
            if comp.comp_id == comp_id:
                return comp
        return None

    def get_component_at(self, world_x: float, world_y: float) -> Component | None:
        """Find component at world position."""
        for comp in self.components:
            if comp.contains_point(world_x, world_y):
                return comp
        return None

    def get_pin_at(self, world_x: float, world_y: float) -> tuple[Component | None, Pin | None]:
        """Find pin at world position. Returns (component, pin) or (None, None)."""
        for comp in self.components:
            pin = comp.hit_test_pin(world_x, world_y)
            if pin is not None:
                return comp, pin
        return None, None

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        """Build adjacency list: component_id -> list of downstream component_ids."""
        graph: dict[str, list[str]] = {}
        # Initialize all components
        for comp in self.components:
            graph[comp.comp_id] = []

        for wire in self.wires:
            # Edges from driver to destination
            if wire.from_comp_id in graph and wire.to_comp_id in graph:
                graph[wire.from_comp_id].append(wire.to_comp_id)

        return graph

    def _topological_sort(self, graph: dict[str, list[str]]) -> tuple[list[Component], set[str]]:
        """Topological sort components. Returns (ordered list, set of cycle nodes)."""
        in_degree: dict[str, int] = {}
        for comp_id in graph:
            in_degree[comp_id] = 0
        for comp_id, deps in graph.items():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue = deque([cid for cid, deg in in_degree.items() if deg == 0])
        order: list[str] = []

        while queue:
            cid = queue.popleft()
            order.append(cid)
            for dep in graph.get(cid, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        # Nodes remaining in in_degree with degree > 0 are in cycles
        cycle_nodes: set[str] = set()
        for cid, deg in in_degree.items():
            if deg > 0:
                cycle_nodes.add(cid)

        # Convert to component objects
        order_comps = []
        for cid in order:
            comp = self.get_component_by_id(cid)
            if comp:
                order_comps.append(comp)

        return order_comps, cycle_nodes

    def _identify_cycle_wires(self, cycle_nodes: set[str]):
        """Find wires involved in cycles."""
        self._cycle_wires.clear()
        for i, wire in enumerate(self.wires):
            if wire.from_comp_id in cycle_nodes and wire.to_comp_id in cycle_nodes:
                self._cycle_wires.add(i)

    def evaluate(self):
        """Run one full evaluation of the circuit."""
        if self._dirty:
            # Rebuild dependency graph and sort
            graph = self._build_dependency_graph()
            self._eval_order, self._cycle_nodes = self._topological_sort(graph)
            self._identify_cycle_wires(self._cycle_nodes)
            self._dirty = False

        # Mark cycle states
        for comp in self.components:
            comp.in_cycle = comp.comp_id in self._cycle_nodes
        for i, wire in enumerate(self.wires):
            wire.in_cycle = i in self._cycle_wires

        # Update special components (clocks)
        for comp in self.components:
            if isinstance(comp, ClockGenerator):
                comp.update()

        # Evaluate all components in topological order
        for comp in self._eval_order:
            if comp.comp_id not in self._cycle_nodes:
                comp.evaluate()

        # For cycle nodes, we don't evaluate them (outputs remain as-is)
        # But we still need to set their output states to something deterministic
        # We just leave them with their previous states.

    def get_cycle_message(self) -> str | None:
        """Return cycle warning message if cycles detected."""
        if self._cycle_nodes:
            return "CYCLE DETECTED"
        return None

    def move_component(self, comp_id: str, new_x: float, new_y: float):
        """Move a component to a new position and update wire routings."""
        comp = self.get_component_by_id(comp_id)
        if comp is None:
            return
        comp.x = snap_to_grid(new_x)
        comp.y = snap_to_grid(new_y)

        # Update wire routing for all connected wires
        for pin in comp.pins:
            if pin.is_input:
                if pin.wire is not None:
                    # Update routing - find the driver output pin world pos
                    driver = self.get_component_by_id(pin.wire.from_comp_id)
                    if driver:
                        from_pos = driver.get_pin_world_pos(pin.wire.from_pin_id)
                        to_pos = comp.get_pin_world_pos(pin.pin_id)
                        if from_pos and to_pos:
                            pin.wire.update_routing(from_pos, to_pos)
            else:
                for wire in pin.wires:
                    dest = self.get_component_by_id(wire.to_comp_id)
                    if dest:
                        from_pos = comp.get_pin_world_pos(pin.pin_id)
                        to_pos = dest.get_pin_world_pos(wire.to_pin_id)
                        if from_pos and to_pos:
                            wire.update_routing(from_pos, to_pos)

    def clear(self):
        """Clear the entire circuit."""
        self.components.clear()
        self.wires.clear()
        self._dirty = True
        self._eval_order.clear()
        self._cycle_nodes.clear()
        self._cycle_wires.clear()

    def to_dict(self) -> dict:
        """Serialize circuit to dictionary."""
        return {
            "id_counter": self._id_counter,
            "components": [comp.to_dict() for comp in self.components],
            "wires": [wire.to_dict() for wire in self.wires],
        }

    def from_dict(self, data: dict):
        """Load circuit from dictionary."""
        self.clear()

        # Set ID counter
        self._id_counter = data.get("id_counter", 0)

        # Rebuild component lookup for wire reconnection
        for comp_data in data.get("components", []):
            comp_type = comp_data["type"]
            pos = comp_data["pos"]
            comp_id = comp_data["id"]
            name = comp_data.get("name", "")
            frequency = comp_data.get("frequency", None)
            initial_state = comp_data.get("state", False)

            comp = comp_module.create_component(
                comp_type, comp_id, pos[0], pos[1],
                name=name, frequency=frequency, initial_state=initial_state,
            )
            self.components.append(comp)

        # Reconnect wires
        for wire_data in data.get("wires", []):
            wire = Wire.from_dict(wire_data)
            self.add_wire(wire)

        self._dirty = True
        # Run initial evaluation to set states
        self.evaluate()
