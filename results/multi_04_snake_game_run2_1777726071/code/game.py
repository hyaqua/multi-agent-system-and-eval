"""
Game class: orchestrates game state (playing / game over), score,
high-level update logic, and rendering.
"""

import pygame
from constants import (
    GRID_WIDTH, GRID_HEIGHT, CELL_SIZE,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    COLOR_BACKGROUND, COLOR_GRID_LINE,
    COLOR_SNAKE_HEAD, COLOR_SNAKE_BODY,
    COLOR_FOOD, COLOR_TEXT, COLOR_GAME_OVER,
    MOVE_INTERVAL,
)
from snake import Snake
from food import Food


class Game:
    """Top-level game manager."""

    def __init__(self):
        self.snake = Snake()
        self.food = Food()
        self.score = 0
        self.game_over = False
        self._last_move_time = pygame.time.get_ticks()
        # Initial food placement
        self.food.respawn(self.snake.segments)

    def reset(self):
        """Reset the entire game state for a new round."""
        self.snake.reset()
        self.score = 0
        self.game_over = False
        self._last_move_time = pygame.time.get_ticks()
        self.food.respawn(self.snake.segments)

    def set_direction(self, dx, dy):
        """Forward a direction change to the snake."""
        if not self.game_over:
            self.snake.set_direction(dx, dy)

    def update(self):
        """Advance game state based on timer."""
        if self.game_over:
            return

        now = pygame.time.get_ticks()
        if now - self._last_move_time < MOVE_INTERVAL:
            return  # Not time to move yet
        self._last_move_time = now

        # Move the snake
        self.snake.move()

        # Check wall collision
        if self.snake.check_wall_collision():
            self.game_over = True
            return

        # Check self collision
        if self.snake.check_self_collision():
            self.game_over = True
            return

        # Check food collision
        if self.snake.head == self.food.position:
            self.snake.queue_growth()
            self.score += 1
            self.food.respawn(self.snake.segments)

    def draw(self, screen):
        """Render everything to the given surface."""
        # Background
        screen.fill(COLOR_BACKGROUND)

        # Grid lines
        self._draw_grid(screen)

        if self.game_over:
            self._draw_game_over(screen)
        else:
            # Draw food
            self._draw_cell(screen, self.food.position, COLOR_FOOD)

            # Draw snake
            for i, segment in enumerate(self.snake.segments):
                color = COLOR_SNAKE_HEAD if i == 0 else COLOR_SNAKE_BODY
                self._draw_cell(screen, segment, color)

            # Draw score
            self._draw_score(screen)

    def _draw_cell(self, screen, position, color):
        """Draw a single grid cell at *position* filled with *color*."""
        x, y = position
        rect = pygame.Rect(
            x * CELL_SIZE + 1,
            y * CELL_SIZE + 1,
            CELL_SIZE - 2,
            CELL_SIZE - 2,
        )
        pygame.draw.rect(screen, color, rect, border_radius=4)

    def _draw_grid(self, screen):
        """Draw faint grid lines."""
        for x in range(GRID_WIDTH + 1):
            pygame.draw.line(
                screen,
                COLOR_GRID_LINE,
                (x * CELL_SIZE, 0),
                (x * CELL_SIZE, WINDOW_HEIGHT),
            )
        for y in range(GRID_HEIGHT + 1):
            pygame.draw.line(
                screen,
                COLOR_GRID_LINE,
                (0, y * CELL_SIZE),
                (WINDOW_WIDTH, y * CELL_SIZE),
            )

    def _draw_score(self, screen):
        """Render score text top-centre."""
        font = pygame.font.Font(None, 36)
        text = font.render(f"Score: {self.score}", True, COLOR_TEXT)
        screen.blit(text, (10, 10))

    def _draw_game_over(self, screen):
        """Render game-over overlay with final score and restart hint."""
        font_large = pygame.font.Font(None, 72)
        font_small = pygame.font.Font(None, 36)

        # Dim overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        # "GAME OVER"
        go_text = font_large.render("GAME OVER", True, COLOR_GAME_OVER)
        go_rect = go_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40)
        )
        screen.blit(go_text, go_rect)

        # Final score
        score_text = font_small.render(
            f"Final Score: {self.score}", True, COLOR_TEXT
        )
        score_rect = score_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 20)
        )
        screen.blit(score_text, score_rect)

        # Restart instruction
        restart_text = font_small.render(
            "Press R to restart", True, COLOR_TEXT
        )
        restart_rect = restart_text.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60)
        )
        screen.blit(restart_text, restart_rect)
