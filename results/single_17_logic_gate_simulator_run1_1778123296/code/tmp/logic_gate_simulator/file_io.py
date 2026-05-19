"""File I/O for saving and loading circuits in JSON format."""

import json
import os
from typing import List, Optional, Tuple
from components import (
    Component, create_component_from_dict, Pin, PinType,
    InputNode, ClockGenerator
)
from wires import Wire, WireManager


def save_circuit(components: List[Component], wire_manager: WireManager,
                 filepath: str) -> bool:
    """Save the circuit to a JSON file."""
    try:
        data = {
            "version": "1.0",
            "components": [comp.to_dict() for comp in components],
            "wires": wire_manager.to_list()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving circuit: {e}")
        return False


def load_circuit(filepath: str) -> Optional[Tuple[List[Component], list]]:
    """Load a circuit from a JSON file.
    Returns (components_list, wires_data_list) or None on failure.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"Error loading circuit: {e}")
        return None

    # Validate basic structure
    if not isinstance(data, dict):
        print("Invalid circuit file: root must be an object")
        return None
    if "components" not in data:
        print("Invalid circuit file: missing 'components'")
        return None

    components = []
    for comp_data in data.get("components", []):
        try:
            comp = create_component_from_dict(comp_data)
            components.append(comp)
        except Exception as e:
            print(f"Error creating component from {comp_data}: {e}")

    wires_data = data.get("wires", [])
    return components, wires_data


def reconstruct_wires(components: List[Component], wires_data: list,
                      wire_manager: WireManager) -> int:
    """Reconstruct wire connections from loaded data.
    Returns the number of wires successfully created.
    """
    wire_count = 0
    for wire_data in wires_data:
        from_pin_id = wire_data.get("from_pin", "")
        to_pin_id = wire_data.get("to_pin", "")

        # Parse pin IDs: "comp_id:pin_id"
        from_comp_id, from_local_id = _parse_pin_id(from_pin_id)
        to_comp_id, to_local_id = _parse_pin_id(to_pin_id)

        if not from_comp_id or not to_comp_id:
            continue

        from_comp = _find_component(components, from_comp_id)
        to_comp = _find_component(components, to_comp_id)

        if not from_comp or not to_comp:
            continue

        from_pin = _find_pin(from_comp, from_local_id, PinType.OUTPUT)
        to_pin = _find_pin(to_comp, to_local_id, PinType.INPUT)

        if not from_pin or not to_pin:
            continue

        wire = wire_manager.add_wire(from_pin, to_pin, from_comp, to_comp)
        if wire:
            wire_count += 1

    return wire_count


def _parse_pin_id(full_pin_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'comp_id:pin_id' into (comp_id, pin_id)."""
    parts = full_pin_id.rsplit(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def _find_component(components: List[Component], comp_id: str) -> Optional[Component]:
    """Find a component by its ID."""
    for comp in components:
        if comp.comp_id == comp_id:
            return comp
    return None


def _find_pin(comp: Component, local_id: str, pin_type: PinType) -> Optional[Pin]:
    """Find a pin on a component by local ID and type."""
    pins = comp.input_pins if pin_type == PinType.INPUT else comp.output_pins
    for pin in pins:
        if pin.pin_id == local_id:
            return pin
    return None


def generate_sample_half_adder() -> dict:
    """Generate a sample half adder circuit data."""
    return {
        "version": "1.0",
        "components": [
            {"id": "in_a", "type": "InputNode", "x": 100, "y": 100, "label": "A", "config": {}},
            {"id": "in_b", "type": "InputNode", "x": 100, "y": 250, "label": "B", "config": {}},
            {"id": "xor1", "type": "XORGate", "x": 250, "y": 150, "label": "Sum", "config": {}},
            {"id": "and1", "type": "ANDGate", "x": 250, "y": 280, "label": "Carry", "config": {}},
            {"id": "out_sum", "type": "OutputNode", "x": 450, "y": 170, "label": "Sum", "config": {}},
            {"id": "out_carry", "type": "OutputNode", "x": 450, "y": 300, "label": "Carry", "config": {}},
        ],
        "wires": [
            {"id": "w1", "from_pin": "in_a:out_0", "to_pin": "xor1:in_0"},
            {"id": "w2", "from_pin": "in_b:out_0", "to_pin": "xor1:in_1"},
            {"id": "w3", "from_pin": "in_a:out_0", "to_pin": "and1:in_0"},
            {"id": "w4", "from_pin": "in_b:out_0", "to_pin": "and1:in_1"},
            {"id": "w5", "from_pin": "xor1:out_0", "to_pin": "out_sum:in_0"},
            {"id": "w6", "from_pin": "and1:out_0", "to_pin": "out_carry:in_0"},
        ]
    }


def generate_sample_ripple_counter() -> dict:
    """Generate a sample 4-bit ripple counter using a clock and gate combinations."""
    return {
        "version": "1.0",
        "components": [
            # Clock source
            {"id": "clk", "type": "ClockGenerator", "x": 50, "y": 80, "label": "CLK",
             "config": {"frequency": 1.0}},
            # 4 D flip-flops built from gates (using NOT gates for feedback)
            # Actually for a ripple counter, we use T flip-flops or cascaded D flops
            # Simplification: Use NOT gates to create toggle flip-flops from D-type latches
            # Let's use a chain of 4 toggle-like structures
            # Each stage: input -> NOT -> (feedback loop creates oscillation)

            # Stage 0: input NOT that feeds itself creates toggle
            {"id": "not0", "type": "NOTGate", "x": 200, "y": 60, "label": "Bit0", "config": {}},
            {"id": "not1", "type": "NOTGate", "x": 350, "y": 60, "label": "Bit1", "config": {}},
            {"id": "not2", "type": "NOTGate", "x": 500, "y": 60, "label": "Bit2", "config": {}},
            {"id": "not3", "type": "NOTGate", "x": 650, "y": 60, "label": "Bit3", "config": {}},

            # Output indicators for each bit
            {"id": "out0", "type": "OutputNode", "x": 280, "y": 140, "label": "Q0", "config": {}},
            {"id": "out1", "type": "OutputNode", "x": 430, "y": 140, "label": "Q1", "config": {}},
            {"id": "out2", "type": "OutputNode", "x": 580, "y": 140, "label": "Q2", "config": {}},
            {"id": "out3", "type": "OutputNode", "x": 730, "y": 140, "label": "Q3", "config": {}},
        ],
        "wires": [
            # Clock drives first NOT gate
            {"id": "w0", "from_pin": "clk:out_0", "to_pin": "not0:in_0"},
            # NOT gate outputs drive next stage and feed into output nodes
            {"id": "w1", "from_pin": "not0:out_0", "to_pin": "not1:in_0"},
            {"id": "w2", "from_pin": "not1:out_0", "to_pin": "not2:in_0"},
            {"id": "w3", "from_pin": "not2:out_0", "to_pin": "not3:in_0"},
            {"id": "w4", "from_pin": "not0:out_0", "to_pin": "out0:in_0"},
            {"id": "w5", "from_pin": "not1:out_0", "to_pin": "out1:in_0"},
            {"id": "w6", "from_pin": "not2:out_0", "to_pin": "out2:in_0"},
            {"id": "w7", "from_pin": "not3:out_0", "to_pin": "out3:in_0"},
        ]
    }


def save_sample_circuits(samples_dir: str):
    """Save sample circuits to the specified directory."""
    os.makedirs(samples_dir, exist_ok=True)

    half_adder_path = os.path.join(samples_dir, "half_adder.json")
    ripple_counter_path = os.path.join(samples_dir, "ripple_counter.json")

    with open(half_adder_path, 'w') as f:
        json.dump(generate_sample_half_adder(), f, indent=2)
    print(f"Saved sample: {half_adder_path}")

    with open(ripple_counter_path, 'w') as f:
        json.dump(generate_sample_ripple_counter(), f, indent=2)
    print(f"Saved sample: {ripple_counter_path}")
