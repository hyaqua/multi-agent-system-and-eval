"""
Platformer Game - Main Game class
Manages game states, level loading, and game loop logic.
"""
import pygame
from constants import *
from player import Player
from camera import Camera
from level import Level
from ui import UI


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Platformer Adventure")
        self.clock = pygame.time.Clock()
        self.running = True

        self.state = MENU
        self.score = 0
        self.current_level = 1
        self.total_levels = 3
        self.level_complete_timer = 0
        self.level_complete_delay = 90  # frames

        self.ui = UI()
        self.level = Level()
        self.player = Player(0, 0)
        self.camera = Camera(WIDTH)

        # Load first level to set initial state
        self.load_level(self.current_level)

    def load_level(self, level_num):
        """Load a level by number."""
        filepath = f"level{level_num}.json"
        self.level = Level()
        self.level.level_number = level_num

        try:
            self.level.load(filepath)
        except FileNotFoundError:
            print(f"Level file {filepath} not found!")
            self.state = MENU
            return

        # Set up camera
        self.camera.set_level_width(self.level.width)

        # Position player at start
        start_x, start_y = self.level.player_start
        self.player.reset(start_x, start_y)

    def handle_events(self):
        """Process pygame events."""
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if self.state == MENU:
                    if event.key == pygame.K_RETURN:
                        self.start_game()
                    if event.key == pygame.K_q:
                        self.running = False

                elif self.state == PLAYING:
                    if event.key == pygame.K_SPACE:
                        self.player.jump()

                elif self.state == GAME_OVER:
                    if event.key == pygame.K_r:
                        self.restart_game()
                    if event.key == pygame.K_q:
                        self.running = False

                elif self.state == LEVEL_COMPLETE:
                    if event.key == pygame.K_RETURN:
                        if self.current_level >= self.total_levels:
                            self.restart_game()
                        else:
                            self.current_level += 1
                            self.load_level(self.current_level)
                            self.state = PLAYING

        # Continuous input during PLAYING state
        if self.state == PLAYING:
            self.player.handle_input(keys)

    def update(self):
        """Update game logic for one frame."""
        if self.state == PLAYING:
            # Update player
            self.player.update(self.level.platforms)

            # Update level objects
            self.level.update()

            # Check coin collisions
            collected = self.level.check_coin_collisions(self.player.rect)
            self.score += collected

            # Check enemy collisions
            if self.level.check_enemy_collisions(self.player.rect):
                self.player.take_damage()

            # Check goal collision
            if self.level.check_goal_collision(self.player.rect):
                self.state = LEVEL_COMPLETE
                self.level_complete_timer = 0

            # Check if player died
            if not self.player.alive:
                self.state = GAME_OVER

            # Update camera
            self.camera.update(self.player.rect)

        elif self.state == LEVEL_COMPLETE:
            self.level_complete_timer += 1
            # Auto-advance after delay (only if not last level)
            if (self.level_complete_timer >= self.level_complete_delay and
                    self.current_level < self.total_levels):
                self.current_level += 1
                self.load_level(self.current_level)
                self.state = PLAYING

    def render(self):
        """Render the current frame."""
        if self.state == MENU:
            self.ui.draw_menu(self.screen)

        elif self.state == PLAYING:
            # Clear screen
            self.screen.fill(SKY_BLUE)

            # Draw level objects with camera offset
            self.level.draw(self.screen, self.camera.camera_x)

            # Draw player with camera offset
            self.player.draw(self.screen, self.camera.camera_x)

            # Draw HUD (no camera offset)
            self.ui.draw_hud(self.screen, self.player, self.score, self.current_level)

        elif self.state == GAME_OVER:
            # Draw the game world frozen in background
            self.screen.fill(SKY_BLUE)
            self.level.draw(self.screen, self.camera.camera_x)
            self.player.draw(self.screen, self.camera.camera_x)
            self.ui.draw_hud(self.screen, self.player, self.score, self.current_level)
            # Draw game over overlay
            self.ui.draw_game_over(self.screen)

        elif self.state == LEVEL_COMPLETE:
            # Draw the game world frozen in background
            self.screen.fill(SKY_BLUE)
            self.level.draw(self.screen, self.camera.camera_x)
            self.player.draw(self.screen, self.camera.camera_x)
            self.ui.draw_hud(self.screen, self.player, self.score, self.current_level)
            # Draw level complete overlay
            self.ui.draw_level_complete(
                self.screen, self.current_level, self.total_levels
            )

        pygame.display.flip()

    def start_game(self):
        """Start a new game from level 1."""
        self.score = 0
        self.current_level = 1
        self.load_level(1)
        self.state = PLAYING

    def restart_game(self):
        """Restart from level 1."""
        self.start_game()

    def run(self):
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)

        pygame.quit()
