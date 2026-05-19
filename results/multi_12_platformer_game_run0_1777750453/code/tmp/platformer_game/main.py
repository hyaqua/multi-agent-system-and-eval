# main.py - Entry point, game loop, state manager

import pygame
import sys
import os
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, BLACK, WHITE, SKY_BLUE
)
from sprites import Player
from level import LevelLoader
from camera import Camera
from gui import (
    draw_hud, draw_menu, draw_game_over,
    draw_level_complete, draw_victory
)


def main():
    """Main game entry point."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Platformer Game")
    clock = pygame.time.Clock()

    # Fonts
    title_font = pygame.font.Font(None, 72)
    font = pygame.font.Font(None, 30)

    # State
    state = "menu"

    # Level tracking
    level_index = 0
    level_files = [
        os.path.join("levels", "level1.json"),
        os.path.join("levels", "level2.json"),
        os.path.join("levels", "level3.json"),
    ]
    total_coins_collected = 0

    # Sprite groups (populated by load_level)
    all_sprites = pygame.sprite.Group()
    platforms = pygame.sprite.Group()
    coins = pygame.sprite.Group()
    enemies = pygame.sprite.Group()
    goals = pygame.sprite.Group()
    player = None
    camera = None
    level = None

    def reset_game():
        """Reset all game progress (for restart from menu)."""
        nonlocal level_index, total_coins_collected
        level_index = 0
        total_coins_collected = 0

    def load_level(index):
        """Load a level by index, returning (level, player, camera, sprite_groups)."""
        nonlocal total_coins_collected

        if index >= len(level_files):
            return None, None, None, None, None, None, None

        level_path = os.path.join(os.path.dirname(__file__), level_files[index])
        if not os.path.exists(level_path):
            # Try relative to cwd
            level_path = level_files[index]

        level = LevelLoader.load(level_path)

        # Create player at start position
        player = Player(*level.player_start)

        # Build unified sprite groups
        all_sprites = pygame.sprite.Group()
        all_sprites.add(player)
        for sprite in level.all_sprites:
            all_sprites.add(sprite)

        # Create camera
        camera = Camera(level.world_width, level.world_height)

        return level, player, camera, all_sprites, level.platforms, level.coins, level.enemies

    # Main game loop
    running = True
    while running:
        # --- Event handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if state == "menu":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        state = "playing"
                        reset_game()
                        result = load_level(level_index)
                        if result[0] is not None:
                            level, player, camera, all_sprites, platforms, coins, enemies = result
                            goals = level.goals

            elif state == "playing":
                pass  # Key handling done via pygame.key.get_pressed()

            elif state == "game_over":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        # Restart from level 1
                        state = "playing"
                        reset_game()
                        result = load_level(level_index)
                        if result[0] is not None:
                            level, player, camera, all_sprites, platforms, coins, enemies = result
                            goals = level.goals
                    elif event.key == pygame.K_m:
                        state = "menu"

            elif state == "level_complete":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        total_coins_collected += player.coins
                        level_index += 1
                        result = load_level(level_index)
                        if result[0] is not None:
                            level, player, camera, all_sprites, platforms, coins, enemies = result
                            goals = level.goals
                            state = "playing"
                        else:
                            # No more levels — victory!
                            state = "victory"

            elif state == "victory":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        state = "playing"
                        reset_game()
                        result = load_level(level_index)
                        if result[0] is not None:
                            level, player, camera, all_sprites, platforms, coins, enemies = result
                            goals = level.goals
                    elif event.key == pygame.K_m:
                        state = "menu"

        # --- Update ---
        keys = pygame.key.get_pressed()

        if state == "playing" and player is not None:
            # Update player
            player.update(platforms, enemies, coins, keys)

            # Update enemies
            for enemy in enemies:
                enemy.update(platforms)

            # Update camera to follow player
            camera.update(player)

            # Check goal collision
            goal_hits = pygame.sprite.spritecollide(player, goals, False)
            if goal_hits:
                state = "level_complete"

            # Check if player fell off the world
            if player.rect.top > level.world_height + 100:
                player.health = 0

            # Check death
            if player.health <= 0:
                state = "game_over"

        # --- Draw ---
        if state == "playing" and player is not None:
            # Draw sky background
            screen.fill(SKY_BLUE)

            # Draw all sprites with camera offset
            for sprite in all_sprites:
                screen.blit(sprite.image, camera.apply(sprite.rect))

            # Draw HUD (not affected by camera)
            draw_hud(screen, player, font)

        elif state == "menu":
            draw_menu(screen, title_font, font)

        elif state == "game_over":
            coins_earned = player.coins if player else 0
            draw_game_over(screen, title_font, font, total_coins_collected + coins_earned)

        elif state == "level_complete":
            draw_level_complete(screen, title_font, font, player.coins, level.name if level else "")

        elif state == "victory":
            draw_victory(screen, title_font, font, total_coins_collected)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
