"""Simulation engine: cycle detection, topological sort, evaluation."""
from collections import defaultdict, deque


def evaluate_gate(gate_type, inputs):
    """Evaluate a gate given its input values list."""
    if gate_type == 'AND':
        return 1 if len(inputs) > 0 and all(v == 1 for v in inputs) else 0
    elif gate_type == 'OR':
        return 1 if any(v == 1 for v in inputs) else 0
    elif gate_type == 'NOT':
        return 0 if len(inputs) > 0 and inputs[0] == 1 else 1
    elif gate_type == 'NAND':
        return 0 if len(inputs) > 0 and all(v == 1 for v in inputs) else 1
    elif gate_type == 'NOR':
        return 0 if any(v == 1 for v in inputs) else 1
    elif gate_type == 'XOR':
        return 1 if sum(inputs) % 2 == 1 else 0
    elif gate_type == 'XNOR':
        return 1 if sum(inputs) % 2 == 0 else 0
    return 0


class SimulationEngine:
    """Manages simulation state, builds dependency graph, evaluates."""

    def __init__(self):
        self.components = {}
        self.wires = []
        self.cycle_components = set()
        self.cycle_wires = set()
        self.high_wires = set()

    def add_component(self, comp):
        self.components[comp.id] = comp

    def remove_component(self, comp_id):
        if comp_id in self.components:
            del self.components[comp_id]
        self.wires = [w for w in self.wires
                      if w.from_comp != comp_id and w.to_comp != comp_id]

    def add_wire(self, wire):
        for existing in self.wires:
            if existing.to_comp == wire.to_comp and existing.to_pin == wire.to_pin:
                self.wires.remove(existing)
                break
        self.wires.append(wire)

    def remove_wire(self, wire_id):
        self.wires = [w for w in self.wires if w.id != wire_id]

    def find_wire_at(self, wx, wy, threshold=10.0):
        best = None
        best_dist = threshold
        for wire in self.wires:
            path = wire.path
            for i in range(len(path) - 1):
                x1, y1 = path[i]
                x2, y2 = path[i + 1]
                dist = self._point_to_segment_dist(wx, wy, x1, y1, x2, y2)
                if dist < best_dist:
                    best_dist = dist
                    best = wire
        return best

    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        nx = x1 + t * dx
        ny = y1 + t * dy
        return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5

    def build_dependency_graph(self):
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for comp_id in self.components:
            in_degree[comp_id] = in_degree.get(comp_id, 0)

        for wire in self.wires:
            src = wire.from_comp
            dst = wire.to_comp
            if src in self.components and dst in self.components:
                adj[src].append(dst)
                in_degree[dst] += 1
        return adj, in_degree

    def detect_cycles(self):
        adj, in_degree = self.build_dependency_graph()
        queue = deque([cid for cid, deg in in_degree.items() if deg == 0])
        sorted_count = 0
        while queue:
            node = queue.popleft()
            sorted_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        cycle_nodes = {cid for cid, deg in in_degree.items() if deg > 0}
        return cycle_nodes

    def get_topological_order(self):
        adj, in_degree = self.build_dependency_graph()
        queue = deque([cid for cid, deg in in_degree.items() if deg == 0])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        cycle_nodes = [cid for cid, deg in in_degree.items() if deg > 0]
        order.extend(cycle_nodes)
        return order

    def step(self, dt):
        """Run one simulation step."""
        # Update clock components
        for comp in self.components.values():
            if comp.comp_type == 'CLOCK':
                freq = comp.properties.get('frequency', 1.0)
                period = 1.0 / max(freq, 0.001)
                comp.clock_timer += dt
                if comp.clock_timer >= period / 2:
                    comp.clock_timer -= period / 2
                    comp.clock_state = 1 - comp.clock_state
                comp.output_values['out'] = comp.clock_state

        # Detect cycles
        self.cycle_components = self.detect_cycles()
        self.cycle_wires.clear()
        for wire in self.wires:
            if wire.from_comp in self.cycle_components or wire.to_comp in self.cycle_components:
                self.cycle_wires.add(wire.id)

        # Get evaluation order
        order = self.get_topological_order()

        # Reset all input values to 0
        for comp in self.components.values():
            for pin_name, _, _ in comp.input_pins:
                comp.input_values[pin_name] = 0
        self.high_wires.clear()

        # Evaluate each component in order, propagating outputs immediately
        for comp_id in order:
            comp = self.components.get(comp_id)
            if comp is None:
                continue
            if comp.comp_type in ('INPUT',):
                pass  # INPUT holds its own state
            elif comp.comp_type == 'CLOCK':
                pass  # Already updated
            elif comp.comp_type == 'OUTPUT':
                comp.output_values['out'] = comp.input_values.get('in0', 0)
            elif comp.comp_type == 'SEVEN_SEGMENT':
                pass  # Display only
            else:
                inputs = [comp.input_values.get(name[0], 0) for name in comp.input_pins]
                result = evaluate_gate(comp.comp_type, inputs)
                for out_pin in comp.output_pins:
                    comp.output_values[out_pin[0]] = result

            # Propagate outputs immediately to downstream inputs
            self._propagate_outputs(comp_id)

        # Build high_wires set for rendering
        for wire in self.wires:
            src_comp = self.components.get(wire.from_comp)
            if src_comp:
                val = src_comp.output_values.get(wire.from_pin, 0)
                if val == 1:
                    self.high_wires.add(wire.id)

    def _propagate_outputs(self, comp_id):
        """Propagate output values from a component to all connected input pins."""
        for wire in self.wires:
            if wire.from_comp == comp_id:
                src_comp = self.components.get(wire.from_comp)
                dst_comp = self.components.get(wire.to_comp)
                if src_comp and dst_comp:
                    pin_names = [p[0] for p in dst_comp.input_pins]
                    if wire.to_pin in pin_names:
                        dst_comp.input_values[wire.to_pin] = src_comp.output_values.get(wire.from_pin, 0)
