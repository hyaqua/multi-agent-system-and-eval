```markdown
# Snake Game Implementation Plan

## Files and Purpose
- `constants.py` – Defines game dimensions, cell size, colors, directions, and tick speed.
- `snake.py` – `Snake` class: stores segments, handles movement, growth, self-collision.
- `food.py` – `Food` class: generates random unoccupied grid position.
- `game.py` – `Game` class: manages game state (running/game over), score, snake, food, and game loop logic.
- `main.py` – Entry point: initializes Pygame, creates `Game` instance, runs the main loop.

## Architecture
- **Model-View-Controller (lightweight)**:
  - `Game` acts as the controller, owns the `Snake` and `Food` instances.
  - `Snake` and `Food` are pure data/logic models.
  - Rendering is handled in `Game`’s `draw()` method using Pygame.
- Data flow:
  - `main.py` creates a `Game` and calls `game.update()` and `game.draw(screen)` each frame.
  - User input is polled in `main.py` and forwarded to `Game.handle_event()`.
  - `Game` ticks movement based on a timer, moves the snake, checks collisions, updates score, and spawns food.
  - On game over, `Game` sets a flag; `draw()` displays a game over overlay; a restart key resets state.

## Implementation Order
1. **Create `constants.py`** – Set `CELL_SIZE`, `GRID_WIDTH`, `GRID_HEIGHT`, window size, colors, directions (`UP`, `DOWN`, `LEFT`, `RIGHT`), base `FPS`.
2. **Implement `snake.py`** – `Snake.__init__()` initializes with 3 segments in the center, direction to the right. Methods: `move(direction)`, `grow()`, `head()`, `body`, `check_self_collision()`.
3. **Implement `food.py`** – `Food.__init__()` places food at a valid random cell. Method `spawn(snake, grid_width, grid_height)` to reposition.
4. **Build `game.py`** – `Game.__init__()` creates `Snake` and `Food` instances, sets score to 0, `game_over = False`. Method `reset()` to reinitialize. `update()`: if not game over, move snake at fixed interval (using a frame counter or `pygame.time.set_timer`), check wall/self collision, check food collision, update score, spawn new food. `draw(screen)`: draw grid, snake segments, food, score text, and game over screen. `handle_event()`: change direction on arrow keys, restart on a specific key when game over.
5. **Create `main.py`** – Initialize Pygame, set caption, create clock, instance of `Game`. Main loop: handle quit and key events via `game.handle_event()`, call `game.update()`, fill background, `game.draw(screen)`, flip display, tick clock.
6. **Add grid rendering** – In `draw()`, optionally draw thin lines for grid cells.
7. **Integrate movement timer** – Use `pygame.time.get_ticks()` to control move interval (e.g., 150 ms).
8. **Test all required features** iteratively.

## Libraries Needed
- `pygame` (version 2.x or later) – for graphics, input, and timing. No other external libraries.

## Feature Implementation Details
1. **Pygame window and grid**  
   - Window size = `GRID_WIDTH * CELL_SIZE` x `GRID_HEIGHT * CELL_SIZE` (e.g., 600×400 with CELL_SIZE=20).  
   - In `draw()`, loop over rows/cols and draw a background rect for each cell (optional grid lines).

2. **Snake and arrow key control**  
   - Snake segments stored as `list` of `(x, y)` grid coordinates. Head is `segments[0]`.  
   - On `KEYDOWN` event in `handle_event()`: update `self.direction` (a tuple from `constants.py`) if the new direction is not opposite of current one.  
   - During movement, compute new head position: `head[0] + dx, head[1] + dy`. Insert new head to `segments` list; if no food eaten, pop last segment.

3. **Continuous movement at steady pace**  
   - Track time of last move with `pygame.time.get_ticks()`. If `current_time - last_move >= MOVE_DELAY` (e.g., 150 ms), execute a move. Reset `last_move`.

4. **Food spawning**  
   - `Food.spawn()` picks a random `(x, y)` within grid bounds. Loop until the chosen cell is not occupied by any snake segment.

5. **Snake growth**  
   - When snake head overlaps food cell: set `self.grow_flag = True`. In the next move, do not pop tail, increasing length by 1. Then unset flag. Increment score.

6. **Score display**  
   - In `draw()`, render a surface with `pygame.font.SysFont(None, 36).render(f"Score: {self.score}", True, COLOR_WHITE)`. Blit at top-left corner.

7. **Game over – wall collision**  
   - After computing new head, if `head[0] < 0 or head[0] >= GRID_WIDTH or head[1] < 0 or head[1] >= GRID_HEIGHT`, set `game_over = True`.

8. **Game over – self collision**  
   - Check if new head position is in `snake.segments[1:]` (ignore current head). If yes, game over.

9. **Game over screen**  
   - In `draw()`, if `game_over` is true, render a semi-transparent overlay and text: “Game Over – Score: X – Press R to restart”. (Optionally use `pygame.SRCALPHA` surface).

10. **Restart**  
    - In `handle_event()`, if game over and `event.key == K_r`, call `game.reset()`, which reinitializes snake, food, score, and sets `game_over = False`.
```