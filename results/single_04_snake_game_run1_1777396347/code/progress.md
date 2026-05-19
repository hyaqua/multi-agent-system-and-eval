STATUS: COMPLETE

## Features Implemented

1. **Pygame window with grid-based playing field** — Window is 600×400 pixels (30×20 grid of 20px cells). Grid lines are drawn each frame on a dark background.

2. **Snake appears on grid, controlled with arrow keys** — Snake starts at the center, 3 segments long, moving right. Arrow keys queue direction changes; 180° reversals are blocked.

3. **Snake moves continuously at steady pace** — Game loop runs at 10 FPS via `clock.tick(FPS)`. Each tick advances the snake one cell in the current direction.

4. **Food spawns at random unoccupied position** — `_spawn_food()` loops until it picks a position not occupied by any snake segment.

5. **Snake grows by one segment when eating food** — A `pending_growth` counter is incremented on eating; each subsequent frame, the tail is retained instead of dropped until the counter reaches zero.

6. **Score counter displayed and increments** — Score is rendered in the top-left corner with a semi-transparent background. +10 points per food eaten.

7. **Game ends on wall collision** — `Snake.update()` checks if the new head position is outside grid bounds and sets `alive = False`.

8. **Game ends on self collision** — `Snake.update()` checks if the new head position is in `body[:-1]` (excluding the tail which will move away).

9. **Game over screen with final score** — A dimmed overlay displays "GAME OVER" in red, the final score, and a restart hint.

10. **Restart on key press after game over** — Pressing R, Space, or Enter calls `Game.reset()` which reinitializes the snake, food, and score.

## Testing

- Code compiles without syntax errors.
- Game initializes cleanly with `SDL_VIDEODRIVER=dummy` and runs through the main loop without crashes.
- All game-logic paths (movement, collision, growth, scoring, game-over, restart) are implemented with no TODOs or placeholders.
