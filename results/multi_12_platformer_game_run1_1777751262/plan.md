# Platformer Game Implementation Plan

## Project Structure
```
platformer_game/
├── main.py                # Entry point: initializes Pygame, runs game loop
├── constants.py           # Game-wide constants (window size, colors, physics)
├── game.py                # Main Game class: state management, game loop logic
├── player.py              # Player class: movement, jumping, gravity, health
├── platform.py            # Platform class: simple rect-based solid surfaces
├── enemy.py               # Enemy class: patrol behavior, collision damage
├── coin.py                # Coin class: collectible item
├── camera.py              # Camera class: horizontal viewport tracking
├── ui.py                  # UI elements: coin counter, health bar, game over screen
├── level.py               # Level loader and container: reads level data, creates objects
├── levels/                # Level data files
│   ├── level1.json
│   ├── level2.json
│   └── level3.json
└── assets/                # (optional, only if images/sounds added later; not required)
```

## Architecture
- **Game** class (in `game.py`) manages all game states: `MENU`, `PLAYING`, `LEVEL_COMPLETE`, `GAME_OVER`. It holds the current `Level`, `Player`, `Camera`, and `UI`. The main loop (in `main.py`) calls `Game.handle_events()`, `Game.update()`, and `Game.render()`.
- **Player** handles physics: horizontal movement (left/right arrow keys), jumping (spacebar), gravity, collision with platforms, health, and damage cooldown (invincibility frames after hit).
- **Platform** is a simple `pygame.Rect` with a color. A list of platforms is stored in `Level`.
- **Enemy** has a position, velocity, and patrol range (left/right bounds). It toggles direction when hitting bounds or platform edges. On collision with player, deducts health and applies knockback.
- **Coin** is a rect; when player intersects it, coin is removed and score increments.
- **Camera** defines a world offset `camera_x` that shifts rendering so the player stays centered (with clamping at level bounds).
- **UI** draws HUD text and health bar; shows game over screen with restart option.
- **Level** loads data from a JSON file and creates platform, coin, enemy, player start, and goal objects. The goal is a special rect that triggers level completion.

## Implementation Order
1. **Project setup**: Create files, import Pygame, define constants.  
2. **Basic window and main loop**: Open a Pygame window, handle quit event, clear screen.  
3. **Player movement and gravity**: Implement player rect, horizontal movement, gravity, and jumping.  
4. **Platforms and collision**: Add platform list, detect collisions from above (landing) and sides (blocking).  
5. **Camera scrolling**: Track player position and apply horizontal offset during rendering.  
6. **Collectible coins**: Spawn coins, check overlap, update counter.  
7. **Enemies and damage**: Add enemy patrol, hurt player on touch, implement health.  
8. **Health display and game over**: Draw health bar, trigger game over state.  
9. **Level loading and multiple levels**: Create JSON level format, load level1, ensure all features work.  
10. **Goal point and level advancement**: Add goal rect, transition to next level or show completion.  
11. **Additional levels**: Design level2 and level3 JSON files with varied layouts.

## Libraries Required
- `pygame` (only external dependency)

## Feature Implementation Details

### Pygame Window & Main Loop
- `pygame.init()`, set mode with `WIDTH, HEIGHT` constants (e.g., 800x600).  
- Game loop runs at 60 FPS capped with `clock.tick(60)`.  
- Events handled: quit, keydown (for movement/jump).  
- States: `PLAYING` (update/draw everything), `GAME_OVER` (show death screen), `LEVEL_COMPLETE` (brief pause then load next).

### Player Movement & Physics
- Player is a `pygame.Rect` with `pos = [x, y]`, `velocity = [0, 0]`, `on_ground = False`.  
- Horizontal: arrow keys add/subtract from `velocity.x`, limited by `MAX_SPEED`. Deceleration when no key pressed.  
- Jump: if `on_ground` and space pressed, set `velocity.y = JUMP_STRENGTH` (negative).  
- Gravity: each frame `velocity.y += GRAVITY`; cap at `MAX_FALL_SPEED`.  
- Movement resolution: move x first, check platform collisions; then move y, check platforms. On collision from top, set `velocity.y = 0`, `on_ground = True`, align bottom with platform top. Side collisions stop x movement.

### Platforms & Collision
- Each platform is defined by `x, y, width, height`. Loaded from level data.  
- Collision detection using `player.rect.colliderect(platform.rect)`.  
- Resolve only from top to allow standing; side collisions handled by x-movement check. Player moved back if overlapping from side.

### Camera Scrolling
- `camera_x` calculated as `player.rect.centerx - WIDTH//2`, clamped between 0 and `level_width - WIDTH`.  
- All world objects (platforms, coins, enemies, goal) are drawn offset by `-camera_x` (and `y` unchanged).  
- Player and HUD drawn without camera offset.

### Coins
- Coin rects small (e.g., 16x16) at given positions.  
- If `player.rect.colliderect(coin.rect)`: remove coin from list, increment `score`.  
- Coin counter UI: text at top-left "Coins: X".

### Enemies
- Enemy rect defined by position and size.  
- Patrol logic: move horizontally between two boundary x-coordinates (or reverse when hitting a platform edge). Speed constant.  
- Damage: on collision with player: if not invincible, reduce `player.health -= DAMAGE` (e.g., 1), set invincible timer (e.g., 2 seconds) to prevent immediate re-damage, apply a small knockback.  
- Invincibility indicated by blinking or transparency.

### Health System
- Player health stored as integer (e.g., start 3). Displayed as a red bar in HUD (width proportional to health).  
- When health reaches 0, game state becomes `GAME_OVER`.  
- Game over screen: dark overlay, "Game Over" text, "Press R to restart" (resets to level 1 and full health).

### Multiple Levels
- Levels defined in JSON files with structure:  
  ```json
  {
    "player_start": [100, 500],
    "goal": [700, 0, 50, 50],
    "platforms": [...],
    "coins": [...],
    "enemies": [...],
    "width": 1200
  }
  ```
- `Level` class loads a file, creates platforms/coins/enemies lists, sets player start position, stores goal rect.  
- Three files: `level1.json`, `level2.json`, `level3.json` with distinct layouts (increasing difficulty, varied gaps, enemy placement).

### Goal Point & Level Progression
- Goal is a rect, often a small area at the far right.  
- When player touches goal rect, trigger `LEVEL_COMPLETE`. After a short delay, load next level (or wrap around to level 1 if last level). Reset player health to full on new level (or carry over but full reset recommended).  
- Transition effect: fade out/in or simple instant load.

### HUD Design
- Health bar: green/red rectangle top-left, with border.  
- Coin counter: text near health bar.  
- All HUD elements drawn after world (so they stay fixed on screen).