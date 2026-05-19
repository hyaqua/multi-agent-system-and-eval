import pygame
from settings import FPS, COLOR_BLACK
from level import Level
from player import Player
from camera import Camera
from ui import (
    draw_coin_counter, draw_health_bar, draw_game_over,
    draw_level_complete, draw_level_title
)


class Game:
    """Main game class managing states, levels, and the game loop."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True

        # Game state: "menu", "playing", "level_transition", "game_over"
        self.state = "playing"

        # Level management
        self.level_files = ["level1.json", "level2.json", "level3.json"]
        self.current_level_index = 0
        self.level: Level | None = None
        self.player: Player | None = None
        self.camera: Camera | None = None

        # Fonts
        self.font = pygame.font.Font(None, 36)
        self.large_font = pygame.font.Font(None, 72)
        self.small_font = pygame.font.Font(None, 24)

        # Level transition
        self.transition_timer = 0
        self.transition_duration = 90  # 1.5 seconds at 60 FPS
        self.next_level_name = ""

        # Level title display
        self.title_timer = 0
        self.title_duration = 120  # 2 seconds

        # Load first level
        self._load_level(self.current_level_index)

    def _load_level(self, index: int):
        """Load a level by index."""
        if index >= len(self.level_files):
            # All levels complete! Loop back to first level
            index = 0
            self.current_level_index = 0

        self.current_level_index = index
        level_file = self.level_files[index]
        self.level = Level(level_file)

        # Create player at start position
        start_x, start_y = self.level.player_start
        if self.player:
            # Carry over coins but reset health and position
            coins = self.player.coins_collected
            self.player = Player(start_x, start_y)
            self.player.coins_collected = coins
        else:
            self.player = Player(start_x, start_y)

        # Create camera
        self.camera = Camera(self.level.level_width)

        # Show level title
        self.title_timer = self.title_duration

        self.state = "playing"

    def _next_level(self):
        """Advance to the next level."""
        self.current_level_index += 1
        if self.current_level_index >= len(self.level_files):
            # All levels complete! Wrap around
            self.current_level_index = 0
            # Reset coins on full game completion
            if self.player:
                self.player.coins_collected = 0

        self.next_level_name = f"Level {self.current_level_index + 1}"
        self.state = "level_transition"
        self.transition_timer = self.transition_duration

    def _restart_game(self):
        """Restart the game from the first level."""
        self.current_level_index = 0
        self.player = None  # Force fresh player
        self._load_level(0)

    def handle_events(self):
        """Process pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if self.state == "game_over":
                    self._restart_game()
                elif self.state == "level_transition":
                    # Skip transition
                    pass

    def update(self):
        """Update game logic."""
        if self.state == "playing":
            self._update_playing()
        elif self.state == "level_transition":
            self.transition_timer -= 1
            if self.transition_timer <= 0:
                self._load_level(self.current_level_index)
        elif self.state == "game_over":
            pass  # Wait for input

    def _update_playing(self):
        """Update logic during gameplay."""
        if not self.player or not self.level or not self.camera:
            return

        # Handle input
        self.player.handle_input()

        # Update player
        platform_rects = self.level.get_platform_rects()
        self.player.update(platform_rects)

        # Update level entities
        self.level.update()

        # Check coin collisions
        active_coins = self.level.get_active_coins()
        self.player.check_coin_collisions(active_coins)

        # Check enemy collisions
        self.player.check_enemy_collisions(self.level.enemies)

        # Check goal collision
        if self.player.check_goal_collision(self.level.goal_rect):
            self._next_level()

        # Check death
        if self.player.is_dead():
            self.state = "game_over"

        # Update camera
        self.camera.update(self.player.rect)

        # Update title timer
        if self.title_timer > 0:
            self.title_timer -= 1

    def render(self):
        """Render the current frame."""
        self.screen.fill(COLOR_BLACK)

        if self.state == "game_over":
            self._render_game_over()
        elif self.state == "level_transition":
            self._render_level_transition()
        else:
            self._render_playing()

        pygame.display.flip()

    def _render_playing(self):
        """Render the playing state."""
        if not self.level or not self.player or not self.camera:
            return

        camera_offset = self.camera.get_offset()

        # Draw level
        self.level.draw(self.screen, camera_offset)

        # Draw player
        self.player.draw(self.screen, camera_offset)

        # Draw HUD (fixed, not affected by camera)
        draw_coin_counter(self.screen, self.font, self.player.coins_collected)
        draw_health_bar(self.screen, self.player.health, self.player.max_health)

        # Draw level title
        if self.title_timer > 0:
            alpha = min(255, int((self.title_timer / self.title_duration) * 255 * 2))
            if self.title_timer > self.title_duration - 60:
                alpha = min(255, int(((self.title_duration - self.title_timer) / 60) * 255))
            draw_level_title(self.screen, self.large_font, self.level.name, alpha)

    def _render_game_over(self):
        """Render the game over screen."""
        if self.level and self.player and self.camera:
            camera_offset = self.camera.get_offset()
            self.level.draw(self.screen, camera_offset)
            self.player.draw(self.screen, camera_offset)
            draw_coin_counter(self.screen, self.font, self.player.coins_collected)
            draw_health_bar(self.screen, self.player.health, self.player.max_health)

        draw_game_over(self.screen, self.large_font, self.small_font)

    def _render_level_transition(self):
        """Render the level transition screen."""
        if self.level and self.player and self.camera:
            camera_offset = self.camera.get_offset()
            self.level.draw(self.screen, camera_offset)
            self.player.draw(self.screen, camera_offset)
            draw_coin_counter(self.screen, self.font, self.player.coins_collected)
            draw_health_bar(self.screen, self.player.health, self.player.max_health)

        draw_level_complete(self.screen, self.large_font, self.next_level_name)

    def run(self):
        """Main game loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)
