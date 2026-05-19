"""
Snake Game — single-file implementation using Pygame.
"""

import pygame
import random
import sys
from collections import deque

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELL_SIZE = 20
CELL_COUNT_X = 30  # 600px wide
CELL_COUNT_Y = 30  # 600px tall
WIDTH = CELL_COUNT_X * CELL_SIZE
HEIGHT = CELL_COUNT_Y * CELL_SIZE
FPS = 12  # classic snake speed

# Colors
COLOR_BG = (15, 15, 15)
COLOR_GRID = (30, 30, 30)
COLOR_SNAKE_HEAD = (100, 200, 100)
COLOR_SNAKE_BODY = (70, 160, 70)
COLOR_FOOD = (220, 70, 70)
COLOR_TEXT = (240, 240, 240)
COLOR_OVERLAY = (0, 0, 0, 180)

# Directions as (dx, dy) vectors
DIRECTIONS = {
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
}

# Opposite direction map — prevent 180° turns
OPPOSITE = {
    (0, -1): (0, 1),
    (0, 1): (0, -1),
    (-1, 0): (1, 0),
    (1, 0): (-1, 0),
}


# ============================================================================
# Classes
# ============================================================================

class Snake:
    """Holds the snake's body segments, direction, and movement logic."""

    def __init__(self):
        # Start in the middle, facing right
        start_x = CELL_COUNT_X // 2
        start_y = CELL_COUNT_Y // 2
        self.direction = (1, 0)  # right
        # Three segments: head (index 0), middle, tail
        self.body = deque([
            [start_x, start_y],
            [start_x - 1, start_y],
            [start_x - 2, start_y],
        ])
        self._growing = False

    @property
    def head(self):
        return self.body[0]

    def set_direction(self, key):
        """Attempt to change direction; 180° reversal is ignored."""
        new_dir = DIRECTIONS.get(key)
        if new_dir is None:
            return
        if new_dir == OPPOSITE[self.direction]:
            return  # ignore reversal
        self.direction = new_dir

    def move(self):
        """Advance the snake one step. Returns False if self-collision detected."""
        hx, hy = self.head
        dx, dy = self.direction
        new_head = [hx + dx, hy + dy]

        # Check self-collision: new_head must not already exist in body
        # (except for the tail that will be popped if not growing)
        if not self._growing and self.body:
            check_body = list(self.body)[:-1]  # tail will be removed
        else:
            check_body = list(self.body)

        if new_head in check_body:
            return False  # self-collision

        # Insert new head
        self.body.appendleft(new_head)

        if self._growing:
            self._growing = False
        else:
            self.body.pop()  # remove tail

        return True

    def grow(self):
        """Signal that the snake should grow on its next move."""
        self._growing = True

    def occupies(self, pos):
        """Check whether a grid position is occupied by the snake."""
        return list(pos) in self.body

    def draw(self, screen):
        """Render the snake on the given surface."""
        for i, segment in enumerate(self.body):
            rect = pygame.Rect(
                segment[0] * CELL_SIZE,
                segment[1] * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE,
            )
            color = COLOR_SNAKE_HEAD if i == 0 else COLOR_SNAKE_BODY
            pygame.draw.rect(screen, color, rect)
            # Slightly darker border for definition
            pygame.draw.rect(screen, (0, 0, 0), rect, 1)


class Food:
    """Manages placement of a single food item on the grid."""

    def __init__(self, snake):
        self.position = [0, 0]
        self.respawn(snake)

    def respawn(self, snake):
        """Place food at a random unoccupied grid cell."""
        while True:
            x = random.randint(0, CELL_COUNT_X - 1)
            y = random.randint(0, CELL_COUNT_Y - 1)
            if not snake.occupies([x, y]):
                self.position = [x, y]
                break

    def draw(self, screen):
        """Render the food item."""
        rect = pygame.Rect(
            self.position[0] * CELL_SIZE,
            self.position[1] * CELL_SIZE,
            CELL_SIZE,
            CELL_SIZE,
        )
        pygame.draw.rect(screen, COLOR_FOOD, rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 1)


# ============================================================================
# Game orchestrator
# ============================================================================

class Game:
    """Top-level game that manages the loop, state, and rendering."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 72)

        self.snake = Snake()
        self.food = Food(self.snake)
        self.score = 0
        self.state = "PLAYING"  # PLAYING or GAME_OVER

    def run(self):
        """Main game loop."""
        while True:
            self._handle_events()

            if self.state == "PLAYING":
                self._update()

            self._draw()
            self.clock.tick(FPS)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if self.state == "PLAYING":
                    if event.key in DIRECTIONS:
                        self.snake.set_direction(event.key)
                elif self.state == "GAME_OVER":
                    if event.key == pygame.K_r or event.key == pygame.K_SPACE:
                        self._restart()

    # ------------------------------------------------------------------
    # Update (game logic)
    # ------------------------------------------------------------------

    def _update(self):
        # Attempt to move; check self-collision
        if not self.snake.move():
            self.state = "GAME_OVER"
            return

        # Wall collision
        hx, hy = self.snake.head
        if hx < 0 or hx >= CELL_COUNT_X or hy < 0 or hy >= CELL_COUNT_Y:
            self.state = "GAME_OVER"
            return

        # Food collision
        if self.snake.head == self.food.position:
            self.snake.grow()
            self.score += 1
            self.food.respawn(self.snake)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _draw_grid(self):
        """Draw faint grid lines for visual clarity."""
        for x in range(0, WIDTH + 1, CELL_SIZE):
            pygame.draw.line(self.screen, COLOR_GRID, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT + 1, CELL_SIZE):
            pygame.draw.line(self.screen, COLOR_GRID, (0, y), (WIDTH, y))

    def _draw_score(self):
        score_surf = self.font.render(f"Score: {self.score}", True, COLOR_TEXT)
        self.screen.blit(score_surf, (10, 10))

    def _draw_game_over(self):
        """Semi-transparent overlay with game-over text and final score."""
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill(COLOR_OVERLAY)
        self.screen.blit(overlay, (0, 0))

        go_surf = self.big_font.render("GAME OVER", True, COLOR_FOOD)
        go_rect = go_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30))
        self.screen.blit(go_surf, go_rect)

        score_surf = self.font.render(
            f"Score: {self.score}", True, COLOR_TEXT
        )
        score_rect = score_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
        self.screen.blit(score_surf, score_rect)

        restart_surf = self.font.render(
            "Press R or SPACE to restart", True, (180, 180, 180)
        )
        restart_rect = restart_surf.get_rect(
            center=(WIDTH // 2, HEIGHT // 2 + 70)
        )
        self.screen.blit(restart_surf, restart_rect)

    def _draw(self):
        self.screen.fill(COLOR_BG)
        self._draw_grid()
        self.food.draw(self.screen)
        self.snake.draw(self.screen)
        self._draw_score()

        if self.state == "GAME_OVER":
            self._draw_game_over()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Restart
    # ------------------------------------------------------------------

    def _restart(self):
        self.snake = Snake()
        self.food = Food(self.snake)
        self.score = 0
        self.state = "PLAYING"


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    Game().run()
