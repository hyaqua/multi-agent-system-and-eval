import pygame
import sys
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
from game import Game


def main():
    """Entry point for the platformer game."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Platformer Adventure")

    game = Game(screen)
    game.run()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
