## Implementation Plan: Classic Snake Game

### 1. Files to Create and Their Purposes

- **`constants.py`** – Central configuration: grid size (e.g., 20x20 cells), cell size in pixels, colors, frames per second (FPS), initial snake length, etc.
- **`snake.py`** – `Snake` class: manages segments (list of grid coordinates), direction, growth, movement, self‑collision detection.
- **`food.py`** – `Food` class: spawns at a random unoccupied cell, provides its position, regenerates when eaten.
- **`game.py`** – `Game` class: orchestrates game state (playing / game over), score, high‑level update logic (snake-head collision with food, walls, self), restarting.
- **`main.py`** – Entry point: initialises Pygame, creates the `Game` instance, runs the main event and game loop, handles input (arrow keys, restart key).

### 2. Architecture

```text
main.py
  ├── initialises pygame, clock, screen
  ├── creates Game instance
  └── main loop:
        ├── polls events (QUIT, KEYDOWN)
        ├── updates Game (movement, collisions, food)
        └── draws Game (grid, snake, food, score / game over)

game.py (Game)
  ├── holds Snake, Food, score, game_over flag
  ├── update():
  │     ├── moves snake (based on tick counter)
  │     ├── checks wall collision → game over
  │     ├── checks self collision → game over
  │     ├── if head at food position: eat, grow, score++.
  │     └── if not eaten, snake just moves.
  └── draw(screen):
        ├── draws background and grid lines
        ├── draws snake (each segment)
        └── draws food or game-over overlay + score

snake.py (Snake)
  ├── segments (list of [x,y] grid positions)
  ├── direction (dx, dy)
  ├── can_change_direction(new_dir) – prevents 180° reversal
  ├── move(grow=False) – advance head, pop tail unless growing
  └── check_self_collision() – head collides with any other segment

food.py (Food)
  ├── position [x,y] on grid
  └── respawn(occupied_cells) – place at random free cell
```

Interaction:

- `Game.update()` calls `Snake.move(grow)` and `Snake.check_self_collision()`.
- When food is eaten, `Game` increases score, tells `Food` to respawn with the current occupied cells (snake segments).
- The rendering step in `Game.draw()` asks `Snake` for its segments and `Food` for its position to draw them.
- Keyboard input in `main.py` sets snake direction via `Game.set_direction()`.

### 3. Implementation Order

1. **`constants.py`** – Define all constants first so other modules can import them.
2. **`snake.py`** – Build and test the snake logic in isolation (e.g., instantiate, move, change direction).
3. **`food.py`** – Create food spawning logic, ensuring it never overlaps the snake.
4. **`game.py`** – Assemble `Snake` and `Food` into a game manager. Implement collision detection (walls, self) and score tracking.
5. **`main.py`** – Write the Pygame loop, event handling, and display logic. Connect keyboard to direction changes and restart key.

### 4. Libraries

- **Pygame** (`pygame`) – the only external dependency. Standard library modules (`random`, `sys`) are used.
- No other libraries required.

### 5. Feature Implementation Details

**Pygame window and grid display**  
In `main.py`, initialise Pygame, set window size to `GRID_WIDTH * CELL_SIZE` × `GRID_HEIGHT * CELL_SIZE`. In `Game.draw()`, fill the background and optionally draw faint grid lines using `pygame.draw.rect` or line loops.

**Snake controlled with arrow keys**  
In the `main.py` event loop, on `pygame.KEYDOWN` for arrow keys, call `Game.set_direction(dx, dy)`. The `Snake` class has a `direction` attribute that is updated only if the new direction is not opposite to current (e.g., not 180°). This prevents the snake from reversing into itself.

**Continuous movement at steady pace**  
Use a frame‑independent tick counter or a fixed movement timer. Simplest: run game logic every `N` frames using a counter; or utilise `pygame.time.get_ticks()` and move every `MOVE_INTERVAL` milliseconds. The plan: `Game.update()` checks elapsed time and only advances the snake when the interval passes.

**Food spawning at random unoccupied position**  
`Food.respawn(occupied)` uses `random.randint` to pick grid coordinates. Keeps trying until a free cell is found (or uses list of free cells for efficiency). Occupied set = all snake segment positions.

**Snake grows when eating food**  
When head position equals food position, `Game.update()` calls `Snake.move(grow=True)` which appends a new head but does not remove the tail, effectively extending the snake by one segment. Then score is incremented and food respawns.

**Score counter displayed and increments**  
`Game` holds `score` attribute, incremented on eating food. `Game.draw()` renders the score at the top of the screen (or as an overlay) using `pygame.font.Font` rendered text, e.g., `Score: {score}`.

**Game over on wall collision**  
After moving the snake, check if head `(x, y)` is outside `[0, GRID_WIDTH-1]` × `[0, GRID_HEIGHT-1]`. If so, set `game_over = True`.

**Game over on self collision**  
`Snake.check_self_collision()` returns `True` if the head position appears in any other segment of the list. `Game` calls this after movement and sets `game_over` accordingly.

**Game over screen with final score**  
When `game_over` is `True`, `Game.draw()` ignores the live game rendering and instead draws a centred “Game Over” message and the final score, with instruction “Press R to restart” or similar.

**Restart by key press after game over**  
In `main.py`, check for `pygame.KEYDOWN` with `K_r` when `game.game_over` is true. Call `Game.reset()` which reinitialises the snake to a starting position, resets score, respawns food, and sets `game_over = False`. Alternatively, just create a new `Game` instance.