import pygame
import random
import sys

# Constants
GRID_SIZE = 20
CELL_SIZE = 25
GRID_WIDTH = 25
GRID_HEIGHT = 20
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE + 60  # Extra space for score

# Colors
BLACK = (0, 0, 0)
WHITE = (200, 200, 200)
GREEN = (0, 180, 0)
DARK_GREEN = (0, 140, 0)
RED = (220, 30, 30)
DARK_RED = (180, 20, 20)
GRAY = (40, 40, 40)
LIGHT_GRAY = (60, 60, 60)
YELLOW = (255, 255, 200)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Game states
PLAYING = 0
GAME_OVER = 1


class Snake:
    """Represents the snake in the game."""

    def __init__(self, x, y):
        self.body = [(x, y)]
        self.direction = RIGHT
        self.next_direction = RIGHT
        self.grow_pending = False

    def set_direction(self, new_direction):
        """Queue a direction change. Prevent reversing into self."""
        # Prevent the snake from going backwards
        opposite = (-self.direction[0], -self.direction[1])
        if new_direction != opposite:
            self.next_direction = new_direction

    def move(self):
        """Move the snake one step in the current direction."""
        self.direction = self.next_direction
        head_x, head_y = self.body[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Insert new head
        self.body.insert(0, new_head)

        if self.grow_pending:
            self.grow_pending = False
        else:
            # Remove tail
            self.body.pop()

        return new_head

    def grow(self):
        """Signal that the snake should grow on next move."""
        self.grow_pending = True

    def head(self):
        return self.body[0]

    def collides_with_self(self):
        """Check if the head collides with any other body segment."""
        head = self.head()
        return head in self.body[1:]

    def draw(self, screen):
        """Draw the snake on the screen."""
        for i, (x, y) in enumerate(self.body):
            px = x * CELL_SIZE
            py = y * CELL_SIZE + 60  # Offset for score area

            if i == 0:
                # Head - brighter with eyes
                color = GREEN
                pygame.draw.rect(screen, color, (px + 1, py + 1, CELL_SIZE - 2, CELL_SIZE - 2), border_radius=6)

                # Draw eyes
                eye_size = 4
                if self.direction == RIGHT:
                    eye1 = (px + CELL_SIZE - 7, py + 7)
                    eye2 = (px + CELL_SIZE - 7, py + CELL_SIZE - 7)
                elif self.direction == LEFT:
                    eye1 = (px + 7, py + 7)
                    eye2 = (px + 7, py + CELL_SIZE - 7)
                elif self.direction == UP:
                    eye1 = (px + 7, py + 7)
                    eye2 = (px + CELL_SIZE - 7, py + 7)
                else:  # DOWN
                    eye1 = (px + 7, py + CELL_SIZE - 7)
                    eye2 = (px + CELL_SIZE - 7, py + CELL_SIZE - 7)

                pygame.draw.circle(screen, BLACK, eye1, eye_size)
                pygame.draw.circle(screen, BLACK, eye2, eye_size)
            else:
                # Body segments
                color = DARK_GREEN
                pygame.draw.rect(screen, color, (px + 2, py + 2, CELL_SIZE - 4, CELL_SIZE - 4), border_radius=4)


class Food:
    """Represents a food item on the grid."""

    def __init__(self):
        self.position = (0, 0)

    def spawn(self, occupied_positions):
        """Place food at a random position not occupied by the snake."""
        available = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                if (x, y) not in occupied_positions:
                    available.append((x, y))

        if available:
            self.position = random.choice(available)
        else:
            # Snake fills the entire grid - player wins! (rare)
            self.position = None

    def draw(self, screen):
        """Draw the food on the screen."""
        if self.position is None:
            return
        x, y = self.position
        px = x * CELL_SIZE
        py = y * CELL_SIZE + 60  # Offset for score area

        # Draw a glowing food item
        # Outer glow
        pygame.draw.rect(screen, YELLOW, (px - 1, py - 1, CELL_SIZE + 2, CELL_SIZE + 2), border_radius=7)
        # Main body
        pygame.draw.rect(screen, RED, (px + 3, py + 3, CELL_SIZE - 6, CELL_SIZE - 6), border_radius=5)
        # Highlight
        pygame.draw.circle(screen, (255, 150, 150), (px + CELL_SIZE // 2 - 2, py + CELL_SIZE // 2 - 3), 4)


class Game:
    """Main game class."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Snake Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 24)

        self.reset()

    def reset(self):
        """Reset the game to initial state."""
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.snake = Snake(start_x, start_y)
        self.food = Food()
        self.food.spawn(self.snake.body)
        self.score = 0
        self.state = PLAYING
        self.move_timer = 0
        self.move_delay = 130  # milliseconds between moves

    def handle_events(self):
        """Process pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if self.state == PLAYING:
                    if event.key == pygame.K_UP or event.key == pygame.K_w:
                        self.snake.set_direction(UP)
                    elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                        self.snake.set_direction(DOWN)
                    elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                        self.snake.set_direction(LEFT)
                    elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                        self.snake.set_direction(RIGHT)
                    elif event.key == pygame.K_ESCAPE:
                        return False

                elif self.state == GAME_OVER:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.reset()
                    elif event.key == pygame.K_ESCAPE:
                        return False

        return True

    def update(self, dt):
        """Update game state."""
        if self.state != PLAYING:
            return

        self.move_timer += dt
        if self.move_timer >= self.move_delay:
            self.move_timer -= self.move_delay
            self._do_move()

    def _do_move(self):
        """Execute one snake move and check collisions."""
        new_head = self.snake.move()

        # Check wall collision
        hx, hy = new_head
        if hx < 0 or hx >= GRID_WIDTH or hy < 0 or hy >= GRID_HEIGHT:
            self.state = GAME_OVER
            return

        # Check self collision
        if self.snake.collides_with_self():
            self.state = GAME_OVER
            return

        # Check food collision
        if new_head == self.food.position:
            self.snake.grow()
            self.score += 10
            self.food.spawn(self.snake.body)

            # Speed up slightly as score increases
            self.move_delay = max(60, 130 - (self.score // 50) * 5)

    def draw_grid(self):
        """Draw the playing field grid."""
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                px = x * CELL_SIZE
                py = y * CELL_SIZE + 60  # Offset for score area
                # Checkerboard pattern
                if (x + y) % 2 == 0:
                    color = GRAY
                else:
                    color = LIGHT_GRAY
                pygame.draw.rect(self.screen, color, (px, py, CELL_SIZE, CELL_SIZE))

    def draw_score(self):
        """Draw the score display at the top."""
        # Score background
        pygame.draw.rect(self.screen, BLACK, (0, 0, WINDOW_WIDTH, 60))

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (20, 15))

        # Draw a subtle divider
        pygame.draw.line(self.screen, WHITE, (0, 58), (WINDOW_WIDTH, 58), 2)

    def draw_game_over(self):
        """Draw the game over overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Game Over text
        go_text = self.big_font.render("GAME OVER", True, RED)
        go_rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40))
        self.screen.blit(go_text, go_rect)

        # Final score
        score_text = self.font.render(f"Final Score: {self.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10))
        self.screen.blit(score_text, score_rect)

        # Restart prompt
        restart_text = self.small_font.render("Press SPACE or ENTER to restart", True, YELLOW)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50))
        self.screen.blit(restart_text, restart_rect)

        quit_text = self.small_font.render("Press ESC to quit", True, LIGHT_GRAY)
        quit_rect = quit_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 75))
        self.screen.blit(quit_text, quit_rect)

    def render(self):
        """Render the full frame."""
        self.screen.fill(BLACK)

        # Draw grid
        self.draw_grid()

        # Draw food
        self.food.draw(self.screen)

        # Draw snake
        self.snake.draw(self.screen)

        # Draw score
        self.draw_score()

        # Draw game over overlay if needed
        if self.state == GAME_OVER:
            self.draw_game_over()

        pygame.display.flip()

    def run(self):
        """Main game loop."""
        running = True
        while running:
            dt = self.clock.tick(60)  # 60 FPS
            running = self.handle_events()
            self.update(dt)
            self.render()

        pygame.quit()
        sys.exit()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
