"""
Classic Snake Game using Pygame.

Features:
- Grid-based playing field
- Arrow key controls
- Snake grows when eating food
- Score counter
- Game over on wall or self collision
- Game over screen with final score
- Restart on key press
"""

import pygame
import random
import sys

# ── Constants ────────────────────────────────────────────────────────────────
CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
SCREEN_WIDTH = CELL_SIZE * GRID_WIDTH
SCREEN_HEIGHT = CELL_SIZE * GRID_HEIGHT
FPS = 10

# Colors (R, G, B)
COLOR_BG = (20, 20, 20)
COLOR_GRID_LINE = (35, 35, 35)
COLOR_SNAKE_HEAD = (80, 180, 80)
COLOR_SNAKE_BODY = (60, 150, 60)
COLOR_FOOD = (220, 60, 60)
COLOR_TEXT = (255, 255, 255)
COLOR_SCORE_BG = (0, 0, 0, 180)


class Snake:
    """Represents the snake: its body, direction, and movement logic."""

    def __init__(self, start_x: int, start_y: int):
        # Body is a list of (x, y) grid positions; head is index 0
        self.body = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
        self.direction = (1, 0)   # moving right
        self.next_direction = (1, 0)
        self.alive = True

    @property
    def head(self):
        return self.body[0]

    def set_direction(self, dx: int, dy: int):
        """Queue a direction change, disallowing 180-degree reversals."""
        # Prevent reversing into yourself
        if (dx, dy) == (-self.direction[0], -self.direction[1]):
            return
        self.next_direction = (dx, dy)

    def update(self):
        """Advance the snake one step. Returns True if still alive."""
        if not self.alive:
            return False

        self.direction = self.next_direction
        dx, dy = self.direction
        new_head = (self.head[0] + dx, self.head[1] + dy)

        # Check wall collision
        if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
            self.alive = False
            return False

        # Check self collision (compare against current body excluding tail,
        # because the tail will move away — unless we just ate food, handled separately)
        if new_head in self.body[:-1]:
            self.alive = False
            return False

        # Move: insert new head, drop tail
        self.body.insert(0, new_head)
        # The tail is dropped here; if food was eaten the caller will skip dropping.
        return True

    def grow(self):
        """Called when the snake eats food; the tail is not dropped this frame."""
        # The new head was already inserted in update(); just keep the tail by
        # not popping. This method exists for clarity — the actual retention
        # is coordinated in the game loop.
        pass

    def drop_tail(self):
        """Remove the tail segment (called on normal moves, not when growing)."""
        self.body.pop()


class Game:
    """Main game state and loop."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Snake")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("consolas", 20)
        self.font_large = pygame.font.SysFont("consolas", 36, bold=True)
        self.reset()

    def reset(self):
        """Reset game state for a new round."""
        self.snake = Snake(GRID_WIDTH // 2, GRID_HEIGHT // 2)
        self.food = self._spawn_food()
        self.score = 0
        self.game_over = False
        self.pending_growth = 0  # number of segments still to grow

    def _spawn_food(self) -> tuple[int, int]:
        """Return a random unoccupied grid position."""
        while True:
            pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
            if pos not in self.snake.body:
                return pos

    def handle_events(self):
        """Process pygame events; returns False if user quits."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if self.game_over:
                    if event.key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
                        self.reset()
                else:
                    if event.key == pygame.K_UP:
                        self.snake.set_direction(0, -1)
                    elif event.key == pygame.K_DOWN:
                        self.snake.set_direction(0, 1)
                    elif event.key == pygame.K_LEFT:
                        self.snake.set_direction(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        self.snake.set_direction(1, 0)
                    elif event.key == pygame.K_ESCAPE:
                        return False
        return True

    def update(self):
        """Advance the game state by one tick."""
        if self.game_over:
            return

        # Move snake (inserts new head, returns False on death)
        if not self.snake.update():
            self.game_over = True
            return

        head = self.snake.head

        # Check food collision
        if head == self.food:
            self.score += 10
            self.pending_growth += 1
            self.food = self._spawn_food()

        # Handle tail: drop it unless we have pending growth
        if self.pending_growth > 0:
            self.pending_growth -= 1
            # Don't drop tail — snake grows
        else:
            self.snake.drop_tail()

    def draw_grid(self):
        """Draw the grid lines."""
        for x in range(0, SCREEN_WIDTH, CELL_SIZE):
            pygame.draw.line(self.screen, COLOR_GRID_LINE, (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, CELL_SIZE):
            pygame.draw.line(self.screen, COLOR_GRID_LINE, (0, y), (SCREEN_WIDTH, y))

    def draw_snake(self):
        """Draw the snake on the grid."""
        for i, (x, y) in enumerate(self.snake.body):
            rect = pygame.Rect(x * CELL_SIZE + 1, y * CELL_SIZE + 1,
                               CELL_SIZE - 2, CELL_SIZE - 2)
            color = COLOR_SNAKE_HEAD if i == 0 else COLOR_SNAKE_BODY
            pygame.draw.rect(self.screen, color, rect, border_radius=4)

    def draw_food(self):
        """Draw the food item."""
        x, y = self.food
        center = (x * CELL_SIZE + CELL_SIZE // 2, y * CELL_SIZE + CELL_SIZE // 2)
        radius = CELL_SIZE // 2 - 2
        pygame.draw.circle(self.screen, COLOR_FOOD, center, radius)

    def draw_score(self):
        """Draw the score at the top of the screen."""
        text = self.font_small.render(f"Score: {self.score}", True, COLOR_TEXT)
        # Semi-transparent background
        bg_rect = text.get_rect(topleft=(8, 4))
        bg_rect.inflate_ip(16, 8)
        bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surface.fill(COLOR_SCORE_BG)
        self.screen.blit(bg_surface, bg_rect.topleft)
        self.screen.blit(text, (12, 6))

    def draw_game_over(self):
        """Draw the game-over overlay."""
        # Dim the screen
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        self.screen.blit(dim, (0, 0))

        # Game over text
        go_text = self.font_large.render("GAME OVER", True, COLOR_FOOD)
        go_rect = go_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(go_text, go_rect)

        # Final score
        score_text = self.font_small.render(f"Final Score: {self.score}", True, COLOR_TEXT)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 15))
        self.screen.blit(score_text, score_rect)

        # Restart hint
        hint_text = self.font_small.render("Press R, SPACE, or ENTER to restart", True,
                                           (180, 180, 180))
        hint_rect = hint_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55))
        self.screen.blit(hint_text, hint_rect)

    def draw(self):
        """Render everything."""
        self.screen.fill(COLOR_BG)
        self.draw_grid()
        self.draw_snake()
        self.draw_food()
        self.draw_score()

        if self.game_over:
            self.draw_game_over()

        pygame.display.flip()

    def run(self):
        """Main game loop."""
        running = True
        while running:
            self.clock.tick(FPS)
            running = self.handle_events()
            self.update()
            self.draw()

        pygame.quit()
        sys.exit()


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    game = Game()
    game.run()
