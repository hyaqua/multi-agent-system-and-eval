# Revised Implementation Plan: Tetris Game

## 1. Files to Create

- **`constants.py`** – Game configuration constants: grid dimensions, cell size, key bindings, timing, and **all color definitions** (`BLACK`, `WHITE`, `RED`, `GRAY`, etc.). Every color used by the renderer or game logic is defined here as an uppercase RGB tuple.
- **`pieces.py`** – Tetromino piece definitions: shapes, rotations, and colors.
- **`game.py`** – Core game logic: board state, piece management, collision detection, line clearing, scoring, speed control.
- **`renderer.py`** – All drawing functions: grid, current piece, next piece preview, score/level display, game over screen. Imports needed colors (like `RED`, `WHITE`) from `constants.py`. Unused imports (`BLACK`, `GRAY`, `GHOST_COLOR` if not yet used) are removed to keep linting clean.
- **`main.py`** – Application entry point: Pygame setup, game loop, event handling, state transitions.

## 2. Architecture

(Unchanged – same as original plan, just ensure `constants.py` defines the missing `RED` and that `renderer.py` imports it.)

## 3. Implementation Order

1. **`constants.py`** – define grid size, cell size, colors (including `RED = (255,0,0)`, `WHITE = (255,255,255)` for text), speeds, keys.
2. **`pieces.py`** – define all 7 pieces with rotation matrices.
3. **`game.py`** – implement `Game` basics: board initialisation, `collides()`, `spawn_piece()`, `lock_piece()`, `clear_lines()`, scoring, speed calculation.
4. **`renderer.py`** – draw the grid, a piece, next piece box, text, and a dedicated `draw_game_over()` function that uses `RED` for the “GAME OVER” title and `WHITE` for score/level text. Import `RED`, `WHITE` (and other needed colors) from `constants`. Remove any unused imports (e.g., `BLACK`, `GRAY`, `GHOST_COLOR` if they aren’t used yet).
5. **`main.py`** – connect everything: game loop, input, game over handling.
6. **Polish** – verify that the game over screen works (no `NameError`). Add soft drop repeat, level‑up speed curve, game over restart.

## 4. Required Libraries

- **pygame** – the only external dependency (`pip install pygame`).
- Standard library modules (`random`, `copy`) only.

## 5. Feature Implementation Details

(All features from the original plan remain valid. The following sections are updated or added to address the review feedback.)

### Game over screen

- In `renderer.py`, implement a function `draw_game_over(screen, game)` that:
  - Fills the screen with a semi‑transparent overlay or a dark background.
  - Renders “GAME OVER” in **`RED`** (imported from `constants`) using a large font.
  - Renders “Score: ...  Level: ...” in **`WHITE`** (also imported from `constants`).
  - Renders “Press R to restart or ESC to quit” in white.
- `main.py` calls `draw_game_over()` when `game.game_over` is `True`, and waits for the appropriate key press (R to restart, ESC to quit).
- The `RED` constant must be defined in `constants.py` as `RED = (255, 0, 0)` (already present if other features use red for piece Z; double‑check that it is defined). `WHITE` is defined as `(255, 255, 255)` for general text.

### Renderer imports clean‑up

- In `renderer.py`, only import the colors that are actually used. For example, if the ghost piece feature is not yet implemented, remove `GHOST_COLOR`. Ensure `RED`, `WHITE`, and any other required colors are imported. A minimal import line might look like:

  ```python
  from constants import RED, WHITE, GRID_COLOR, NEXT_PANEL_BG, ...  # adjust as needed
  ```

### Bug fix: missing `RED`

- The original `renderer.py` used `RED` but did not import it. The revised plan explicitly adds `RED` to `constants.py` (if not already there) and imports it in `renderer.py`. This prevents the `NameError` crash when the game over screen is displayed.

With these changes, the game over screen will display correctly, showing final score and level without crashing. All other features remain as originally planned.