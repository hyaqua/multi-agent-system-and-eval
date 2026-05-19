import pygame
from constants import (
    CELL_SIZE, GRID_WIDTH, GRID_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT,
    COLOR_BG, COLOR_GRID, COLOR_SNAKE_HEAD, COLOR_SNAKE_BODY,
    COLOR_FOOD, COLOR_WHITE, COLOR_OVERLAY,
    UP, DOWN, LEFT, RIGHT,
    MOVE_DELAY,
)
from snake import Snake
from food import Food


class Game:
    """Controller that manages snake, food, score, game state, and rendering."""

    def __init__(self):
        self.snake = Snake()
        self.food = Food()
        self.food.spawn(self.snake.segments)
        self.score = 0
        self.game_over = False
        self._last_move_time = pygame.time.get_ticks()
        self._font = pygame.font.SysFont(None, 36)
        self._big_font = pygame.font.SysFont(None, 48)

    def reset(self):
        """Reset the entire game to start a new round."""
        self.snake.reset()
        self.food.spawn(self.snake.segments)
        self.score = 0
        self.game_over = False
        self._last_move_time = pygame.time.get_ticks()

    def update(self):
        """Advance the game state by one frame."""
        if self.game_over:
            return

        now = pygame.time.get_ticks()
        if now - self._last_move_time < MOVE_DELAY:
            return  # not time to move yet

        self._last_move_time = now

        # Check if next head will hit food (before moving)
        dx, dy = self.snake.direction
        hx, hy = self.snake.head
        next_head = (hx + dx, hy + dy)

        if next_head == self.food.position:
            self.snake.grow()  # grow on *this* move

        # Move the snake
        new_head = self.snake.move()

        # Wall collision check
        hx, hy = new_head
        if hx < 0 or hx >= GRID_WIDTH or hy < 0 or hy >= GRID_HEIGHT:
            self.game_over = True
            return

        # Self collision check
        if self.snake.check_self_collision():
            self.game_over = True
            return

        # Food collision — already flagged grow above; now update score & respawn
        if new_head == self.food.position:
            self.score += 1
            self.food.spawn(self.snake.segments)

    def handle_event(self, event):
        """Process a single Pygame event."""
        if event.type == pygame.KEYDOWN:
            if self.game_over:
                if event.key == pygame.K_r:
                    self.reset()
                return

            # Arrow key direction changes
            if event.key == pygame.K_UP:
                self.snake.set_direction(UP)
            elif event.key == pygame.K_DOWN:
                self.snake.set_direction(DOWN)
            elif event.key == pygame.K_LEFT:
                self.snake.set_direction(LEFT)
            elif event.key == pygame.K_RIGHT:
                self.snake.set_direction(RIGHT)

    def draw(self, screen):
        """Render the entire game to the given surface."""
        # Fill background
        screen.fill(COLOR_BG)

        # Draw grid lines
        for x in range(0, WINDOW_WIDTH, CELL_SIZE):
            pygame.draw.line(screen, COLOR_GRID, (x, 0), (x, WINDOW_HEIGHT))
        for y in range(0, WINDOW_HEIGHT, CELL_SIZE):
            pygame.draw.line(screen, COLOR_GRID, (0, y), (WINDOW_WIDTH, y))

        # Draw snake
        segments = self.snake.segments
        for i, (sx, sy) in enumerate(segments):
            rect = pygame.Rect(sx * CELL_SIZE + 1, sy * CELL_SIZE + 1,
                               CELL_SIZE - 2, CELL_SIZE - 2)
            color = COLOR_SNAKE_HEAD if i == 0 else COLOR_SNAKE_BODY
            pygame.draw.rect(screen, color, rect, border_radius=4)

        # Draw food
        fx, fy = self.food.position
        if fx >= 0 and fy >= 0:
            food_rect = pygame.Rect(fx * CELL_SIZE + 2, fy * CELL_SIZE + 2,
                                    CELL_SIZE - 4, CELL_SIZE - 4)
            pygame.draw.rect(screen, COLOR_FOOD, food_rect, border_radius=6)

        # Draw score
        score_surf = self._font.render(f"Score: {self.score}", True, COLOR_WHITE)
        screen.blit(score_surf, (10, 10))

        # Draw game-over overlay
        if self.game_over:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT),
                                     pygame.SRCALPHA)
            overlay.fill(COLOR_OVERLAY)
            screen.blit(overlay, (0, 0))

            game_over_text = self._big_font.render(
                "GAME OVER", True, COLOR_WHITE
            )
            score_text = self._font.render(
                f"Score: {self.score}", True, COLOR_WHITE
            )
            restart_text = self._font.render(
                "Press R to restart", True, COLOR_WHITE
            )

            # Center the texts
            go_rect = game_over_text.get_rect(
                center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40)
            )
            sc_rect = score_text.get_rect(
                center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10)
            )
            rs_rect = restart_text.get_rect(
                center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 55)
            )

            screen.blit(game_over_text, go_rect)
            screen.blit(score_text, sc_rect)
            screen.blit(restart_text, rs_rect)
