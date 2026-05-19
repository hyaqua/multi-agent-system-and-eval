# circuit.py - Circuit state, simulation, cycle detection
from collections import defaultdict, deque
from components import *
from wires import Wire

class Circuit:
    """Manages all components and wires, handles simulation."""

    def __init__(self):
        self.components = {}  # comp_id -> Component
        self.wires = {}       # wire_id -> Wire
        self._next_comp_id = 0
        self._next_wire_id = 0
        self.cycle_components = set()  # comp_ids in a cycle
        self.cycle_wires = set()       # wire_ids in a cycle
        self.has_cycle = False
        self.topo_order = []  # topological order for evaluation

    def add_component(self, comp_type, x, y, label=""):
        """Create and add a component. Returns the component."""
        comp_id = f"comp_{self._next_comp_id}"
        self._next_comp_id += 1
        if comp_type == "AND":
            comp = AndGate(comp_id, x, y, label)
        elif comp_type == "OR":
            comp = OrGate(comp_id, x, y, label)
        elif comp_type == "NOT":
            comp = NotGate(comp_id, x, y, label)
        elif comp_type == "NAND":
            comp = NandGate(comp_id, x, y, label)
        elif comp_type == "NOR":
            comp = NorGate(comp_id, x, y, label)
        elif comp_type == "XOR":
            comp = XorGate(comp_id, x, y, label)
        elif comp_type == "XNOR":
            comp = XnorGate(comp_id, x, y, label)
        elif comp_type == "INPUT":
            comp = InputNode(comp_id, x, y, label)
        elif comp_type == "OUTPUT":
            comp = OutputNode(comp_id, x, y, label)
        elif comp_type == "CLOCK":
            comp = ClockGen(comp_id, x, y, label)
        elif comp_type == "SEVEN_SEGMENT":
            comp = SevenSegment(comp_id, x, y, label)
        else:
            raise ValueError(f"Unknown component type: {comp_type}")
        self.components[comp_id] = comp
        return comp

    def remove_component(self, comp_id):
        """Remove a component and all connected wires."""
        if comp_id not in self.components:
            return
        wires_to_remove = []
        for wire_id, wire in self.wires.items():
            if wire.from_comp_id == comp_id or wire.to_comp_id == comp_id:
                wires_to_remove.append(wire_id)
        for wid in wires_to_remove:
            del self.wires[wid]
        del self.components[comp_id]

    def add_wire(self, from_comp_id, from_pin_id, to_comp_id, to_pin_id):
        """Add a wire. Returns wire or None if invalid."""
        # Validate
        if from_comp_id not in self.components or to_comp_id not in self.components:
            return None
        from_comp = self.components[from_comp_id]
        to_comp = self.components[to_comp_id]

        # Check that from_pin is an output pin
        from_pin = None
        for p in from_comp.output_pins:
            if p.pin_id == from_pin_id:
                from_pin = p
                break
        if not from_pin:
            return None

        # Check that to_pin is an input pin
        to_pin = None
        for p in to_comp.input_pins:
            if p.pin_id == to_pin_id:
                to_pin = p
                break
        if not to_pin:
            return None

        # Check that the input pin isn't already connected
        for wire in self.wires.values():
            if wire.to_comp_id == to_comp_id and wire.to_pin_id == to_pin_id:
                return None  # Input pin already has a connection

        wire_id = f"wire_{self._next_wire_id}"
        self._next_wire_id += 1
        wire = Wire(wire_id, from_comp_id, from_pin_id, to_comp_id, to_pin_id)
        self.wires[wire_id] = wire
        return wire

    def remove_wire(self, wire_id):
        """Remove a wire by ID."""
        if wire_id in self.wires:
            del self.wires[wire_id]

    def get_wire_at(self, world_x, world_y, threshold=8):
        """Return wire_id if a wire is near the given world position."""
        for wire_id, wire in self.wires.items():
            if wire.hit_test(world_x, world_y, self.components, threshold):
                return wire_id
        return None

    def get_component_at(self, world_x, world_y):
        """Return component if one is at the given world position."""
        for comp in reversed(list(self.components.values())):
            if comp.contains_point(world_x, world_y):
                return comp
        return None

    def get_pin_at(self, world_x, world_y, max_dist=8):
        """Return (component, pin) if a pin is near the given world position."""
        for comp in self.components.values():
            pin = comp.get_pin_at(world_x, world_y, max_dist)
            if pin:
                return comp, pin
        return None, None

    def detect_cycles(self):
        """Detect cycles in the circuit using DFS. Returns (has_cycle, cycle_components, cycle_wires)."""
        # Build adjacency: comp_id -> list of comp_ids it feeds into
        adj = defaultdict(list)
        # Also track which wire connects them
        edge_to_wire = {}  # (from_comp, to_comp) -> wire_id

        for wire_id, wire in self.wires.items():
            adj[wire.from_comp_id].append(wire.to_comp_id)
            edge_to_wire[(wire.from_comp_id, wire.to_comp_id)] = wire_id

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {cid: WHITE for cid in self.components}
        parent = {}
        cycle_nodes = set()
        cycle_wires_set = set()

        def dfs(u):
            color[u] = GRAY
            for v in adj[u]:
                if color[v] == GRAY:
                    # Found a cycle - trace back
                    cycle_nodes.add(u)
                    cycle_nodes.add(v)
                    # Add the edge from u to v
                    wid = edge_to_wire.get((u, v))
                    if wid:
                        cycle_wires_set.add(wid)
                    # Trace back through parents
                    cur = u
                    while cur != v:
                        cycle_nodes.add(cur)
                        if cur not in parent:
                            break
                        p = parent[cur]
                        wid2 = edge_to_wire.get((p, cur))
                        if wid2:
                            cycle_wires_set.add(wid2)
                        cur = p
                    return True
                elif color[v] == WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
            color[u] = BLACK
            return False

        has_cycle = False
        for cid in self.components:
            if color[cid] == WHITE:
                if dfs(cid):
                    has_cycle = True
                    # Mark all remaining GRAY nodes as BLACK to prevent false cycle detection
                    for nid, c in color.items():
                        if c == GRAY:
                            color[nid] = BLACK

        self.has_cycle = has_cycle
        self.cycle_components = cycle_nodes
        self.cycle_wires = cycle_wires_set
        return has_cycle, cycle_nodes, cycle_wires_set

    def topological_sort(self):
        """Compute topological order using Kahn's algorithm. Returns list of comp_ids or None if cycle."""
        # Build adjacency and in-degree
        adj = defaultdict(list)
        in_degree = defaultdict(int)

        for cid in self.components:
            in_degree[cid] = 0

        for wire_id, wire in self.wires.items():
            adj[wire.from_comp_id].append(wire.to_comp_id)
            in_degree[wire.to_comp_id] += 1

        # Start with nodes that have no incoming edges
        queue = deque()
        for cid in self.components:
            if in_degree[cid] == 0:
                queue.append(cid)

        result = []
        while queue:
            u = queue.popleft()
            result.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(result) != len(self.components):
            return None  # Has cycle
        self.topo_order = result
        return result

    def simulate(self, dt):
        """Run one simulation step. dt is elapsed time in seconds."""
        # Update clocks
        for comp in self.components.values():
            if isinstance(comp, ClockGen):
                comp.update_clock(dt)

        # Detect cycles
        has_cycle, _, _ = self.detect_cycles()

        if has_cycle:
            # Still try to evaluate what we can, but mark cycle components
            # For cycle components, we don't update their state
            self._simulate_with_cycles()
        else:
            self._simulate_normal()

    def _simulate_normal(self):
        """Simulate assuming no cycles."""
        order = self.topological_sort()
        if order is None:
            return

        # Evaluate in topological order
        for comp_id in order:
            comp = self.components[comp_id]
            if isinstance(comp, InputNode):
                pass  # Input nodes maintain their own state
            elif isinstance(comp, ClockGen):
                pass  # Already updated via update_clock
            else:
                # Collect input values by reading upstream component outputs
                inputs = {}
                for wire_id, wire in self.wires.items():
                    if wire.to_comp_id == comp_id:
                        from_comp = self.components.get(wire.from_comp_id)
                        if from_comp:
                            out_val = getattr(from_comp, '_output_state', False)
                            inputs[wire.to_pin_id] = out_val
                comp.evaluate(inputs)

    def _simulate_with_cycles(self):
        """Simulate with cycles - evaluate non-cycle components normally."""
        order = self._partial_order()
        for comp_id in order:
            if comp_id in self.cycle_components:
                continue
            comp = self.components[comp_id]
            if isinstance(comp, InputNode):
                pass
            elif isinstance(comp, ClockGen):
                pass
            else:
                # Collect input values from upstream components not in cycle
                inputs = {}
                for wire_id, wire in self.wires.items():
                    if wire.to_comp_id == comp_id:
                        if wire.from_comp_id in self.cycle_components:
                            continue  # Skip inputs from cycle components
                        from_comp = self.components.get(wire.from_comp_id)
                        if from_comp:
                            out_val = getattr(from_comp, '_output_state', False)
                            inputs[wire.to_pin_id] = out_val
                comp.evaluate(inputs)

    def _partial_order(self):
        """Get a partial order ignoring cycle edges."""
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for cid in self.components:
            in_degree[cid] = 0

        for wire_id, wire in self.wires.items():
            if wire.from_comp_id in self.cycle_components and wire.to_comp_id in self.cycle_components:
                continue
            adj[wire.from_comp_id].append(wire.to_comp_id)
            in_degree[wire.to_comp_id] += 1

        queue = deque()
        for cid in self.components:
            if in_degree[cid] == 0:
                queue.append(cid)

        result = []
        while queue:
            u = queue.popleft()
            result.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        # Add remaining nodes
        for cid in self.components:
            if cid not in result:
                result.append(cid)
        return result

    def clear(self):
        """Clear all components and wires."""
        self.components.clear()
        self.wires.clear()
        self._next_comp_id = 0
        self._next_wire_id = 0
        self.cycle_components.clear()
        self.cycle_wires.clear()
        self.has_cycle = False
        self.topo_order = []

    def to_dict(self):
        """Serialize circuit to a dictionary."""
        return {
            "version": 1,
            "next_comp_id": self._next_comp_id,
            "next_wire_id": self._next_wire_id,
            "components": [comp.to_dict() for comp in self.components.values()],
            "wires": [wire.to_dict() for wire in self.wires.values()],
        }

    @staticmethod
    def from_dict(data):
        """Deserialize circuit from a dictionary."""
        circuit = Circuit()
        circuit._next_comp_id = data.get("next_comp_id", 0)
        circuit._next_wire_id = data.get("next_wire_id", 0)
        for comp_data in data.get("components", []):
            comp = Component.from_dict(comp_data, comp_data["id"])
            circuit.components[comp.comp_id] = comp
        for wire_data in data.get("wires", []):
            wire = Wire(
                wire_data["id"],
                wire_data["from_component"],
                wire_data["from_pin"],
                wire_data["to_component"],
                wire_data["to_pin"],
            )
            circuit.wires[wire.wire_id] = wire
        return circuit

    def get_highest_ids(self):
        """Get the highest component and wire IDs to continue numbering."""
        max_comp = 0
        max_wire = 0
        for cid in self.components:
            try:
                num = int(cid.split("_")[1])
                max_comp = max(max_comp, num)
            except (ValueError, IndexError):
                pass
        for wid in self.wires:
            try:
                num = int(wid.split("_")[1])
                max_wire = max(max_wire, num)
            except (ValueError, IndexError):
                pass
        self._next_comp_id = max_comp + 1
        self._next_wire_id = max_wire + 1
