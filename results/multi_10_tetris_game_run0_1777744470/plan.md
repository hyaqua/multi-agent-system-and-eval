## Implementation Plan: Tetris (Pygame)

### Architecture Overview
The game is split into four modules, each with a clear responsibility:
- `constants.py` – configuration and constants.
- `piece.py` – tetromino definitions and rotation logic.
- `board.py` – grid state, collision detection, line clearing.
- `main.py` – game loop, event handling, rendering, overall state management.

The core gameplay is driven by a `Game` class inside `main.py` that orchestrates `Board` and the active/next pieces. The game loop uses Pygame’s event system and a clock-based timer for piece gravity.

### Files to Create and Purposes

1. **`constants.py`**
   - Grid dimensions (10×20), cell size, window size.
   - Colors (by name and piece colors).
   - Initial fall interval (e.g., 800 ms), speed increment per level, scoring values (single, double, triple, tetris).
   - Preview panel position and size.
   
2. **`piece.py`**
   - Definition of the 7 tetrominoes as coordinate sets or 2D arrays (4×4 matrix for I, 3×3 for others).
   - A `Piece` class that holds:
     - Current shape matrix, color, position (x, y on grid).
     - Method `rotate()` – returns a new shape rotated 90° clockwise (transpose + reverse rows).
   - No collision logic here – it’s purely about the piece’s own data.

3. **`board.py`**
   - `Board` class:
     - 2D list representing fixed blocks (0 = empty, other ints = piece index or color).
     - `is_valid_position(shape, offset_x, offset_y)` – checks if a piece at a location collides with walls, floor, or locked blocks.
     - `lock_piece(piece)` – writes piece shape into board grid with its color index.
     - `clear_lines()` – scans for full rows, removes them, shifts down, returns number of lines cleared.
     - `is_game_over(piece_type)` – tries to place a new piece at spawn; if invalid -> game over.

4. **`main.py`**
   - Pygame initialization, window, clock.
   - `Game` class or global state:
     - `board` (Board instance).
     - `current_piece` (Piece), `next_piece` (type index to generate new Piece later).
     - `score`, `level`, `lines_cleared`.
   - Drop timer using `pygame.time.get_ticks()`.
   - Event handling: key presses (left/right/up/rotate, down/soft drop).
   - Main loop:
     1. Handle events (quit, keydown).
     2. Handle piece movement (timer-driven gravity, soft drop).
     3. Check if piece can move down; if not, lock it, clear lines, update score/level, spawn next piece.
     4. If spawn fails -> game over.
     5. Draw everything (background grid, locked blocks, current piece, next piece preview, score/level).
     6. If game over, overlay final score and level.
   - Rendering helper: draw a single cell, draw preview panel, draw text.

### Implementation Order

Build bottom-up, testing each module in isolation if possible (though integrated quickly):

1. **constants.py** – define all constants.
2. **piece.py** – define shapes/dictionaries, `Piece` class with rotation. Test by printing rotations.
3. **board.py** – implement `Board` class with basic grid, `is_valid_position`, `lock_piece`, `clear_lines`. Test with simple script.
4. **main.py (core loop)** – set up Pygame window, empty grid drawing, basic event loop (quit only).
5. **Piece spawning and gravity** – add `Game` state, spawn first piece, implement timer-based drop, lock when bottom, spawn next, simple rendering of board and piece.
6. **Clear lines and scoring** – after lock, call `clear_lines`, update score, calculate level and new drop interval.
7. **Input handling** – left/right movement with `is_valid_position`, rotation with up key (try to rotate, if invalid ignore or attempt simple wall kick by testing offsets).
8. **Soft drop** – down arrow accelerates drop by moving piece down every few frames or immediately.
9. **Next piece preview** – maintain `next_piece` type (shuffled bag or random), draw its shape in a preview area.
10. **Game over condition** – when spawning new piece fails, set `game_over = True`, stop gravity, draw game over screen.
11. **Polish** – ensure responsiveness, adjust speed curve, add optional hold piece? Not required by spec, skip.
12. **Final testing** – play through all features.

### Libraries Needed
- **pygame** (only external dependency; standard library for everything else).

### Feature Implementation Details

- **Pygame window with bordered playing field grid**  
  `pygame.display.set_mode((width, height))`. Draw grid lines or separate background. Store board drawing offset so pieces align.

- **All 7 standard tetrominoes with distinct colors**  
  In `piece.py`, define `SHAPES` dict with keys like 'I','O','T' etc., each mapping to a 2D list of 1/0 and a color from `constants.py`. `Piece` takes a type name.

- **Pieces fall automatically at a steady rate**  
  Use `pygame.time.get_ticks()` and `last_drop_time`. When `current_time - last_drop_time > drop_interval`, move piece down by one cell. `drop_interval` starts at `INITIAL_SPEED` (ms) and decreases as level rises.

- **Move left/right with arrow keys**  
  On `KEYDOWN` left/right, call `Board.is_valid_position` with offset x+/-1, if true, update piece’s x.

- **Rotate clockwise with up arrow**  
  On up key, call `piece.rotate()` to get new shape. Check `is_valid_position` with rotated shape at current position; if valid, replace shape. Simple rotation; can add small wall kick offsets if needed.

- **Soft drop with down arrow**  
  While down held (or on keydown), set `soft_drop = True`. In loop, if soft_drop, move piece down immediately on each frame or use a faster interval, until it can’t go further.

- **Pieces lock when landing**  
  After a drop attempt (gravity or soft) if `is_valid_position` for the next y fails, immediately lock: call `board.lock_piece(current_piece)`, set `current_piece = None`, then after clearing lines spawn next.

- **Completed rows detected and cleared**  
  `Board.clear_lines()` iterates rows bottom-up; if row all non-zero, delete it, insert empty row at top. Return number of cleared rows. Score increases: `multiplier * rows_cleared * 100` (e.g., 1:100,2:300,3:500,4:800).

- **Score display**  
  Render score, level, lines as `pygame.font.Font` surface to screen.

- **Falling speed increases with score/level**  
  Calculate level from total lines cleared: e.g., `level = lines // 10 + 1`. Then `drop_interval = max(100, INITIAL_SPEED - (level-1)*50)`.

- **Next piece preview**  
  Store `next_type` (string). Generate a new random type from 7 pieces (weighted equally) when piece locks. Draw a 4×4 grid of that piece’s shape in a preview area (fixed position beside board), using the shape data.

- **Game over when new piece can’t be placed**  
  After clearing lines and before spawning new piece, try to create a new piece at spawn position (x = board_width//2 – piece_width//2, y = 0). If `board.is_valid_position` returns False, set `game_over = True`. Display “GAME OVER” with final score and level.

- **Game over screen shows final score and level reached**  
  When `game_over`, stop the main update logic. Draw a semi-transparent overlay and center text “GAME OVER”, “Score: X”, “Level: Y”. Wait for quit or restart (restart not required but could be an optional Esc key to play again).

This plan should allow a coder to implement the game step by step without ambiguity.