"""
Main entry point: initialises Pygame, creates the Game instance,
runs the event and game loop.
"""

import sys
import pygame
from constants import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from game import Game


def main():
    """Launch the Snake game."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()

    game = Game()

    running = True
    while running:
        # ---- Event handling ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if game.game_over:
                    if event.key == pygame.K_r:
                        game.reset()
                else:
                    # Arrow keys change direction
                    if event.key == pygame.K_UP:
                        game.set_direction(0, -1)
                    elif event.key == pygame.K_DOWN:
                        game.set_direction(0, 1)
                    elif event.key == pygame.K_LEFT:
                        game.set_direction(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        game.set_direction(1, 0)
                    elif event.key == pygame.K_r:
                        game.reset()

        # ---- Update ----
        game.update()

        # ---- Draw ----
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
