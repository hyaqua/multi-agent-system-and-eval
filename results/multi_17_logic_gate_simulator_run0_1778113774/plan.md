# Implementation Plan: Logic Gate Simulator

## Files and Their Purposes

| File | Purpose |
|------|---------|
| `main.py` | Pygame window creation, main loop, event dispatching, orchestration of all modules. |
| `canvas.py` | Infinite pan/zoom camera, world/screen coordinate conversion, dot‑grid background rendering. |
| `components.py` | Base component class, specific gate logic (AND, OR, NOT, NAND, NOR, XOR, XNOR), INPUT node, OUTPUT node, CLOCK generator, SEVEN SEGMENT display. Drawing, pin definitions, state colours. |
| `wires.py` | Wire class storing connection endpoints and orthogonal routing points. Drawing of wires, deletion on right‑click. |
| `circuit.py` | Circuit graph (components + wires), topological evaluation, cycle detection, signal propagation, highlight logic. |
| `ui.py` | Toolbar rendering and hit detection, placement mode, selection (single and rubber band), dragging, properties panel (right‑click component), file‑save/load prompts, coordinate/zoom overlay. |
| `file_io.py` | JSON serialisation/deserialisation of circuit data. |
| `constants.py` | Colours, grid spacing, pin radius, default zoom limits, frequencies, etc. |
| `sample_circuits/` | Folder containing `half_adder.json` and `ripple_counter.json`. |

## Architecture Overview

- **MVC‑like separation:** `circuit.py` holds the model (components, wires, simulation state). `canvas.py` and `ui.py` handle the view and user input. `main.py` ties everything together.
- **Camera:** A `Camera` class stores world offset and zoom factor. All screen↔world coordinate transformations go through it. Panning (middle‑mouse drag or Space+left‑drag) and zooming (scroll wheel centred on cursor) update the camera.
- **Component base class:** Defines `rect` (bounding box at grid position), `draw()`, `get_pins()`, `evaluate()`. Each subclass implements its logic. Pins are small circles; input circles on left/top, outputs on right/bottom. Each pin has an ID (e.g., `"in0"`, `"out"`).
- **Wiring:** Clicking an output pin starts a wire. Moving the mouse shows a preview rubber band; clicking an input pin completes the connection. Wire routing: simple orthogonal path with one corner, stored as a list of screen points (snapped to grid).
- **Simulation engine:** The circuit builds a dependency graph (edge from driver component to driven component). Each frame, it topologically sorts the components; those not involved in a cycle are evaluated in order. If a cycle is detected, the involved components and wires are coloured red and a warning message is displayed; simulation continues for acyclic parts.
- **File I/O:** JSON format stores component type, ID, position, optional name, clock frequency, and wire connections (from/to component ID + pin ID). File dialogs use `tkinter.filedialog` for native OS prompts.
- **Toolbar:** Fixed panel on the left showing buttons for each component. Clicking a button enters “placement mode”; clicking the canvas creates a component snapped to the nearest grid point.
- **Selection & deletion:** Left‑click on component selects it; rubber band selection selects multiple. Dragging moves all selected components (grid‑snapped). Delete key removes selected components and clears any connected wires.
- **Properties:** Right‑click a component shows a small floating panel to rename or, for a CLOCK, adjust its frequency in Hz.

## Implementation Order

1. **Core window and camera** (`main.py`, `canvas.py`, `constants.py`)  
   - Set up Pygame window, event loop, basic quit.  
   - Implement `Camera` with pan (middle‑mouse drag, Space+left‑drag) and zoom (scroll wheel).  
   - Draw dot‑grid background scaled to current zoom, infinite pan.

2. **Component system** (`components.py`)  
   - Define base component class with position, bounding rect, pins, drawing logic.  
   - Implement all gates (AND, OR, NOT, …) with correct pin counts and boolean evaluation.  
   - Render components with state colouring (green = HIGH, grey = LOW).  
   - Add INPUT/OUTPUT nodes, CLOCK generator, SEVEN‑SEGMENT display later.

3. **Toolbar and placement** (`ui.py`)  
   - Draw toolbar with buttons for each component type.  
   - Enter placement mode, show preview under cursor, snap to grid on left‑click.  
   - Assign unique IDs to new components.

4. **Selection and dragging** (`ui.py`)  
   - Left‑click on component selects it (single selection).  
   - Rubber band selection (multiple) with visual rectangle.  
   - Drag selected components, snapping to grid, updating wire endpoints.

5. **Wiring** (`wires.py`, `ui.py`)  
   - Detect clicks on output pins, start drawing temp wire.  
   - Validate connection on input‑pin click (one connection per input).  
   - Create wire with orthogonal route stored.  
   - Draw wires with colour based on current state (green/grey).  
   - Right‑click on wire deletes it.

6. **Simulation engine** (`circuit.py`)  
   - Maintain component and wire lists.  
   - Build dependency graph: for each wire, add edge from source component to destination component.  
   - Topological sort each frame; evaluate components in order.  
   - Update output states and wire colours.

