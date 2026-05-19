"""Tetris Game - Entry Point."""

import sys
import pygame

import settings
from game import Game
from display import Display


def main():
    """Initialize and run the Tetris game."""
    pygame.init()
    pygame.display.set_caption("Tetris")

    screen = pygame.display.set_mode((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
    clock = pygame.time.Clock()
    game = Game()
    display = Display(screen)

    running = True

    while running:
        dt = clock.tick(settings.FPS) / 1000.0  # delta time in seconds

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if game.game_over:
                    if event.key == pygame.K_r:
                        game.reset()
                    elif event.key == pygame.K_q:
                        running = False
                else:
                    game.handle_input(event)
            elif event.type == pygame.KEYUP:
                if not game.game_over:
                    game.handle_input(event)

        # Update game state
        game.update(dt)

        # Draw everything
        state = game.get_state()
        display.draw(state)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
