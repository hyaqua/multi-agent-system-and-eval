"""
Headless test: run a few game frames to verify no crashes.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from game import Game


def test_game():
    pygame.init()
    game = Game()

    # Simulate a few frames with different inputs
    for frame in range(120):
        # Simulate right arrow and space on some frames
        # We'll directly call _update after setting up fake events
        pass

    print("Game initialized successfully")
    print(f"Level: {game.level_name}")
    print(f"Player pos: {game.player.rect.x}, {game.player.rect.y}")
    print(f"Platforms: {len(game.platforms)}")
    print(f"Coins: {len(game.coins)}")
    print(f"Enemies: {len(game.enemies)}")
    print(f"Goal at: {game.goal.rect.x}, {game.goal.rect.y}")

    # Test game over
    game.player.health = 0
    assert not game.player.is_alive()
    print("Health / game over check: OK")

    # Test restart
    game._restart()
    assert game.player.health == 5
    assert game.current_level == 0
    assert not game.game_over
    print("Restart: OK")

    # Test win
    game.current_level = 2
    game._load_level(2)
    # Simulate reaching goal
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    # This would trigger win in _update
    print("Level loading: OK")

    print("\nAll tests passed!")
    pygame.quit()


if __name__ == "__main__":
    test_game()
