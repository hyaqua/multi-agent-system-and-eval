# Logic Gate Simulator – Revised Implementation Plan (REVISE v2)

**Status after test run:**  
The application fails to start because `sys.dont_write_bytecode = True` is missing from all modules except `main.py`. This causes `PermissionError` when the interpreter tries to create `__pycache__`. Additionally, pin labels are invisible, sample circuit files are absent, the *Delete* key is not suppressed when the properties panel is open, and several linter warnings remain. This revised plan **prioritises** the bytecode fix so that the program can actually run, then addresses the other defects in a logical order.

---

## Critical Fixes – Execution Order (must be completed first)

### 1. Bytecode Prevention – Entire Project
**Goal:** Eliminate all `PermissionError` / `__pycache__` creation attempts.

- **In every `.py` file** (`config.py`, `camera.py`, `pins.py`, `components.py`, `wires.py`, `simulation.py`, `canvas.py`, `toolbar.py`, `selection.py`, `file_io.py`, `ui_overlay.py`, `main.py`):
  Insert these two lines **as the absolute first two lines** of the file, before any comments, docstrings, or other imports:

  ```python
  import sys
  sys.dont_write_bytecode = True
  ```

- **Create `sitecustomize.py`** in the project root with exactly the same two lines. This file is automatically executed by the Python interpreter on startup and acts as a safety net for any import.

- **In `main.py`**:  
  After adding the bytecode lines, move any existing module docstring **below all `import` statements** to avoid `E402` warnings. The bytecode preamble must remain at line 1.

- **Verification:**  
  Immediately after making the changes, run `python main.py` (or the test harness) from the project directory. The application should launch **without** any `PermissionError` or `__pycache__`‑related traceback. If any error still appears, check that every file has the two lines and that no `__pycache__` directory was created inadvertently. This step *must* succeed before any further work.

---

### 2. Pin Labels – `"IN"` / `"OUT"` Text on Every Pin Circle
**Goal:** Render clear, persistent pin labels at all zoom levels.

- Implement a `_render_pin(pin, screen, camera, label)` method in `components.py`.
- For each pin:
  - Draw the filled circle (as before).
  - Calculate a label position **8 pixels outward** from the component edge, perpendicular to the pin’s normal.
  - Use a camera‑scaled font: `pygame.font.SysFont('Arial', max(10, int(12 * camera.zoom)))`.
  - Render the label string (e.g., `"IN"` or `"OUT"`) with anti‑aliasing.
- Apply this method in **every** draw path:
  - Normal component drawing (all gates, INPUT, OUTPUT, CLOCK, SEVEN‑SEGMENT).
  - Placement preview ghost shown by the toolbar (so the user sees connection points before placing).
  - Any selection or overlay draw calls that show the component.

**Verification:**  
After implementation, start the simulator, place any gate or display component. All pins must display a visible `"IN"` or `"OUT"` text at every zoom level, including during drag‑preview.

---

### 3. Sample Circuit Files
**Goal:** Provide the required example circuits so that the save/load feature can be tested end‑to‑end.

- Create a directory named `circuits/` in the project root (next to `main.py`).
- Once the core simulation engine and file I/O are working, use the simulator’s **Save** function (`Ctrl+S`) to generate:
  - `circuits/half_adder.json` – a half‑adder implemented with an XOR gate for sum, an AND gate for carry, two INPUT nodes (`A`, `B`), and two OUTPUT nodes (`SUM`, `CARRY`).
  - `circuits/ripple_counter_4bit.json` – a 4‑bit ripple counter built from D flip‑flops (constructed from basic gates), driven by a CLOCK generator, with the counter’s outputs connected to a SEVEN‑SEGMENT DISPLAY that shows the current count.
- Verify that both files load correctly via `Ctrl+O` and simulate as expected (e.g., the half‑adder computes correct truth‑table values, the counter increments with each clock pulse).

---

### 4. Delete Key Suppression When Properties Panel Is Open
**Goal:** Prevent accidental deletion of components while the user is editing properties.

- In `main.py`, locate the keyboard handler `_handle_keydown`.
- Change the Delete‑key guard from only checking the file dialog:
  ```python
  if not self.overlay.show_file_dialog and key == pygame.K_DELETE:
  ```
  to an extended check that also considers the properties panel:
  ```python
  if (not self.overlay.show_file_dialog and
      not self.overlay.show_properties and
      key == pygame.K_DELETE):
  ```
- Ensure that `self.overlay.show_properties` is set to `True` whenever the right‑click properties panel is displayed, and `False` when it is closed (typically on clicking outside the panel or pressing `Enter`/`Escape`).

**Verification:**  
Right‑click a component to open its properties panel, then press `Delete`. The component must **not** be deleted. Close the panel and press `Delete` again – the deletion should work as usual.

---

### 5. Linter Cleanliness
**Goal:** Eliminate all warnings from Flake8 / Pylint.

