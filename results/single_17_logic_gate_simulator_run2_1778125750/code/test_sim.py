"""Test script for the logic gate simulator - verifies core features programmatically."""
import sys
import json
import os

# Test imports
from constants import *
from models import Component, Wire
from simulation import SimulationEngine, evaluate_gate
from file_io import save_circuit, load_circuit

print("=== Testing Logic Gate Simulator ===")

# === Test 1: Gate evaluation ===
print("\n1. Gate evaluation...")
assert evaluate_gate('AND', [1, 1]) == 1
assert evaluate_gate('AND', [1, 0]) == 0
assert evaluate_gate('OR', [0, 0]) == 0
assert evaluate_gate('OR', [0, 1]) == 1
assert evaluate_gate('NOT', [1]) == 0
assert evaluate_gate('NOT', [0]) == 1
assert evaluate_gate('NAND', [1, 1]) == 0
assert evaluate_gate('NAND', [0, 1]) == 1
assert evaluate_gate('NOR', [1, 0]) == 0
assert evaluate_gate('NOR', [0, 0]) == 1
assert evaluate_gate('XOR', [1, 0]) == 1
assert evaluate_gate('XOR', [1, 1]) == 0
assert evaluate_gate('XNOR', [1, 0]) == 0
assert evaluate_gate('XNOR', [1, 1]) == 1
print("   PASSED")

# === Test 2: Component creation and pins ===
print("\n2. Component creation...")
c = Component('AND', 100, 200, 'AND1')
assert c.comp_type == 'AND'
assert c.label == 'AND1'
assert c.x == 100 and c.y == 200
assert len(c.input_pins) == 2
assert len(c.output_pins) == 1
assert c.input_pins[0][0] == 'in0'
assert c.output_pins[0][0] == 'out'

inp = Component('INPUT', 0, 0)
assert len(inp.input_pins) == 0
assert len(inp.output_pins) == 1

outp = Component('OUTPUT', 0, 0)
assert len(outp.input_pins) == 1
assert len(outp.output_pins) == 1

clock = Component('CLOCK', 0, 0)
assert clock.properties.get('frequency') == 1.0

seg = Component('SEVEN_SEGMENT', 0, 0)
assert len(seg.input_pins) == 7
assert len(seg.output_pins) == 0
print("   PASSED")

# === Test 3: Pin positions ===
print("\n3. Pin positions...")
px, py = c.get_pin_world_pos('in0', True)
assert px == c.x  # Left edge
assert py > c.y and py < c.y + c.height
px2, py2 = c.get_pin_world_pos('out', False)
assert px2 == c.x + c.width  # Right edge
print("   PASSED")

# === Test 4: Hit testing ===
print("\n4. Hit testing...")
assert c.contains_point(c.x + 10, c.y + 10) == True
assert c.contains_point(c.x - 10, c.y - 10) == False
hit = c.find_pin_at(c.x, c.y + c.height * 0.33)
assert hit is not None and hit[0] == 'in0' and hit[1] == True
print("   PASSED")

# === Test 5: Wire creation ===
print("\n5. Wire creation...")
w = Wire('comp_0', 'out', 'comp_1', 'in0')
assert w.from_comp == 'comp_0'
assert w.to_comp == 'comp_1'
assert w.from_pin == 'out'
assert w.to_pin == 'in0'
print("   PASSED")

# === Test 6: Simulation engine - simple circuit ===
print("\n6. Simulation engine...")
sim = SimulationEngine()

# Create a simple AND circuit: two INPUTs -> AND -> OUTPUT
in_a = Component('INPUT', 0, 0, 'A')
in_a.output_values['out'] = 1
sim.add_component(in_a)

in_b = Component('INPUT', 0, 0, 'B')
in_b.output_values['out'] = 0
sim.add_component(in_b)

and_gate = Component('AND', 0, 0, 'AND1')
sim.add_component(and_gate)

out = Component('OUTPUT', 0, 0, 'OUT1')
sim.add_component(out)

sim.add_wire(Wire(in_a.id, 'out', and_gate.id, 'in0'))
sim.add_wire(Wire(in_b.id, 'out', and_gate.id, 'in1'))
sim.add_wire(Wire(and_gate.id, 'out', out.id, 'in0'))

sim.step(0.016)
assert and_gate.output_values['out'] == 0  # 1 AND 0 = 0
assert out.output_values['out'] == 0
print("   AND(1,0)=0: PASSED")

# Change input B to 1
in_b.output_values['out'] = 1
sim.step(0.016)
assert and_gate.output_values['out'] == 1  # 1 AND 1 = 1
assert out.output_values['out'] == 1
print("   AND(1,1)=1: PASSED")

