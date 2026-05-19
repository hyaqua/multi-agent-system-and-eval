"""
Platformer Game - Main entry point
Initializes Pygame and runs the game loop.
"""
import pygame
from game import Game


def main():
    """Entry point for the platformer game."""
    pygame.init()
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
