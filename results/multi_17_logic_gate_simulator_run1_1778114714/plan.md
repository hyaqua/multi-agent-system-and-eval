# Implementation Plan: Logic Gate Simulator

## 1. File List and Responsibilities

| File               | Purpose |
|--------------------|---------|
| `main.py`          | Entry point: initialize Pygame, set up window, instantiate core objects, run main loop. |
| `config.py`        | Constants: colors (HIGH/LOW, cycle warning, UI), pin radius, grid size, toolbar dimensions, default clock frequency, etc. |
| `canvas.py`        | `Canvas` class: manages infinite pan/zoom, coordinate transforms, dot‑grid background rendering. |
| `components.py`    | `Component` base class and concrete subtypes: `AndGate`, `OrGate`, … , `InputNode`, `OutputNode`, `Clock`, `SevenSegment`. Each defines its pins, shape, and logic evaluation. |
| `circuit.py`       | `Circuit` class: owns all components and wires, simulation update loop (iterative), cycle detection (DFS), topological ordering fallback. |
| `wire.py`          | `Wire` class: stores endpoints (component + pin IDs), computes orthogonal route with corners, draws itself. |
| `toolbar.py`       | `Toolbar` class: draws component palette, handles click selection, sets current placement type. |
| `input_handler.py` | `InputManager`: finite‑state machine for idle/placement/dragging/rubber‑band/wire‑drawing modes, binds mouse/keyboard events. |
| `ui.py`            | Helper functions/classes for property panel (right‑click), save/open dialogs (simple text input using `pygame`), warning overlay. |
| `sample_circuits/` | Folder containing `half_adder.json` and `ripple_counter.json` (pre‑built circuits). |

All files use Python standard library (`json`, `math`, `sys`, `os`, `time`) plus `pygame`.

---

## 2. Architecture

**MVC‑inspired** separation:

- **Model**: `Circuit`, `Component`, `Wire` – circuit state, logic evaluation, cycle graph.
- **View**: `Canvas`, `Toolbar`, rendering of components/wires (each object draws itself with world coordinates transformed by `Canvas`).
- **Controller**: `InputManager` + `Toolbar` – interprets events, drives model changes.

**Interaction flow** (main loop):
1. `InputManager` processes Pygame events, updates its mode and the model (e.g., places component, starts wire, drags selection).
2. `Circuit.simulate()` runs one update step: capture external inputs (`InputNode` toggles, `Clock` phase), iterate all gates until stable (max iterations), set `OutputNode`/pin states, detect cycles.
3. `Canvas` clears the screen, applies pan/zoom transform, draws grid, then calls `circuit.draw()` which asks components/wires to draw.
4. `Toolbar` draws itself on top.
5. UI overlays (coordinates, zoom %, warning) are rendered last without world transform.

**Canvas coordinates**: `Canvas` stores `offset_x, offset_y, zoom`. Mouse screen → world: `world = (mouse - offset) / zoom`. World → screen for drawing: `screen = world * zoom + offset`. Grid lines are drawn in world space every `GRID_SPACING` units.

---

## 3. Implementation Order

1. **Window & Canvas basics**  
   - `main.py` opens a Pygame window.  
   - `Canvas` with dot‑grid, pan (middle mouse or space+left drag), zoom (mouse wheel, centered on cursor).  

2. **Toolbar**  
   - `Toolbar` fixed on the left side, buttons for each component. Clicking sets `InputManager.placement_type`.  

3. **Component base & gate types**  
   - `Component` base: ID, type, position, pins list (each pin with local offset, `is_input`, `label`), current output state rendering.  
   - Implement AND, OR, NOT, NAND, NOR, XOR, XNOR gates with 2 inputs, 1 output. NOT has 1 input.  
   - Drawing: rectangle shape, pin circles, label inside.  

4. **Placement, selection, dragging, rubber‑band**  
   - `InputManager` placement mode: on canvas click, instantiate component, add to `Circuit`.  
   - Selection: left‑click on component toggles selection; rubber‑band rectangle (left drag with no component hit) multi‑selects.  
   - Dragging: holding left button on selected component(s) moves them.  
   - Delete key removes selected components/wires.  