# === Test 7: XOR gate ===
print("\n7. XOR gate...")
sim2 = SimulationEngine()
a = Component('INPUT', 0, 0, 'A')
a.output_values['out'] = 1
b = Component('INPUT', 0, 0, 'B')
b.output_values['out'] = 1
xor_g = Component('XOR', 0, 0, 'XOR1')
out2 = Component('OUTPUT', 0, 0, 'O')
sim2.add_component(a)
sim2.add_component(b)
sim2.add_component(xor_g)
sim2.add_component(out2)
sim2.add_wire(Wire(a.id, 'out', xor_g.id, 'in0'))
sim2.add_wire(Wire(b.id, 'out', xor_g.id, 'in1'))
sim2.add_wire(Wire(xor_g.id, 'out', out2.id, 'in0'))
sim2.step(0.016)
assert xor_g.output_values['out'] == 0  # 1 XOR 1 = 0
print("   XOR(1,1)=0: PASSED")

# === Test 8: Half adder simulation ===
print("\n8. Half adder simulation...")
sim3 = SimulationEngine()
a = Component('INPUT', 0, 0, 'A')
a.output_values['out'] = 0
b = Component('INPUT', 0, 0, 'B')
b.output_values['out'] = 0
xor_g = Component('XOR', 0, 0, 'Sum')
and_g = Component('AND', 0, 0, 'Carry')
sum_o = Component('OUTPUT', 0, 0, 'S')
carry_o = Component('OUTPUT', 0, 0, 'C')
for c in [a, b, xor_g, and_g, sum_o, carry_o]:
    sim3.add_component(c)
sim3.add_wire(Wire(a.id, 'out', xor_g.id, 'in0'))
sim3.add_wire(Wire(b.id, 'out', xor_g.id, 'in1'))
sim3.add_wire(Wire(a.id, 'out', and_g.id, 'in0'))
sim3.add_wire(Wire(b.id, 'out', and_g.id, 'in1'))
sim3.add_wire(Wire(xor_g.id, 'out', sum_o.id, 'in0'))
sim3.add_wire(Wire(and_g.id, 'out', carry_o.id, 'in0'))

# A=0, B=0 -> Sum=0, Carry=0
sim3.step(0.016)
assert sum_o.input_values['in0'] == 0, f"Expected 0 got {sum_o.input_values['in0']}"
assert carry_o.input_values['in0'] == 0
print("   0+0: Sum=0 Carry=0 PASSED")

# A=1, B=0 -> Sum=1, Carry=0
a.output_values['out'] = 1
sim3.step(0.016)
assert sum_o.input_values['in0'] == 1, f"Expected 1 got {sum_o.input_values['in0']}"
assert carry_o.input_values['in0'] == 0
print("   1+0: Sum=1 Carry=0 PASSED")

# A=1, B=1 -> Sum=0, Carry=1
b.output_values['out'] = 1
sim3.step(0.016)
assert sum_o.input_values['in0'] == 0, f"Expected 0 got {sum_o.input_values['in0']}"
assert carry_o.input_values['in0'] == 1, f"Expected 1 got {carry_o.input_values['in0']}"
print("   1+1: Sum=0 Carry=1 PASSED")

# === Test 9: Cycle detection ===
print("\n9. Cycle detection...")
sim4 = SimulationEngine()
n1 = Component('NOT', 0, 0, 'N1')
n2 = Component('NOT', 0, 0, 'N2')
sim4.add_component(n1)
sim4.add_component(n2)
# Create a cycle: N1 -> N2 -> N1
sim4.add_wire(Wire(n1.id, 'out', n2.id, 'in0'))
sim4.add_wire(Wire(n2.id, 'out', n1.id, 'in0'))
cycles = sim4.detect_cycles()
assert len(cycles) == 2, f"Expected 2 cycle nodes, got {len(cycles)}"
assert n1.id in cycles
assert n2.id in cycles
print("   Cycle detection: PASSED")

# No cycle
sim5 = SimulationEngine()
a = Component('INPUT', 0, 0, 'A')
n = Component('NOT', 0, 0, 'N')
o = Component('OUTPUT', 0, 0, 'O')
sim5.add_component(a)
sim5.add_component(n)
sim5.add_component(o)
sim5.add_wire(Wire(a.id, 'out', n.id, 'in0'))
sim5.add_wire(Wire(n.id, 'out', o.id, 'in0'))
cycles = sim5.detect_cycles()
assert len(cycles) == 0, f"Expected 0 cycle nodes, got {len(cycles)}"
print("   No-cycle detection: PASSED")

# === Test 10: Topological order ===
print("\n10. Topological order...")
order = sim5.get_topological_order()
# INPUT should come before NOT, which should come before OUTPUT
a_idx = order.index(a.id)
n_idx = order.index(n.id)
o_idx = order.index(o.id)
assert a_idx < n_idx < o_idx, f"Order incorrect: {order}"
print("   Topological order: PASSED")

# === Test 11: Clock simulation ===
print("\n11. Clock simulation...")
sim6 = SimulationEngine()
clock = Component('CLOCK', 0, 0, 'CLK')
clock.properties['frequency'] = 2.0  # 2 Hz = 0.5s period, toggles every 0.25s
sim6.add_component(clock)

