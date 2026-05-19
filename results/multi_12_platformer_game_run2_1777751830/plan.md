# Revised Platformer Game Implementation Plan

## Architecture Overview

The game is built around a central `Game` class that manages state (menu, playing, game over), updates game objects each frame, and renders via a camera. Levels are loaded from JSON files defining platforms, coins, enemies, start point, and goal. Each entity (Player, Platform, Coin, Enemy) is a class with its own update/draw logic and collision detection. A `Camera` class handles horizontal scrolling to keep the player in view. UI elements (coin counter, health bar) are drawn on top of the camera’s view or as a fixed HUD.

## Files and Their Purposes

| File | Purpose |
|------|---------|
| `main.py` | Entry point: initializes Pygame, creates the `Game` instance, runs the main loop. |
| `game.py` | `Game` class: holds game state (menu/playing/dead/level_complete), current level, player, camera, UI. Contains `run()` loop and orchestration of updates/renders. |
| `settings.py` | All constants: screen size, FPS, colors, gravity, player speed, jump velocity, enemy speed, health points, coin value, etc. |
| `level.py` | `Level` class: loads a level from a JSON file, stores lists of `Platform`, `Coin`, `Enemy`, start position, goal rect. Provides `update()` and `draw()` for non-player entities. |
| `player.py` | `Player` class: rect-based physics, movement left/right, jump with gravity, collision with platforms, interaction with coins/enemies/goal. |
| `platform.py` | `Platform` class: simple rectangle with a color; static. |
| `coin.py` | `Coin` class: rect and `update()`/`draw()`; checks collision with player to be collected and removed. |
| `enemy.py` | `Enemy` class: moves back and forth between two x limits; `update()` moves it, `draw()`. Collision with player causes damage (with invincibility cooldown). |
| `camera.py` | `Camera` class: offsets all drawing based on player position so the world scrolls horizontally. |
| `ui.py` | Functions/classes to draw coin counter (top-left), health bar (top-right), “Game Over” screen with restart prompt, and minimal level transition text. |
| `levels/` | Directory containing JSON level files (e.g., `level1.json`, `level2.json`, `level3.json`). Each defines the layout. |

## Implementation Order

1. **Setup and window** – Create `main.py` (Pygame init, display, clock) and `settings.py`. Stub a `Game` class in `game.py` with a basic loop that quits on close.
2. **Level loading and platforms** – Implement `Level` class that loads a JSON definition, creates `Platform` objects, and draws them. Write a sample `level1.json`. Ensure a static background/rects appear.
3. **Player movement and gravity** – Implement `Player` in `player.py`: keyboard input for left/right, jump with space only when on ground, gravity pulling down. Add collision detection against platforms so player lands/stops.
4. **Camera** – Add `Camera` class that adjusts drawing offsets based on player position. Modify `Game` to render the world offset by camera.
5. **Coins and counter** – Create `Coin` class. In `Level`, spawn coins from JSON. Player checks collision in update; on contact, increment coin count and remove coin. Draw coin count using `ui.py` (fixed on screen, not affected by camera).
6. **Enemies and health system** – Create `Enemy` class (patrol logic: move left until hitting x_min, reverse, etc.). Player-enemy collision reduces health with an invincibility timer to avoid per-frame damage. Draw health bar via UI.
7. **Goal point and level advance** – Define a goal rect in level JSON. Player overlap triggers a brief “Level Complete” message, then loads next level (via a list of level paths in `Game`). Reset player position, health restored to full. Keep coin count accumulating across levels. Level transition handled in `Game.change_level()`.
8. **Game over and restart** – When health ≤ 0, switch game state to “game_over”. Show “Game Over” text, prompt to press any key to restart from level 1 (reset health and coins). Use UI.
9. **Multiple levels and code cleanup**  
   - Create `level2.json` and `level3.json` with distinct, varied platform layouts (e.g., gaps, vertical sections, different enemy placements).  
   - Remove all unused imports and variables:  
     - In `level.py`, delete unused `SCREEN_HEIGHT` import.  
     - In `game.py`, delete unused `COLOR_WHITE`, `SCREEN_WIDTH`, `SCREEN_HEIGHT` imports and the unused variable `next_file`.  
     - In `main.py`, delete unused `COLOR_BLACK` import.  
   - Verify that all three levels load correctly and the game transitions through them.

## Libraries

- **pygame** (only third-party library): handles graphics, input, sound (not required), event loop.
- Standard libraries: `json` for level loading, `os` for file paths.

## Feature Implementation Details

- **Pygame window** – In `main.py`, initialize with `SCREEN_WIDTH`, `SCREEN_HEIGHT` from settings.
- **Player character** – `Player` class uses a `pygame.Rect` for position and collision. Move left/right changes `vel_x` (capped), `vel_y` incremented by gravity each frame. Jump adds upward velocity if on ground. Ground detection via collision with any platform rect, where player’s bottom fits on top.
- **Jump and gravity** – Gravity constant + `vel_y` update. On each frame, attempt movement along x and y separately; if y movement would overlap a platform, snap player to platform’s top.
- **Platforms** – `Platform` object holds `rect` and `color`. Drawn as filled rectangles. Level’s platform list used for collision.
- **Collectible coins** – `Coin` has a rect and a small radius or square, rendered as yellow circle. On player overlap: remove coin, increment `coins_collected` in `Player` or `Game`. UI reads this counter.
- **Coin counter** – Drawn top-left corner of screen (fixed), e.g., “Coins: 42”. Not affected by camera offset.
- **Enemies** – `Enemy` initialized with start x, patrol range (min_x, max_x), speed. `update()` moves it along x, reversing at boundaries. Drawn as red rectangles. Collision with player: if no invincibility active, reduce `player.health` by 1, set invincibility timer to ~1 second (flashing effect optional). If health becomes ≤0, trigger game over.
- **Health display** – A `draw_health_bar(screen, player.health, max_health)` in `ui.py`. Position top-right, fixed.
- **Game over** – In `game_over` state: clear screen, draw “GAME OVER” and “Press any key to restart”. On key, reset level list to first, reset player health and coins.
- **Three distinct levels** – `level1.json` simple flat ground + few platforms; `level2.json` gaps and moving enemies; `level3.json` taller vertical sections. JSON structure example:
  ```json
  {
    "platforms": [{"x": 0, "y": 550, "width": 800, "height": 50}, ...],
    "coins": [{"x": 200, "y": 500}],
    "enemies": [{"x": 400, "y": 510, "min_x": 350, "max_x": 600}],
    "player_start": [100, 500],
    "goal": [750, 520, 40, 40]
  }
  ```
- **Level advance** – Player rect overlaps goal rect → `Game.next_level()` increments level index, loads next JSON, resets player position, health to max. Show short “Level X” text.
- **Camera scrolling** – `Camera` tracks player; offset = player.rect.centerx - SCREEN_WIDTH//2, clamped so view doesn’t show beyond level boundaries. All world drawing (platforms, coins, enemies, player, goal) subtracts camera offset.

## Notes

- Collision detection: simple AABB overlap. For platforms, only the top face is solid (player can jump through from below). Enemies treat all sides as solid?
- Enemy patrol: implemented by tracking direction and flipping when reaching `min_x` or `max_x`. Enemies don’t need gravity; they stay fixed on their platform Y (could define a y anchor).
- Coins and enemies are part of the level data; when player reaches goal, current level objects are cleared and replaced.
- For smooth game over, after health hits zero, allow one final frame or immediate transition. Invincibility prevents quick multi-hit death.
- JSON files must be placed in a `levels/` folder; loading uses `json.load(open(os.path.join('levels', level_name)))`.
- No sound required.