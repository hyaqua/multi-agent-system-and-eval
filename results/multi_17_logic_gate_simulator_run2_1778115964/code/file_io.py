"""Save and load circuits as JSON files."""

import json
from pathlib import Path
from typing import Optional

from simulation import Simulator
from components import COMPONENT_TYPES, Component


def save_circuit(simulator: Simulator, filepath: str):
    """Save the current circuit to a JSON file."""
    data = {
        "components": [],
        "wires": [],
    }

    for comp in simulator.components:
        comp_data = {
            "id": comp.id,
            "type": comp.type_name,
            "pos": [comp.position.x, comp.position.y],
            "config": comp.config.copy(),
        }
        data["components"].append(comp_data)

    for wire in simulator.wires:
        wire_data = {
            "from": {
                "component_id": wire.start_pin.parent_component.id,
                "pin_name": wire.start_pin.name,
            },
            "to": {
                "component_id": wire.end_pin.parent_component.id,
                "pin_name": wire.end_pin.name,
            },
        }
        data["wires"].append(wire_data)

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_circuit(simulator: Simulator, filepath: str) -> Optional[str]:
    """Load a circuit from a JSON file. Returns error message or None on success."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return f"File not found: {filepath}"
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    simulator.clear()

    # First pass: create all components
    comp_map: dict[str, Component] = {}
    for comp_data in data.get("components", []):
        comp_type = comp_data["type"]
        if comp_type not in COMPONENT_TYPES:
            return f"Unknown component type: {comp_type}"

        pos = comp_data["pos"]
        comp_id = comp_data["id"]
        cls = COMPONENT_TYPES[comp_type]
        component = cls((pos[0], pos[1]), comp_id=comp_id)
        if "config" in comp_data:
            component.config.update(comp_data["config"])
        simulator.add_component(component)
        comp_map[comp_id] = component

    # Second pass: create all wires
    for wire_data in data.get("wires", []):
        from_info = wire_data["from"]
        to_info = wire_data["to"]

        from_comp = comp_map.get(from_info["component_id"])
        to_comp = comp_map.get(to_info["component_id"])

        if from_comp is None or to_comp is None:
            continue  # Skip orphaned wires

        start_pin = from_comp.get_output_pin_by_name(from_info["pin_name"])
        end_pin = to_comp.get_input_pin_by_name(to_info["pin_name"])

        if start_pin is None or end_pin is None:
            continue

        if end_pin.wire is not None:
            continue  # Already connected

        from wires import Wire
        wire = Wire(start_pin, end_pin)
        simulator.add_wire(wire)

    return None  # Success