5. **Wires**  
   - Click on an output pin starts wire creation; a preview rubber‑band line follows cursor.  
   - Click on an input pin completes wire (if input is free). Wire stored with endpoints (`(comp_id, pin_name)`).  
   - Orthogonal routing: compute a path of horizontal/vertical segments that snaps to grid corners. Simple A‑to‑B with one bend, extend if obstructed.  
   - Right‑click on a wire deletes it.  

6. **Simulation engine**  
   - `Circuit.simulate()` runs every frame.  
   - Set external inputs: for each `InputNode`, state is set from its toggle; `Clock` computes HIGH/LOW from elapsed time and frequency.  
   - Evaluate all gate components by multiple passes until no change (max e.g. 100 iterations). This handles feedback loops that settle.  
   - After stabilization, propagate final states to pins for drawing.  

7. **Special components**  
   - `OutputNode`: shows HIGH (green) / LOW (grey) with text label.  
   - `Clock`: toggles based on `pygame.time.get_ticks()` and `frequency` (configurable).  
   - `SevenSegment`: 7 input pins (A–G). Output is a pattern drawn as lit/unlit segments using a simple line‑drawing function.  

8. **Cycle detection & warning**  
   - Build directed graph: nodes = components; edges from component’s output to all components connected by wires.  
   - Run DFS: back edge → cycle. Collect all components/wires on that cycle.  
   - If cycle found, highlight those components/wires in red, show warning text overlay.  
   - Simulation continues; if iterative evaluation doesn’t stabilize within limit, mark cycle nodes as unknown/grey.  

9. **Save / Load JSON**  
   - JSON schema: `{"components": [{"id": ..., "type": "...", "x": ..., "y": ..., "config": {...}}], "wires": [{"from": [comp_id, pin_name], "to": [comp_id, pin_name]}]}`.  
   - Ctrl+S: prompt filename via `ui.get_text_input()`, serialize circuit, write file.  
   - Ctrl+O: prompt, load JSON, clear circuit, recreate components and wires.  

10. **Property panel**  
    - Right‑click on component opens a small popup near cursor. For all components: rename (display label). For Clock: also set frequency. Input fields rendered with a simple text cursor, using `pygame.key` for input.  

11. **Corner overlay**  
    - Draw coordinate under mouse (world coords) and zoom % in top‑left or bottom‑right corner (always screen space).  

12. **Sample circuits**  
    - `half_adder.json`: two XOR, one AND, two INPUT, two OUTPUT wired to compute sum & carry.  
    - `ripple_counter.json`: four NOT gates cross‑coupled with AND/OR to form T flip‑flops chained, clock generator connected to first flip‑flop, outputs displayed on seven‑segment? The spec says a 4‑bit ripple counter using clock and gate combinations – we can create a minimal valid counter circuit formed by 4 D‑latch‑like structures (NAND gates with feedback) and a Clock. The cycle detector will flag the feedback loops, but we can store it as a sample despite the warning.

---

## 4. Libraries

- **pygame** – graphics, events, rendering.
- **json** – save/load.
- **math** – distance, transforms.
- **time** – for clock frequency (or use `pygame.time`).
- **tkinter** (optional) – could replace custom text input for dialogs, but we’ll stick with a simple pygame‑based text prompt to avoid extra dependency.

---

## 5. Feature Implementation Details

