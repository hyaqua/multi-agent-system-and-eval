"""
Comprehensive headless test simulating gameplay.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from game import Game
from player import Player
from platform import Platform
from coin import Coin
from enemy import Enemy
from goal import Goal


class MockKeys:
    """Mock pygame key state that supports indexing."""
    def __init__(self, left=False, right=False, space=False):
        self.left = left
        self.right = right
        self.space = space

    def __getitem__(self, key):
        if key == pygame.K_LEFT or key == pygame.K_a:
            return self.left
        if key == pygame.K_RIGHT or key == pygame.K_d:
            return self.right
        if key == pygame.K_SPACE or key == pygame.K_UP or key == pygame.K_w:
            return self.space
        return 0

    def __len__(self):
        return 512  # big enough for any pygame key constant


def simulate_key_state(left=False, right=False, space=False):
    """Create a mock key state."""
    return MockKeys(left, right, space)


def test_core_mechanics():
    pygame.init()

    # Test 1: Player physics
    print("=== Test 1: Player Physics ===")
    player = Player(100, 400)
    platform = Platform(0, 500, 300)  # ground from 0 to 300

    # Simulate gravity pulling player down
    for _ in range(30):
        keys = simulate_key_state()
        player.update(keys, [platform], [], [])

    assert player.on_ground, "Player should be on ground after falling"
    assert player.rect.bottom == platform.rect.top, "Player should be on platform top"
    print("  Gravity & landing: OK")

    # Test 2: Player jump
    print("=== Test 2: Jumping ===")
    keys = simulate_key_state(space=True)
    player.update(keys, [platform], [], [])
    assert player.vy < 0, "Player should have upward velocity after jump"
    print("  Jump initiated: OK")

    # Let player land
    for _ in range(60):
        keys = simulate_key_state()
        player.update(keys, [platform], [], [])

    assert player.on_ground, "Player should land back on platform"
    print("  Jump & land: OK")

    # Test 3: Coin collection
    print("=== Test 3: Coin Collection ===")
    player2 = Player(100, 300)
    platform2 = Platform(0, 500, 300)
    coin = Coin(250, 460)  # coin at x=250, player at x=100 won't hit it while falling
    coins = [coin]

    # Let player fall to ground - coin should not be collected (different x position)
    for _ in range(30):
        keys = simulate_key_state()
        collected = player2.update(keys, [platform2], [], coins)
    assert len(coins) == 1, "Coin should not be collected yet (different x)"

    # Move player right toward coin
    for _ in range(30):
        keys = simulate_key_state(right=True)
        collected += player2.update(keys, [platform2], [], coins)
    assert len(coins) == 0, "Coin should be collected when player walks into it"
    assert collected >= 1, "Should report at least 1 coin collected"
    print("  Coin collection: OK")

    # Test 4: Enemy damage
    print("=== Test 4: Enemy Damage ===")
    player3 = Player(100, 400)
    platform3 = Platform(0, 500, 300)
    enemy = Enemy(200, 500)  # enemy on platform
    enemies = [enemy]

    # Fall to ground
    for _ in range(30):
        player3.update(simulate_key_state(), [platform3], enemies, [])

    initial_health = player3.health
    # Move into enemy
    player3.rect.x = enemy.rect.x
    player3.update(simulate_key_state(), [platform3], enemies, [])
    assert player3.health == initial_health - 1, "Player should take damage"
    assert player3.invincible_timer > 0, "Player should be invincible after hit"
    print("  Enemy damage: OK")

    # Test 5: Invincibility frames
    print("=== Test 5: Invincibility ===")
    # Try hitting again during invincibility
    health_before = player3.health
    player3.update(simulate_key_state(), [platform3], enemies, [])
    assert player3.health == health_before, "Should not take damage while invincible"
    print("  Invincibility frames: OK")

    # Expire invincibility
    player3.invincible_timer = 0
    player3.update(simulate_key_state(), [platform3], enemies, [])
    assert player3.health == health_before - 1, "Should take damage after invincibility expires"
    print("  Invincibility expiry: OK")

    # Test 6: Game over on zero health
    print("=== Test 6: Game Over ===")
    player4 = Player(100, 400)
    platform4 = Platform(0, 500, 300)
    enemy2 = Enemy(200, 500)

    player4.health = 1
    player4.rect.x = enemy2.rect.x
    for _ in range(30):
        player4.update(simulate_key_state(), [platform4], [enemy2], [])
    player4.invincible_timer = 0
    player4.update(simulate_key_state(), [platform4], [enemy2], [])
    assert not player4.is_alive(), "Player should die when health reaches 0"
    print("  Game over on death: OK")

    # Test 7: Goal / Level completion
    print("=== Test 7: Goal Detection ===")
    game = Game()
    # Place player at goal
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    game._update()  # This triggers goal collision → next level
    assert game.current_level == 1, "Should advance to level 2"
    print("  Level advancement: OK")

    # Test 8: Win after all levels
    print("=== Test 8: Win Condition ===")
    game.current_level = 2
    game._load_level(2)
    game.player.rect.x = game.goal.rect.x
    game.player.rect.y = game.goal.rect.y
    game._update()
    assert game.won, "Should trigger win after final level"
    print("  Win condition: OK")

    # Test 9: Camera follows player
    print("=== Test 9: Camera ===")
    game2 = Game()
    initial_cam = game2.camera_x
    game2.player.rect.x = 600
    for _ in range(30):
        game2._update()
    assert game2.camera_x > initial_cam, "Camera should move right when player moves right"
    print("  Camera scrolling: OK")

    # Test 10: All levels load correctly
    print("=== Test 10: Level Loading ===")
    game3 = Game()
    for i in range(3):
        game3._load_level(i)
        assert len(game3.platforms) > 0, f"Level {i+1} should have platforms"
        assert len(game3.coins) > 0, f"Level {i+1} should have coins"
        assert len(game3.enemies) > 0, f"Level {i+1} should have enemies"
        assert game3.goal is not None, f"Level {i+1} should have a goal"
    print("  All levels load: OK")

    pygame.quit()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    test_core_mechanics()
