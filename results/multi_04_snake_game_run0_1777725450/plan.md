# Snake Game Implementation Plan

## Files
- `snake_game.py` — single-file implementation containing all game logic, state, and rendering.

## Architecture
A minimal object-oriented design using three main classes:

1. **`Snake`** — holds the list of body segments (grid coordinates), current direction, and methods to move, grow, and check self-collision.
2. **`Food`** — manages the single food item: position (grid coordinate) and spawning logic to avoid the snake.
3. **`Game`** — orchestrates the game loop, handles input, updates state, renders everything, manages game-over state, and controls restart.

No separate module files; everything lives in one script for simplicity. The game loop follows the standard Pygame pattern: process events → update state → draw.

## Implementation Order
1. Initialization and window setup (Pygame, constants, grid cell size, colors).
2. `Snake` class: initial state, movement, growing, direction change validation, self-collision.
3. `Food` class: random placement avoiding snake.
4. `Game` class: game loop, event handling (arrow keys, restart key), scoring, collision checks, rendering (grid, snake, food, score, game-over overlay).
5. Integration and polish (steady pace with clock, edge-case handling like full grid).

## Libraries
- **Pygame** (`pip install pygame`) — for graphics, input, and timing. No other external dependencies.

## Feature Implementation Details

### 1. Pygame window with grid-based field
- Initialize Pygame, set display mode `WIDTH x HEIGHT`.
- Define `CELL_SIZE` (e.g., 20), `GRID_WIDTH = WIDTH // CELL_SIZE`, `GRID_HEIGHT = HEIGHT // CELL_SIZE`.
- Optionally draw faint grid lines using `pygame.draw.line` for visual clarity, or just color the background and let segments fill cells.

### 2. Snake controlled with arrow keys
- Use `pygame.KEYDOWN` events mapping `K_UP`, `K_DOWN`, `K_LEFT`, `K_RIGHT` to a variable `next_direction`.
- Prevent 180° reversals: if moving right, ignore left input. Validate before updating direction each frame.

### 3. Continuous movement at steady pace
- Use `pygame.time.Clock`. Set a fixed tick rate (e.g., 10–15 FPS for classic snake speed).
- On each tick, update the snake’s head position based on current direction: `head.x += dx`, `head.y += dy` (dx, dy from direction vector). Insert new head at front of segment list, pop tail (unless growing).

### 4. Food spawns at random unoccupied grid
- Generate a random `(x, y)` pair within the grid bounds. Repeat until the chosen position is not present in the snake’s segment list.
- Place only one food item at a time; re-spawn immediately after it is eaten.

### 5. Snake grows when eating food
- When the snake’s new head position equals the food position, skip popping the tail (the segment list grows by one), increment score by 1, and call `food.respawn()`.

### 6. Score counter displayed on screen
- Use a simple `pygame.font.Font(None, 36).render(f"Score: {score}", ...)` call each frame. Position in a corner (e.g., top-left) consistently.

### 7. Game ends on wall collision
- After updating head position, check if `head.x < 0 or head.x >= GRID_WIDTH or head.y < 0 or head.y >= GRID_HEIGHT`. If true, set game state to `GAME_OVER`.

### 8. Game ends on self-collision
- After the head is placed (and before tail removal on grow) check if the head’s new position already exists in the snake’s segment list (excluding the tail that would be removed). For simplicity, after updating, check if `head` is in `snake.body[1:]` (all but the head). If true, game over.

### 9. Game over screen with final score
- When game state is `GAME_OVER`, fill screen with a semi-transparent overlay or solid color, then render two text surfaces: “GAME OVER” and “Score: X” centered. Blit them to the screen.

### 10. Restart with key press after game over
- In event loop, while game over, listen for a specific key (e.g., `K_r` or `K_SPACE`). On press, re-instantiate `Snake`, `Food`, reset score, and change state to `PLAYING`. The main loop resumes normal updates.