| Feature | Implementation |
|---------|----------------|
| Infinite scroll/zoom canvas | `Canvas` with `offset`, `zoom`. Pan by delta when middle‑button or space+left drag. Zoom by `zoom *= factor` and adjust offset to keep world point under mouse fixed. Dot‑grid drawn in world space `step = GRID_SPACING * zoom`. |
| Toolbar | Fixed rectangle on left; each button draws icon + label. `InputManager.placement_type` set on click. |
| Placement mode | `InputManager` stores `placement_type`. On left click on canvas, create component instance, add to `circuit.components`. Exit placement mode after placement. |
| Component selection | Hit test: bounding rect of component (pins excluded for selection? We'll treat entire shape). Left click: if no component hit, start rubber band. If component hit, toggle single selection unless shift held, then add to selection. Rubber band: drag rect to select all components whose center falls inside. |
| Dragging selected | In `DRAGGING` mode, offset all selected components by mouse delta. |
| Delete | Remove selected components and any wires attached to them. For selected wires, delete those. |
| Pins rendering | Each component defines pin list: `(local_x, local_y, is_input, label)`. Draw small filled circle (radius 6) at component edge. Inside, color depends on state if simulation is running. |
| Wire drawing | Start wire: click on output pin → store source. Mouse move draws preview line. Click on input pin of different component: create `Wire`. Orthogonal routing: if source and target have different X and Y, choose a single bend point that doesn’t cross components (simple: y‑then‑x if source below target, else x‑then‑y). Snap bend point to grid. Store path as list of points. |
| Wire deletion | Right click on wire: check distance to each wire’s segments, delete nearest. |
| Input pin limit | When connecting, `Circuit.add_wire()` checks that target pin has no existing wire; rejects if busy. |
| Simulation continuous | `Circuit.simulate()` called every frame. Iterative propagation: 1) read `InputNode` and `Clock` states. 2) For each gate, compute output from current pin states. 3) Compare old/new outputs; if any changed, repeat (up to e.g., 100 iterations). 4) Update visual state of pins. |
| INPUT node toggle | `InputNode` has left‑click handler in `InputManager` that flips its `state` (HIGH/LOW). |
| OUTPUT node display | Always shows its input state as colour and label (e.g., “HIGH”). |
| CLOCK generator | `state = HIGH` if `(time_ms // (500/frequency)) % 2 == 0` else LOW. Frequency stored in config, adjustable via property panel. Label displays current frequency. |
| SEVEN SEGMENT DISPLAY | 7 input pins A–G (order: top, upper right, lower right, bottom, lower left, upper left, middle). Computed output is a pattern of lit segments. Draw each segment with two triangles or thick lines. |
| Cycle detection | After stabilizing or during simulation, build directed graph. DFS from each component; if back edge found, mark all components/wires on the cycle. On next frame, those components are outlined in red, wires turn red, and a warning label appears. Simulation can still attempt to evaluate; if cycle prevents settling, those outputs remain unknown (grey). |
| Signal propagation order | The iterative approach guarantees correct propagation regardless of depth. No explicit topological sort needed, but for performance we could pre‑compute evaluation order ignoring cycles. |
| Component output colour | During simulation, pin fill is green if logic HIGH, grey if LOW. Drawn in `Component.draw()`. |
| Save (Ctrl+S) | `event.mod & KMOD_CTRL` and `K_s`. Call `ui.prompt_save()` which shows text field. On enter, serialize circuit to JSON and write to `filename.json`. |
| Load (Ctrl+O) | Similar, prompt for filename, read JSON, reset circuit, rebuild. Validate JSON structure. |
| JSON format | Example: `{"components": [{"id": "c1", "type": "AND", "x": 100, "y": 200, "config": {}}], "wires": [{"from": ["c1", "out"], "to": ["c2", "in0"]}]}`. |
| Property panel | Right‑click on component: `ui.show_properties(component)`. Renders a small rectangle near mouse with text fields “Name” and (if Clock) “Freq (Hz)”. Editing uses `pygame.key` to modify strings. |
| Coordinate / zoom overlay | In top‑right corner, draw `f"zoom: {zoom*100:.0f}%"` and world coords under mouse (if on canvas). Updated each frame. |

---

## 6. Additional Notes

- Use unique IDs for components (e.g., `uuid4()` or incremental integer) to avoid collisions.
- The iterative simulation must handle pure combinational circuits instantly (one pass should suffice), but multiple passes handle feedback. The max iteration limit stops infinite loops.
- Orthogonal wire routing may need to avoid overlapping other components – for simplicity, a single bend point is acceptable; if it collides, add extra bends later.
- The sample circuits JSON files should be stored in a known location (e.g., next to `main.py` or in `sample_circuits/`); the load dialog can show available files.
- No external libraries besides Pygame; all UI (text input, property panel) built with rectangle drawing and font rendering.
