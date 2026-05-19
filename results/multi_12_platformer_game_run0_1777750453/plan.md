# Revised Implementation Plan: 2D Platformer Game

## Overview

The original plan was sound, but the primary issue was the absence of the **main.py** entry point. This document revises the plan to guarantee that main.py is created early and serves as the central integration hub. All other modules (camera, sprites, level, gui) are progressively connected through main.py, with incremental testing after each addition.

## 1. Project Structure

```
platformer_game/
├── main.py            # Entry point, game loop, state manager (MUST EXIST FIRST)
├── settings.py        # All constants (screen, physics, colors, paths)
├── sprites.py         # Player, Enemy, Coin sprite classes
├── level.py           # LevelLoader, Level class
├── camera.py          # Camera class for horizontal scrolling
├── gui.py             # UI drawing (health, coins, game over)
├── levels/            # Level data files
│   ├── level1.json
│   ├── level2.json
│   └── level3.json
└── assets/            # (optional, empty or for future art)
```

## 2. Architecture

- **Game States**: `menu`, `playing`, `level_complete`, `game_over`.  
  Managed by a simple string variable in `main.py`.
- **Core Loop** (in `main.py`):
  1. Process events.
  2. Update game objects based on current state.
  3. Draw everything (camera-adjusted for playing state, HUD on top).
- **Sprite Groups**:  
  - `all_sprites` for efficient update/draw.  
  - `platforms`, `coins`, `enemies`, `player` separate groups for collision.
- **Level Loading**:  
  Each level is a JSON file. `LevelLoader` reads it and populates a `Level` object containing: list of platform rectangles, enemy spawn info, coin positions, player start, goal area.
- **Physics**: Simple Euler integration for velocity/gravity, handled in `Player.update()`.
- **Camera**: Follows player horizontally, clamps to level boundaries.
- **UI**: Drawn on top of the screen (HUD) – coin counter, health bar. Game over screen is a separate drawing routine.

## 3. Implementation Order (Revised for Early Integration)

The critical change: **main.py is created immediately after settings.py**, and it is continuously expanded as new modules are added. This ensures the game is always runnable and testable.

1. `settings.py` – define all constants.
2. **`main.py` – Minimal Pygame skeleton**  
   - Initialize Pygame, create window, define states variable (`state = "menu"`).  
   - Implement a main `while` loop that handles `QUIT` event, calls a dispatcher that draws/updates according to state. Initially only `menu` and `playing` states, with `playing` just clearing the screen.
   - This gives a runnable application (window opens, closes, can exit via quit).
3. `camera.py` – implement `Camera` class.  
   After completion, update `main.py` to import `Camera`, instantiate it in `playing` state, and apply offset to a dummy rectangle to verify scrolling.
4. `sprites.py` – `Player` class with movement, gravity, floor collision, placeholder rendering.  
   Update `main.py` to create a `Player` instance, add it to an `all_sprites` group, and draw with camera offset. Test left/right movement, jump, and gravity against a hardcoded test platform.
5. `level.py` – create JSON level format and `LevelLoader`.  
   Update `main.py` to load a level and spawn player at the defined start. Platforms become `pygame.sprite.Sprite` objects added to `platforms` group. Test player-platform collision.
6. Integration milestone: The basic game loop is running with player, platforms, camera, and gravity.
7. `sprites.py` – add `Coin` class (collision with player, pickup removal, coin increment).  
   Update `main.py` to populate coins from level data, add to `coins` group, and check collision. Print coin count to console for now.
8. `gui.py` – implement draw functions for coin counter and health bar.  
   Update `main.py` to call these drawing routines each frame while state is `playing`. (Health bar can show a static full health at this point.)
9. `sprites.py` – add `Enemy` class (patrol, collision with player causes damage, invincibility timer).  
   Update `main.py` to spawn enemies, add to `enemies` group, handle damage logic, reduce health.
10. `gui.py` – enhance health bar to reflect actual `player.health`.  
    Update `main.py` to check `player.health <= 0` and transition to `game_over` state.
11. `gui.py` – draw game over screen (with restart prompt).  
    Update `main.py` to handle `game_over` state: display message, wait for key press to restart from level 1.
12. `level.py` – add goal area detection.  
    Update `main.py`: when player rect overlaps goal rect, set state to `level_complete`.
