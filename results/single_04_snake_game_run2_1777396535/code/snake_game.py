import pygame
import random
import sys

# Constants
CELL_SIZE = 25
GRID_WIDTH = 20
GRID_HEIGHT = 20
WINDOW_WIDTH = CELL_SIZE * GRID_WIDTH
WINDOW_HEIGHT = CELL_SIZE * GRID_HEIGHT + 40  # Extra space for score

# Colors
BLACK = (0, 0, 0)
WHITE = (200, 200, 200)
GREEN = (0, 180, 0)
DARK_GREEN = (0, 140, 0)
RED = (220, 40, 40)
BLUE = (40, 40, 220)
GRAY = (60, 60, 60)
LIGHT_GRAY = (100, 100, 100)
YELLOW = (255, 255, 0)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


class SnakeGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Snake Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 32)
        self.big_font = pygame.font.Font(None, 48)
        self.reset_game()

    def reset_game(self):
        """Initialize or reset the game state."""
        # Snake starts in the middle, length 3, moving right
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.snake = [
            (start_x, start_y),
            (start_x - 1, start_y),
            (start_x - 2, start_y),
        ]
        self.direction = RIGHT
        self.next_direction = RIGHT
        self.food = self._spawn_food()
        self.score = 0
        self.game_over = False
        self.frame_counter = 0
        self.move_delay = 8  # Frames between moves (lower = faster)

    def _spawn_food(self):
        """Spawn food at a random unoccupied position."""
        while True:
            pos = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
            if pos not in self.snake:
                return pos

    def handle_events(self):
        """Process pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if self.game_over:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.reset_game()
                    continue

                # Direction changes — prevent reversing
                if event.key == pygame.K_UP and self.direction != DOWN:
                    self.next_direction = UP
                elif event.key == pygame.K_DOWN and self.direction != UP:
                    self.next_direction = DOWN
                elif event.key == pygame.K_LEFT and self.direction != RIGHT:
                    self.next_direction = LEFT
                elif event.key == pygame.K_RIGHT and self.direction != LEFT:
                    self.next_direction = RIGHT
        return True

    def update(self):
        """Update game state."""
        if self.game_over:
            return

        self.frame_counter += 1
        if self.frame_counter % self.move_delay != 0:
            return
        self.frame_counter = 0

        # Apply the queued direction
        self.direction = self.next_direction

        # Calculate new head position
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Check wall collision
        if new_head[0] < 0 or new_head[0] >= GRID_WIDTH or new_head[1] < 0 or new_head[1] >= GRID_HEIGHT:
            self.game_over = True
            return

        # Check self collision (skip the tail since it will move unless we eat food)
        if new_head in self.snake[:-1]:
            self.game_over = True
            return

        # Add new head
        self.snake.insert(0, new_head)

        # Check food collision
        if new_head == self.food:
            self.score += 10
            self.food = self._spawn_food()
        else:
            # Remove tail (snake moves forward without growing)
            self.snake.pop()

    def draw_grid(self):
        """Draw the grid lines."""
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + 40, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, GRAY, rect, 1)

    def draw_snake(self):
        """Draw the snake on the grid."""
        for i, (x, y) in enumerate(self.snake):
            rect = pygame.Rect(
                x * CELL_SIZE + 1,
                y * CELL_SIZE + 41,
                CELL_SIZE - 2,
                CELL_SIZE - 2,
            )
            if i == 0:
                # Head — slightly brighter
                color = GREEN
            else:
                # Body segments alternate slightly
                color = DARK_GREEN if i % 2 == 0 else GREEN
            pygame.draw.rect(self.screen, color, rect, border_radius=4)

    def draw_food(self):
        """Draw the food item."""
        x, y = self.food
        center_x = x * CELL_SIZE + CELL_SIZE // 2
        center_y = y * CELL_SIZE + 40 + CELL_SIZE // 2
        radius = CELL_SIZE // 2 - 2
        pygame.draw.circle(self.screen, RED, (center_x, center_y), radius)

    def draw_score(self):
        """Draw the score counter at the top."""
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 8))

    def draw_game_over(self):
        """Draw the game over overlay."""
        # Dim the background
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Game over text
        go_text = self.big_font.render("GAME OVER", True, RED)
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40))
        self.screen.blit(go_text, go_rect)

        # Final score
        score_text = self.font.render(f"Final Score: {self.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10))
        self.screen.blit(score_text, score_rect)

        # Restart instruction
        restart_text = self.font.render("Press SPACE or ENTER to restart", True, YELLOW)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50))
        self.screen.blit(restart_text, restart_rect)

    def render(self):
        """Render the entire frame."""
        self.screen.fill(BLACK)

        # Draw grid area background
        grid_bg = pygame.Rect(0, 40, WINDOW_WIDTH, WINDOW_HEIGHT - 40)
        pygame.draw.rect(self.screen, (20, 20, 20), grid_bg)

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
            running = self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)  # 60 FPS

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = SnakeGame()
    game.run()
