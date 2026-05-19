"""
main.py – Application entry point for the Tetris game.

Handles: Pygame setup, game loop, event handling, state transitions.
"""

import sys
import pygame
from constants import (
    FPS, SCREEN_W, SCREEN_H,
    KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL,
)
from game import Game
from renderer import init_screen, render


def main():
    """Run the Tetris game."""
    pygame.init()
    pygame.key.set_repeat(KEY_REPEAT_DELAY, KEY_REPEAT_INTERVAL)

    screen = init_screen()
    clock = pygame.time.Clock()

    game = Game()

    running = True

    while running:
        dt_ms = clock.tick(FPS)  # milliseconds since last frame

        # --- Event handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if game.game_over:
                    if event.key == pygame.K_r:
                        game = Game()  # restart
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                else:
                    if event.key == pygame.K_LEFT:
                        game.move(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        game.move(1, 0)
                    elif event.key == pygame.K_DOWN:
                        game.move(0, 1)
                    elif event.key == pygame.K_UP:
                        game.rotate()
                    elif event.key == pygame.K_SPACE:
                        game.hard_drop()
                    elif event.key == pygame.K_ESCAPE:
                        running = False

        # --- Update ---
        game.update(dt_ms)

        # --- Render ---
        render(screen, game)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