7. **Cycle detection** (`circuit.py`)  
   - Run Kahn’s algorithm on the dependency graph. If not all nodes processed, cycle exists.  
   - Identify cycle nodes and associated wires; render them in red.  
   - Show warning message on canvas.

8. **Special components**  
   - **INPUT node:** output pin, click to toggle HIGH/LOW.  
   - **OUTPUT node:** input pin, display state with distinct colour/label.  
   - **CLOCK generator:** no inputs, one output. Use `pygame.time.get_ticks()` to toggle every half‑period based on configurable frequency.  
   - **SEVEN‑SEGMENT DISPLAY:** 7 input pins (a‑g). Draw segments lit based on input states.

9. **Saving & loading** (`file_io.py`, `ui.py`)  
   - Implement JSON serialisation/deserialisation of all component/wire data.  
   - Use `tkinter.filedialog` for file save/open.  
   - Add `Ctrl+S` and `Ctrl+O` hotkeys.

10. **Properties panel** (`ui.py`)  
    - On right‑click, show a small panel near the component with editable name field and frequency input (if clock).  
    - Implement simple text input handling within Pygame (or use `tkinter.simpledialog`). Use Pygame’s keyboard events for entering text.

11. **Coordinate & zoom overlay** (`ui.py`)  
    - Draw semi‑transparent text in lower‑right corner showing current world coordinates of the mouse and zoom percentage.

12. **Sample circuits** (`sample_circuits/`)  
    - Create `half_adder.json` and `ripple_counter.json` using the defined JSON format.

## Libraries

- `pygame` – graphics, events, timing.
- Standard library: `json`, `os`, `tkinter` (for file dialogs), `math`. No external dependencies beyond Pygame.

## Feature Implementation Details

- **Infinite canvas & dot grid:**  
  Camera stores `offset_x`, `offset_y`, `zoom`. Dot grid is drawn as a series of lines spaced by `GRID_SPACING * zoom`. Only dots within the screen view are drawn to maintain performance.

- **Pan / zoom:**  
  Middle‑mouse drag: change offset by mouse delta / zoom. Space+left‑drag: same. Scroll wheel: zoom in/out centred on cursor position by adjusting offset so world point under cursor stays fixed.

- **Placement & snapping:**  
  World position of mouse snapped to nearest multiple of `GRID_SPACING`. New component placed at that location.

- **Wire routing:**  
  When connecting, calculate a path: from output pin, go horizontally/vertically to a “break” point, then go to the input pin. The intermediate points ensure orthogonal routing. Wires snap to grid.

- **One wire per input:**  
  `input_pin.connected_wire` is a single reference. On attempt to add second wire, show error or simply ignore. Output pins maintain a list of wires.

- **Simulation update each frame:**  
  Topological order recomputed only when wiring changes (add/delete wire) for efficiency, otherwise reused. During evaluation, for each component in order, fetch input values from connected driver’s output state, compute output, store. Wire colours updated accordingly.

- **Signal propagation depth:**  
  Topological sort naturally handles arbitrary cascading depths because evaluation order respects dependencies.

- **Component visual states:**  
  Each component’s body is filled with green if its output is HIGH, grey if LOW. INPUT nodes toggle colour on click.

- **Toggle INPUT node:**  
  Click on the input node (when not in placement/drag mode) flips its stored state. Output is immediately updated.

- **CLOCK generator frequency:**  
  Property stores a `period_ms` (1000/frequency). Use accumulation of delta time to decide when to toggle. Timer resets after toggle.

- **SEVEN‑SEGMENT mapping:**  
  Input pin order: a (top), b (upper right), c (lower right), d (bottom), e (lower left), f (upper left), g (middle). Drawing uses a predefined pattern of rectangles/lines.

- **Cycle warning:**  
  Highlighting: set a flag on involved components and wires; their draw methods use red colour. A text label “CYCLE DETECTED” appears at top‑center of canvas.

- **Saving / Loading:**  
  JSON schema:
  ```json
  {
    "components": [
      {
        "id": "comp_1",
        "type": "AND",
        "pos": [400, 300],
        "name": "",
        "frequency": null
      }
    ],
    "wires": [
      {
        "from": { "component": "comp_1", "pin": "out" },
        "to":   { "component": "comp_2", "pin": "in0" }
      }
    ]
  }
  ```
  On loading, components are recreated, wires reconnected, simulation restarted.

- **File dialogue:**  
  `tkinter.filedialog.asksaveasfilename` and `askopenfilename` provide native dialogs. On Pygame focus loss/regain, the main loop is paused briefly.

- **Properties panel:**  
  Right‑click pops a small rectangle with a text input (for name) and, if clock, a number input for frequency. Text input is handled by capturing `KEYDOWN` events, building a string, and rendering it.

- **Coordinate overlay:**  
  Every frame, get mouse world pos via camera, display as `X: <world_x> Y: <world_y>` along with `Zoom: <int(zoom*100)>%`.

---