- **Remove unused imports:**
  - `main.py`: `COLOR_HIGH`, `COLOR_LOW`, `OutputNode`, `ClockGenerator`.
  - `ui_overlay.py`: `COLOR_HIGH`, `COLOR_LOW`.
  - `wires.py`: `COLOR_WIRE` (if present).
- **Remove unused local variables:**
  - `main.py`: `dt`, `toolbar_hover` (if assigned but never used).
  - `components.py`: unused `font` / `camera_zoom` in `InputNode._draw_body`, unused `margin` in `SevenSegmentDisplay.render`.
- **Fix indentation in `selection.py`** around line 109: align continuation lines **4 spaces** beyond the opening parenthesis to pass E127.
- **Type checking compatibility** in `components.py`:  
  At the top, add:
  ```python
  from __future__ import annotations
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from camera import Camera
      from pins import Pin
  ```
  This resolves forward‑reference warnings while keeping the runtime clean. Also leave the bytecode preamble above all of these.

**Verification:**  
Run `flake8` and `pylint` on the entire project; there should be **zero** errors or warnings.

---

## Full Feature Implementation (unchanged from original plan, after critical fixes)

Once the five critical fixes are applied and verified, proceed with the remaining features described below. The order ensures that core functionality (pan, zoom, components, wires, simulation) is integrated with the already‑corrected code.

1. **Skeleton & Configuration**
   - `config.py` holds window size, colors, grid size, FPS.
   - `main.py` sets up the Pygame window, runs the main loop, and draws a dot‑grid background via camera transforms.

2. **Pan & Zoom**
   - Middle‑mouse drag or `Space` + left drag pans the canvas.
   - Scroll wheel zooms centred on the cursor position.
   - `Camera` class handles coordinate conversions.

3. **Component Classes (Gates, Input/Output, Clock, Seven‑Segment)**
   - Each component defines its input/output pin positions.
   - Drawing methods render the component body, pins (with `"IN"`/`"OUT"` labels via the already‑implemented `_render_pin`), and dynamic state (HIGH = green, LOW = grey).
   - `InputNode` toggles state on click.
   - `OutputNode` shows its HIGH/LOW state with a coloured label.
   - `Clock` oscillates at a configurable frequency (default 1 Hz) and displays the frequency as text.
   - `SevenSegmentDisplay` accepts 7 ordered input wires and draws the corresponding digit segment pattern.

4. **Toolbar & Component Placement**
   - Toolbar on the left with clickable buttons for each component.
   - Placement mode activated on button click; a translucent ghost follows the mouse, showing all pin labels.
   - Left‑click on the canvas snaps to the grid and places the component.

5. **Selection & Movement**
   - Left‑click a placed component to select it; rubber‑band drag selects multiple components.
   - Selected components can be dragged to new positions.
   - Selected components can be deleted with the `Delete` key, subject to the modal‑aware guard from Critical Fix #4.

6. **Wires & Routing**
   - Wire drawn by clicking an output pin, then an input pin.
   - Wires follow orthogonal paths with automatic corners.
   - Right‑click a wire to delete it.
   - Each input pin accepts exactly one wire; output pins may fan out to many.

7. **Simulation Engine**
   - Every frame, topological evaluation updates all component outputs based on current inputs.
   - Cycle detection identifies combinational loops and highlights the offending wires/components in red with a warning message.

8. **File I/O (Save / Load)**
   - `Ctrl+S` saves the current circuit as JSON (components, IDs, types, positions, wire connections by pin ID).
   - `Ctrl+O` loads a circuit from a JSON file.
   - The JSON format is compatible with the sample circuits created in Critical Fix #3.

9. **UI Overlays**
   - File‑dialog prompts for save/load filenames.
   - Properties panel (right‑click a component) allows renaming and clock frequency adjustment.
   - Corner overlay shows current coordinates and zoom percentage.

10. **Final Verification**
    - The application starts without any `PermissionError`.
    - Pin labels are visible everywhere (place a few gates and inspect).
    - Sample circuits load and simulate correctly; the half‑adder gives correct sum/carry, and the ripple counter increments with each clock edge.
    - `Delete` key does nothing while the properties panel is open.
    - Linters (Flake8, Pylint) report zero warnings.
    - All other specified behaviours (pan, zoom, placement, wire connections, deletion, etc.) function as documented.

---

**Execution Order (re‑prioritised):**  
1. Apply bytecode preamble to every file + `sitecustomize.py`, **verify startup works**.  
2. Fix all linter issues (unused imports, variables, indentation, TYPE_CHECKING).  
3. Implement and verify pin label rendering.  
4. Implement the extended Delete‑key guard.  
5. Build remaining features (toolbar, components, simulation, etc.) with pin labels integrated.  
6. Generate and verify the two sample circuit files.  

This revised plan directly addresses every point of failure identified in the review and test run, guaranteeing a fully functional, clean codebase that passes all acceptance criteria.