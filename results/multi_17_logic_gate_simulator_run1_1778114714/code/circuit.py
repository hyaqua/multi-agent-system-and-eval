"""Circuit class: manages components, wires, simulation, and cycle detection."""
import json
import pygame
from components import create_component, InputNode, OutputNode, Clock
from wire import Wire


class Circuit:
    """The complete circuit model."""
    def __init__(self):
        self.components = []
        self.wires = []
        self._next_id = 1
        self._wire_next_id = 1
        self.cycle_components = set()
        self.cycle_wires = set()
        self.warning_message = ""

    def get_next_id(self):
        cid = f"c{self._next_id}"
        self._next_id += 1
        return cid

    def get_next_wire_id(self):
        wid = f"w{self._wire_next_id}"
        self._wire_next_id += 1
        return wid

    def add_component(self, comp_type, x, y, config=None):
        """Create and add a component."""
        cid = self.get_next_id()
        comp = create_component(comp_type, cid, x, y, config)
        self.components.append(comp)
        return comp

    def remove_component(self, comp):
        """Remove a component and all its connected wires."""
        # Remove wires connected to this component
        wires_to_remove = []
        for w in self.wires:
            if w.from_comp_id == comp.id or w.to_comp_id == comp.id:
                wires_to_remove.append(w)
        for w in wires_to_remove:
            self.wires.remove(w)
        self.components.remove(comp)

    def remove_wire(self, wire):
        """Remove a wire."""
        if wire in self.wires:
            self.wires.remove(wire)

    def find_component_at(self, wx, wy):
        """Return the topmost component at world position, or None."""
        for comp in reversed(self.components):
            if comp.contains_point(wx, wy):
                return comp
        return None

    def find_pin_at(self, wx, wy):
        """Return (component, pin) for a pin at world position, or (None, None)."""
        for comp in reversed(self.components):
            pin = comp.get_pin_at_world(wx, wy)
            if pin:
                return (comp, pin)
        return (None, None)

    def find_wire_at(self, wx, wy, max_dist=8):
        """Return the nearest wire within max_dist world units."""
        best_wire = None
        best_dist = max_dist
        for w in self.wires:
            d = w.distance_to_point(wx, wy)
            if d < best_dist:
                best_dist = d
                best_wire = w
        return best_wire

    def add_wire(self, from_comp, from_pin, to_comp, to_pin):
        """Add a wire between two pins. Returns Wire or None if invalid."""
        # Validate
        if from_comp.id == to_comp.id:
            return None  # Can't connect to same component
        if from_pin.is_input:
            return None  # Source must be output
        if not to_pin.is_input:
            return None  # Target must be input

        # Check if target input already has a wire
        for w in self.wires:
            if w.to_comp_id == to_comp.id and w.to_pin_name == to_pin.name:
                return None  # Input already connected

        wid = self.get_next_wire_id()
        wire = Wire(wid, from_comp, from_pin, to_comp, to_pin)
        wire.compute_path(self.components)
        self.wires.append(wire)
        return wire

    def get_input_state(self, comp, pin_name):
        """Get the state of an input pin by following wires backward."""
        # Find wire that connects to this input pin
        for w in self.wires:
            if w.to_comp_id == comp.id and w.to_pin_name == pin_name:
                # Find source component
                for c in self.components:
                    if c.id == w.from_comp_id:
                        for p in c.pins:
                            if p.name == w.from_pin_name and not p.is_input:
                                return p.state
        return False  # Floating input = LOW

    def simulate(self, time_ms):
        """Run one simulation step."""
        # Reset all pin states
        for comp in self.components:
            for pin in comp.pins:
                pin.state = False

        # Update external inputs
        for comp in self.components:
            if isinstance(comp, InputNode):
                comp.pins[0].state = comp.state
            elif isinstance(comp, Clock):
                comp.update_state(time_ms)

        # Iterative evaluation
        changed = True
        iterations = 0
        while changed and iterations < 100:
            changed = False
            for comp in self.components:
                # Skip external input nodes and clocks (they don't compute from inputs)
                if isinstance(comp, (InputNode, Clock)):
                    continue

                # Gather input values
                input_values = {}
                for pin in comp.pins:
                    if pin.is_input:
                        input_values[pin.name] = self.get_input_state(comp, pin.name)

                # Compute output
                output = comp.evaluate(input_values)

                # Set output pins
                for pin in comp.pins:
                    if not pin.is_input:
                        if pin.state != output:
                            pin.state = output
                            changed = True

            iterations += 1

        # Detect cycles
        self.detect_cycles()

    def detect_cycles(self):
        """Detect combinational cycles using DFS."""
        self.cycle_components = set()
        self.cycle_wires = set()
        self.warning_message = ""

        # Build adjacency: comp -> list of comps that receive its output
        adj = {c.id: [] for c in self.components}
        wire_map = {}  # (from_id, to_id) -> wire

        for w in self.wires:
            if w.from_comp_id in adj and w.to_comp_id in adj:
                adj[w.from_comp_id].append(w.to_comp_id)
                wire_map[(w.from_comp_id, w.to_comp_id)] = w

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {c.id: WHITE for c in self.components}
        parent = {}

        def dfs(u):
            color[u] = GRAY
            for v in adj.get(u, []):
                if color.get(v) == GRAY:
                    # Back edge: cycle found
                    # Trace back to find cycle members
                    cycle = set()
                    cycle.add(u)
                    cycle.add(v)
                    # Walk back from u to v
                    curr = u
                    while curr != v:
                        curr = parent.get(curr)
                        if curr is None:
                            break
                        cycle.add(curr)
                    # Add wires on this cycle
                    comp_list = list(cycle)
                    for i in range(len(comp_list)):
                        a = comp_list[i]
                        b = comp_list[(i + 1) % len(comp_list)]
                        # Check adjacency in original direction
                        if b in adj.get(a, []):
                            self.cycle_components.add(a)
                            self.cycle_components.add(b)
                            key = (a, b)
                            if key in wire_map:
                                self.cycle_wires.add(wire_map[key])
                        elif a in adj.get(b, []):
                            self.cycle_components.add(a)
                            self.cycle_components.add(b)
                            key = (b, a)
                            if key in wire_map:
                                self.cycle_wires.add(wire_map[key])
                    return True
                elif color.get(v) == WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
            color[u] = BLACK
            return False

        for c in self.components:
            if color[c.id] == WHITE:
                dfs(c)

        if self.cycle_components:
            self.warning_message = "⚠ Cycle detected! Oscillating signals may not stabilize."

    def draw(self, screen, canvas, font, selected_ids=None):
        """Draw all wires and components."""
        selected_ids = selected_ids or set()

        # Draw wires
        for w in self.wires:
            in_cycle = w in self.cycle_wires
            w.draw(screen, canvas, cycle=in_cycle)

        # Draw components
        for comp in self.components:
            selected = comp.id in selected_ids
            comp.draw(screen, canvas, font, selected=selected, cycle_members=self.cycle_components)

    def to_dict(self):
        """Serialize to dict."""
        return {
            "components": [
                {
                    "id": c.id,
                    "type": c.type,
                    "x": c.x,
                    "y": c.y,
                    "config": c.config,
                    "label": c.label,
                }
                for c in self.components
            ],
            "wires": [w.to_dict() for w in self.wires],
        }

    def from_dict(self, data):
        """Load from dict, replacing current circuit."""
        self.components.clear()
        self.wires.clear()
        self.cycle_components.clear()
        self.cycle_wires.clear()
        self.warning_message = ""

        # Rebuild components
        for cd in data.get("components", []):
            cid = cd["id"]
            ctype = cd["type"]
            cx = cd["x"]
            cy = cd["y"]
            config = cd.get("config", {})
            label = cd.get("label", ctype)

            comp = create_component(ctype, cid, cx, cy, config)
            comp.label = label
            if isinstance(comp, InputNode):
                comp.state = config.get("state", False)
            self.components.append(comp)

        # Update next IDs
        max_id = 0
        for c in self.components:
            if c.id.startswith("c"):
                try:
                    n = int(c.id[1:])
                    max_id = max(max_id, n)
                except ValueError:
                    pass
        self._next_id = max_id + 1

        max_wid = 0
        for wd in data.get("wires", []):
            wid = wd.get("id", "")
            if wid.startswith("w"):
                try:
                    n = int(wid[1:])
                    max_wid = max(max_wid, n)
                except ValueError:
                    pass
        self._wire_next_id = max_wid + 1

        # Rebuild wires
        for wd in data.get("wires", []):
            try:
                wire = Wire.from_dict(wd, self.get_next_wire_id(), self.components)
                wire.compute_path(self.components)
                self.wires.append(wire)
            except (ValueError, KeyError) as e:
                print(f"Warning: Could not load wire: {e}")

    def save_to_file(self, filepath):
        """Save circuit to JSON file."""
        data = self.to_dict()
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_from_file(self, filepath):
        """Load circuit from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.from_dict(data)
