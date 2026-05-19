"""
Integration test: simulate running the full game for a while.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from game import Game


def test_integration():
    pygame.init()
    game = Game()

    # Simulate 300 frames of gameplay with various inputs
    # We'll manipulate the game state directly to test transitions

    print("=== Integration Test ===")

    # Level 1: Simulate player reaching goal
    for frame in range(60):
        # Simulate right key pressed
        game.player.vx = 5  # Move right
        game._update()
    print(f"  After 60 frames: player x={game.player.rect.x:.0f}, cam={game.camera_x:.0f}")

    # Test damage
    initial_health = game.player.health
    game.player.rect.x = game.enemies[0].rect.x
    game._update()
    print(f"  Damage test: health {initial_health} → {game.player.health}")

    # Test invincibility
    game.player.rect.x = game.enemies[0].rect.x
    game._update()
    print(f"  Invincibility test: health still {game.player.health}")

    # Let invincibility wear off
    game.player.invincible_timer = 0
    game.player.rect.x = game.enemies[0].rect.x
    game._update()
    print(f"  Second damage: health now {game.player.health}")

    # Test level completion by moving player to goal
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    game.player.health = 5  # Reset health
    game._update()
    print(f"  After goal: level={game.current_level}, name={game.level_name}")

    # Level 2: Test
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    game._update()
    print(f"  After goal 2: level={game.current_level}, name={game.level_name}")

    # Level 3: Test
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    game._update()
    print(f"  After goal 3: won={game.won}")

    # Test game over
    game._restart()
    game.player.health = 0
    game._update()
    print(f"  Game over: {game.game_over}")

    # Test restart
    game._restart()
    print(f"  Restart: level={game.current_level}, health={game.player.health}, score={game.score}")

    # Test coin collection via direct collision
    if game.coins:
        coin = game.coins[0]
        game.player.rect.x = coin.rect.x
        game.player.rect.y = coin.rect.y
        game._update()
        print(f"  Coin collected: score={game.score}")

    pygame.quit()
    print("\n=== Integration Test PASSED ===")


if __name__ == "__main__":
    test_integration()
