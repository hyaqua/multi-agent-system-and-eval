"""Save and load circuits in JSON format."""
import json
from models import Component, Wire


def save_circuit(components, wires, filepath):
    """Save a circuit to a JSON file."""
    data = {
        'version': '1.0',
        'components': [c.to_dict() for c in components.values()],
        'wires': [w.to_dict() for w in wires],
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_circuit(filepath):
    """Load a circuit from a JSON file.
    Returns (components_dict, wires_list) or raises on error."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    if data.get('version') != '1.0':
        raise ValueError(f"Unsupported file version: {data.get('version')}")

    components = {}
    for cd in data.get('components', []):
        comp = Component.from_dict(cd)
        components[comp.id] = comp

    wires = []
    for wd in data.get('wires', []):
        wire = Wire.from_dict(wd)
        wires.append(wire)

    return components, wires