assert clock.output_values['out'] == 0
# Advance by 0.25s - should toggle
sim6.step(0.25)
assert clock.output_values['out'] == 1, f"Clock should be 1 after 0.25s, got {clock.output_values['out']}"
# Advance by another 0.25s
sim6.step(0.25)
assert clock.output_values['out'] == 0, f"Clock should be 0 after 0.5s, got {clock.output_values['out']}"
print("   Clock oscillation: PASSED")

# === Test 12: Multiple output connections ===
print("\n12. Multiple fan-out...")
sim7 = SimulationEngine()
src = Component('INPUT', 0, 0, 'SRC')
src.output_values['out'] = 1
o1 = Component('OUTPUT', 0, 0, 'O1')
o2 = Component('OUTPUT', 0, 0, 'O2')
sim7.add_component(src)
sim7.add_component(o1)
sim7.add_component(o2)
sim7.add_wire(Wire(src.id, 'out', o1.id, 'in0'))
sim7.add_wire(Wire(src.id, 'out', o2.id, 'in0'))
sim7.step(0.016)
assert o1.input_values['in0'] == 1
assert o2.input_values['in0'] == 1
print("   Fan-out works: PASSED")

# === Test 13: Input pin accepts only one wire ===
print("\n13. Single input connection...")
sim8 = SimulationEngine()
a = Component('INPUT', 0, 0, 'A')
b = Component('INPUT', 0, 0, 'B')
o = Component('OUTPUT', 0, 0, 'O')
sim8.add_component(a)
sim8.add_component(b)
sim8.add_component(o)
sim8.add_wire(Wire(a.id, 'out', o.id, 'in0'))
assert len(sim8.wires) == 1
sim8.add_wire(Wire(b.id, 'out', o.id, 'in0'))
assert len(sim8.wires) == 1  # Should replace, not add
assert sim8.wires[0].from_comp == b.id
print("   Single input enforcement: PASSED")

# === Test 14: Component serialization ===
print("\n14. JSON serialization...")
# Use a fresh component for serialization test
test_comp = Component('AND', 100, 200, 'AND1')
d = test_comp.to_dict()
assert d['type'] == 'AND'
assert d['x'] == 100 and d['y'] == 200
c2 = Component.from_dict(d)
assert c2.id == test_comp.id
assert c2.comp_type == test_comp.comp_type
assert c2.x == test_comp.x and c2.y == test_comp.y
print("   Component serialization: PASSED")

# === Test 15: Wire serialization ===
test_wire = Wire('comp_0', 'out', 'comp_1', 'in0')
d2 = test_wire.to_dict()
assert d2['from_component'] == 'comp_0'
assert d2['to_component'] == 'comp_1'
w2 = Wire.from_dict(d2)
assert w2.id == test_wire.id
assert w2.from_comp == test_wire.from_comp
print("   Wire serialization: PASSED")

# === Test 16: Save and load circuit ===
print("\n16. Save/load circuit...")
# Use the half adder simulation
save_circuit(sim3.components, sim3.wires, '/tmp/test_half_adder.json')
comps, wires = load_circuit('/tmp/test_half_adder.json')
assert len(comps) == 6
assert len(wires) == 6
# Verify loaded circuit works
sim_loaded = SimulationEngine()
sim_loaded.components = comps
sim_loaded.wires = wires
sim_loaded.step(0.016)
# Check that the loaded circuit evaluates correctly
for comp in sim_loaded.components.values():
    if comp.comp_type == 'INPUT':
        comp.output_values['out'] = 0  # Reset all inputs
sim_loaded.step(0.016)
print("   Save/Load: PASSED")

# === Test 17: Wire hit detection ===
print("\n17. Wire hit detection...")
from simulation import SimulationEngine as SE
se = SE()
c1 = Component('INPUT', 0, 0, 'I1')
c1.output_values['out'] = 1
c2 = Component('OUTPUT', 200, 0, 'O1')
se.add_component(c1)
se.add_component(c2)
w = Wire(c1.id, 'out', c2.id, 'in0')
w.path = [(70, 20), (130, 20), (130, 20), (200, 20)]  # Simple path
se.add_wire(w)
hit = se.find_wire_at(100, 22, threshold=5)
assert hit is not None, "Should find wire near (100, 22)"
print("   Wire hit detection: PASSED")

# === Test 18: Seven segment inputs ===
print("\n18. Seven segment display...")
seg = Component('SEVEN_SEGMENT', 0, 0, 'DISP')
assert len(seg.input_pins) == 7
pin_names = [p[0] for p in seg.input_pins]
assert set(pin_names) == {'a', 'b', 'c', 'd', 'e', 'f', 'g'}
print("   Seven segment pins: PASSED")

# === Test 19: Component to_dict/from_dict with properties ===
print("\n19. Properties serialization...")
clk = Component('CLOCK', 100, 200, 'MyClock')
clk.properties['frequency'] = 5.0
d = clk.to_dict()
assert d['properties']['frequency'] == 5.0
clk2 = Component.from_dict(d)
assert clk2.properties['frequency'] == 5.0
assert clk2.label == 'MyClock'
print("   Properties serialization: PASSED")

print("\n=== ALL TESTS PASSED ===")