13. State transitions:  
    In `main.py`, `level_complete` state loads next level (if exists), otherwise shows victory. `game_over` restarts from first level. `menu` shows title, waits for Enter to start playing.
14. Create 3 distinct level JSON files with increasing difficulty.
15. Polish: clamp camera to world boundaries, ensure enemies turn at platform edges, add final touches.

## 4. Libraries

- **pygame** (required).  
  Standard Python library only (json, os, sys). No external libraries.

## 5. Feature Implementation Details (unchanged from original, but with integration notes)

Each feature’s logic remains as originally specified, but now explicitly tied to **main.py** updates:

- **A. Pygame Window**: `main.py` creates the window using `SCREEN_WIDTH=800, SCREEN_HEIGHT=600` from `settings.py`.
- **B. Player Movement**: `Player` class handles input in its `update()`. `main.py` passes the current pressed keys.
- **C. Jump and Gravity**: `Player` class applies gravity and handles platform collision.
- **D. Platforms**: Level loader creates platform sprites stored in `platforms` group. Collision is done via axis‑separation in `Player.update()` after each movement.
- **E. Collectible Coins**: `Coin` sprites are loaded by `LevelLoader` and added to `coins` group. `main.py` checks collision each frame.
- **F. Coin Counter**: `gui.py` function draws text from `player.coins`. `main.py` calls it after drawing sprites.
- **G. Enemy Patrol**: `Enemy` class patrols using platform edge detection. `main.py` updates all enemies.
- **H. Player Takes Damage**: Collision with enemies handled in `main.py` or `Player.update()`, depending on design. Invincibility timer stored in player.
- **I. Health Display**: `gui.py` draws health bar using `player.health / MAX_HEALTH`.
- **J. Game Over**: When health ≤ 0, `main.py` sets state to `game_over`, calls `gui.py` to draw game‑over screen.
- **K. Multiple Levels**: Level files in `levels/`. Next level loaded when player touches goal. In `main.py`, state `level_complete` increments a level index, loads new level.
- **L. Camera Scroll**: `Camera` object updated each frame in `main.py` before drawing, offset applied to all sprite rects.
- **M. State Transitions**: All controlled in `main.py` via the `state` variable. Details as in step 13 above.

## 6. Integration and Testing Strategy

To prevent the exact problem encountered (missing main.py), we follow a hands‑on incremental build:

- **After completing each step that creates or modifies a Python file**, run the game (e.g., `python main.py`) to verify that:
  1. The file exists and contains valid Python syntax.
  2. Imports succeed (no `ImportError`).
  3. The game window opens and the new feature behaves as expected.
- Maintain a simple checklist in the project (e.g., a `TODO.md`) that marks each step as completed.
- At step 2, `main.py` must be a standalone script that runs without errors before moving on. This guarantees the entry point is never missing.

## 7. Revised Implementation of main.py (Skeleton)

To further clarify, here is the mandatory structure that must be present in `main.py` from the very beginning:

```python
import pygame
import sys
from settings import *

# State management
state = "menu"
current_level = 0
level_data = None
all_sprites = pygame.sprite.Group()
platforms = pygame.sprite.Group()
coins = pygame.sprite.Group()
enemies = pygame.sprite.Group()
player = None
camera = None

def load_level(index):
    # Clear groups, load JSON, create sprites, set player start, etc.
    pass

def main():
    global state, camera, player, all_sprites, platforms, coins, enemies
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    # Game loop
    while True:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            # State-specific event handling
            if state == "menu":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    state = "playing"
                    load_level(0)
            # ... more event hooks

        # Update
        keys = pygame.key.get_pressed()
        if state == "playing":
            # Update player, enemies, camera, etc.
            pass

        # Draw
        screen.fill(BLACK)
        if state == "playing":
            # Draw sprites with camera offset
            pass
        elif state == "menu":
            # Draw title screen
            pass
        # ... other states

        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()

if __name__ == "__main__":
    main()
```

This skeleton evolves with each module integration, but the core loop and state variable remain the anchors.

## 8. Conclusion

The revised plan explicitly prioritizes the creation and continuous expansion of `main.py`, ensuring that all modules are integrated from the start. The original feature designs are retained, and incremental testing guarantees that the game is always in a runnable state. By following this plan, the missing‑file issue will be avoided entirely.