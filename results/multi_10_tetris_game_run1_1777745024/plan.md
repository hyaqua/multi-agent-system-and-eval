## Implementation Plan: Tetris Game

### 1. File Structure and Purpose

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Initializes pygame, creates game and display objects, runs the main loop. |
| `settings.py` | All game constants: window size, grid dimensions, piece colors, fall speeds, scoring table. |
| `pieces.py` | Tetromino definitions (7 standard pieces) with shape matrices for each rotation state. `Piece` class representing an active piece (type, rotation, position). |
| `grid.py` | `Grid` class managing the playing field: 2D list of locked cells, collision detection, line clearing, and checking if a piece can be placed. |
| `game.py` | `Game` class: orchestrates game state (score, level, current piece, next piece, soft-drop, game over), handles keyboard input, piece falling, locking, line clearing, and speed calculation. |
| `display.py` | Rendering functions: draws the playing field grid borders, locked cells, active piece, next-piece preview panel, score/level text, and game-over overlay. |

### 2. Architecture

- **`main.py`** imports `Game` and `Display` (or uses display functions). It creates a `Clock` for frame-rate control and a game loop:
  - Process pygame event queue → `game.handle_input(event)`
  - Update game state based on delta time → `game.update(dt)`
  - Clear screen, call `draw(game.get_state())`, `pygame.display.flip()`
- **`Game`** class holds a `Grid`, current `Piece`, next `Piece` type, score, level, fall timer, drop interval. It uses methods:
  - `handle_input(event)`: on keydown, rotates or moves piece via grid collision checks.
  - `update(dt)`: increments timer; if timer > interval, moves piece down. If cannot move down, locks piece, clears lines, spawns next piece; if spawn fails, game over.
- **`Grid`** class stores a 2D array (e.g., `[[None]*10 for _ in range(20)]`). Methods:
  - `is_valid(piece, offset)`: checks if piece cells are within bounds and not overlapping locked cells.
  - `lock(piece)`: writes piece cells to the grid.
  - `clear_lines()`: finds full rows, removes them, inserts empty rows at top, returns number cleared.
- **`Piece`** class: holds `type`, `rotation_index`, `row`, `col`. Has method `cells()` returning list of (row, col) world coordinates using the rotated shape matrix. Rotations are pre-defined as a list of shape lists for each piece.

### 3. Implementation Order

1. **`settings.py`** – define all constants (grid width=10, height=20, cell size, margin, colors, drop intervals per level, line scores).  
2. **`pieces.py`** – define piece shapes as lists of rotation states (each state a list of (dx,dy) offsets or a matrix). Implement `Piece` class with `rotate()`, `move()`, `cells()`.  
3. **`grid.py`** – `Grid` class with `is_valid(piece)`, `lock(piece)`, `clear_lines()`. Test with simple manual tests.  
4. **`game.py`** – `Game` class tying everything together. Manages state, input, spawning, fall timer, scoring, level progression.  
5. **`display.py`** – functions `draw_grid()`, `draw_piece()`, `draw_preview()`, `draw_score()`, `draw_game_over()`. Retrieve state from game (`Game.get_drawable_state()` returning grid, current piece cells, score, next piece type, game_over flag).  
6. **`main.py`** – final integration. Initialize pygame, create window, instantiate `Game`, run loop.

### 4. Required Libraries

- `pygame` (for graphics, input, time)
- `sys` (for quitting)
- `random` (for selecting next pieces) – part of Python standard library.

No external dependencies beyond Pygame.

### 5. Feature Implementation Details

- **Pygame window with bordered playing field grid**  
  Window size calculated from `GRID_WIDTH * CELL_SIZE + PREVIEW_AREA + BORDERS`. `draw_grid()` uses `pygame.draw.rect` for border and grid lines.

- **7 standard tetromino pieces with distinct colors**  
  `pieces.py` defines a dictionary `SHAPES` mapping piece names to a list of 4 rotation states. Each state is a list of (x,y) offsets relative to a pivot. Colors in `settings.PIECE_COLORS`.

- **Automatic falling at steady rate**  
  `Game.update(dt)` accumulates `fall_timer`. When `fall_timer >= drop_interval` (based on level), the piece moves down one row. If `grid.is_valid(piece)` fails, it locks.

- **Move left/right with arrow keys**  
  `Game.handle_input(event)` on `KEYDOWN`. Left/right arrows call `piece.move(-1,0)` or `(1,0)`, but only if `grid.is_valid(piece)` with the offset.

- **Rotate clockwise with up arrow**  
  On up arrow: `piece.rotate(1)` (increment rotation index modulo 4). If the rotated piece is not valid, try wall kicks (optional; basic version: try offset 0, -1, +1 col). If still invalid, revert.

- **Soft-drop with down arrow**  
  Down arrow sets a fast drop interval (e.g., 50 ms) while held. In `update()`, if soft-drop flag is active, use a much shorter interval. Release resets to normal.

- **Piece locks when landing**  
  When the piece cannot move down, `game.lock_piece()` is called: `grid.lock(piece)`. Then `grid.clear_lines()` is called, score updated, and next piece spawned.

- **Completed rows cleared and rows shift down**  
  `grid.clear_lines()` scans all rows; if a row has no `None` cells, it is removed. `del grid[row]` and `grid.insert(0, [None]*10)`. Number of cleared rows returned.

- **Score display and increase on line clears**  
  `settings.SCORE_TABLE` maps number of lines cleared at once to points (1→100, 2→300, 3→500, 4→800). Added to `score`. Score rendered with `pygame.font` in `display.py`.

- **Falling speed increases with level**  
  Level = `floor(total_lines / 10)` or based on score thresholds. `drop_interval` = `max(50, BASE_INTERVAL - level * SPEED_DECREASE)`. So speed increases gradually.

- **Next piece preview panel**  
  `Game` stores `next_piece_type`. `display.py` draws the piece shape inside a small box on the right side using the first rotation state and color.

- **Game over when new piece cannot be placed**  
  When spawning a new piece, if `grid.is_valid(new_piece)` is false → `game_over = True`. In the main loop, if game over, stop updating and show overlay.

- **Game over screen shows final score and level**  
  `display.py` `draw_game_over()` renders "Game Over" text, final score, level, and "Press R to restart or Q to quit". `main.py` listens for those keys to reset (`Game.__init__()`) or quit.