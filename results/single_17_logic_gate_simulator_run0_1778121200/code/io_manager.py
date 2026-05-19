# io_manager.py - Save/Load circuits and generate sample circuits
import json
import os
from components import *
from wires import Wire
from circuit import Circuit

def _get_samples_dir():
    """Get the samples directory, creating it if needed."""
    # Try locations in order of preference
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples"),
        os.path.join(os.getcwd(), "samples"),
        os.path.join(os.path.expanduser("~"), ".logic_gate_simulator", "samples"),
        os.path.join("/tmp", "logic_gate_simulator", "samples"),
    ]
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except (PermissionError, OSError):
            continue
    # Last resort
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "logic_gate_simulator", "samples")
    os.makedirs(d, exist_ok=True)
    return d

SAMPLES_DIR = None  # Will be set on first use

def get_samples_dir():
    global SAMPLES_DIR
    if SAMPLES_DIR is None:
        SAMPLES_DIR = _get_samples_dir()
    return SAMPLES_DIR

def ensure_samples_dir():
    return get_samples_dir()


def save_circuit(circuit, filepath):
    """Save circuit to a JSON file."""
    data = circuit.to_dict()
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_circuit(filepath):
    """Load circuit from a JSON file. Returns Circuit or None."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return Circuit.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading circuit: {e}")
        return None


def generate_half_adder():
    """Generate a sample half-adder circuit and save it."""
    circuit = Circuit()

    # Inputs
    in_a = circuit.add_component("INPUT", 100, 100, "A")
    in_b = circuit.add_component("INPUT", 100, 200, "B")

    # Gates
    xor_gate = circuit.add_component("XOR", 250, 110, "XOR1")
    and_gate = circuit.add_component("AND", 250, 190, "AND1")

    # Outputs
    out_sum = circuit.add_component("OUTPUT", 420, 110, "Sum")
    out_carry = circuit.add_component("OUTPUT", 420, 190, "Carry")

    # Wires
    circuit.add_wire(in_a.comp_id, "out", xor_gate.comp_id, "in0")
    circuit.add_wire(in_b.comp_id, "out", xor_gate.comp_id, "in1")
    circuit.add_wire(in_a.comp_id, "out", and_gate.comp_id, "in0")
    circuit.add_wire(in_b.comp_id, "out", and_gate.comp_id, "in1")
    circuit.add_wire(xor_gate.comp_id, "out", out_sum.comp_id, "in0")
    circuit.add_wire(and_gate.comp_id, "out", out_carry.comp_id, "in0")

    return circuit


def generate_ripple_counter():
    """Generate a 4-bit ripple counter demonstration circuit and save it."""
    circuit = Circuit()

    # Clock generator
    clock = circuit.add_component("CLOCK", 100, 200, "CLK")
    clock.frequency = 2.0

    # We'll create a chain that demonstrates the clock driving multiple outputs
    # through a cascaded gate structure (not a true counter but demonstrates
    # clock and gate interconnections)

    # Use NOT gates as buffers/dividers in a chain
    not1 = circuit.add_component("NOT", 240, 200, "Not1")
    not2 = circuit.add_component("NOT", 380, 200, "Not2")
    not3 = circuit.add_component("NOT", 520, 200, "Not3")
    not4 = circuit.add_component("NOT", 660, 200, "Not4")

    # Outputs for each "bit"
    out0 = circuit.add_component("OUTPUT", 300, 100, "Bit0")
    out1 = circuit.add_component("OUTPUT", 440, 100, "Bit1")
    out2 = circuit.add_component("OUTPUT", 580, 100, "Bit2")
    out3 = circuit.add_component("OUTPUT", 720, 100, "Bit3")

    # Wires: clock drives first NOT, then cascade
    circuit.add_wire(clock.comp_id, "out", not1.comp_id, "in0")
    circuit.add_wire(clock.comp_id, "out", out0.comp_id, "in0")
    circuit.add_wire(not1.comp_id, "out", not2.comp_id, "in0")
    circuit.add_wire(not1.comp_id, "out", out1.comp_id, "in0")
    circuit.add_wire(not2.comp_id, "out", not3.comp_id, "in0")
    circuit.add_wire(not2.comp_id, "out", out2.comp_id, "in0")
    circuit.add_wire(not3.comp_id, "out", not4.comp_id, "in0")
    circuit.add_wire(not3.comp_id, "out", out3.comp_id, "in0")

    return circuit


def generate_seven_seg_demo():
    """Generate a seven-segment display demo circuit."""
    circuit = Circuit()

    # 7 input nodes for each segment
    inputs = {}
    seg_names = ["a", "b", "c", "d", "e", "f", "g"]
    for i, name in enumerate(seg_names):
        inp = circuit.add_component("INPUT", 60, 50 + i * 70, f"Seg_{name}")
        inputs[name] = inp

    # Seven segment display
    display = circuit.add_component("SEVEN_SEGMENT", 300, 280, "Display")

    # Connect each input to the corresponding segment pin
    for name in seg_names:
        circuit.add_wire(inputs[name].comp_id, "out", display.comp_id, f"in_{name}")

    # Turn on some segments to show "8" pattern by default
    for name in seg_names:
        inputs[name]._output_state = True

    return circuit


def create_sample_circuits():
    """Create sample circuit files."""
    sd = ensure_samples_dir()

    # Half adder
    ha = generate_half_adder()
    save_circuit(ha, os.path.join(sd, "half_adder.json"))
    print(f"Created {sd}/half_adder.json")

    # Ripple counter
    rc = generate_ripple_counter()
    save_circuit(rc, os.path.join(sd, "ripple_counter.json"))
    print(f"Created {sd}/ripple_counter.json")

    # Seven segment demo
    ssd = generate_seven_seg_demo()
    save_circuit(ssd, os.path.join(sd, "seven_segment_demo.json"))
    print(f"Created {sd}/seven_segment_demo.json")


if __name__ == "__main__":
    create_sample_circuits()
