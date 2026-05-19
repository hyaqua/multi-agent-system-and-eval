"""
Tetris Game - Classic Tetris implemented with Pygame
All 7 standard tetrominoes, scoring, levels, next-piece preview, game over.
"""

import pygame
import random
import sys

# ── Initialize Pygame ──────────────────────────────────────────────────────
pygame.init()

# ── Constants ──────────────────────────────────────────────────────────────
SCREEN_WIDTH = 500
SCREEN_HEIGHT = 620
BOARD_COLS = 10
BOARD_ROWS = 20
CELL_SIZE = 30
BOARD_X = 30
BOARD_Y = 30
PREVIEW_X = 360
PREVIEW_Y = 80

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (30, 30, 30)
BOARD_BG = (25, 25, 25)
BORDER_LIGHT = (100, 100, 100)
BORDER_DARK = (55, 55, 55)
GRID_COLOR = (40, 40, 40)
PANEL_BG = (28, 28, 28)
TEXT_COLOR = (210, 210, 210)
TEXT_DIM = (130, 130, 130)

# Tetromino colors — index matches piece index 0..6
PIECE_COLORS = [
    (0, 255, 255),      # I - Cyan
    (255, 255, 0),      # O - Yellow
    (160, 0, 160),      # T - Purple
    (0, 255, 0),        # S - Green
    (255, 0, 0),        # Z - Red
    (255, 165, 0),      # L - Orange
    (0, 100, 255),      # J - Blue
]

PIECE_NAMES = ['I', 'O', 'T', 'S', 'Z', 'L', 'J']

# ── Shape definitions (base rotation state) ────────────────────────────────
# 1 = filled cell, 0 = empty. Each shape's first rotation.
BASE_SHAPES = {
    'I': [[0, 0, 0, 0],
          [1, 1, 1, 1],
          [0, 0, 0, 0],
          [0, 0, 0, 0]],
    'O': [[1, 1],
          [1, 1]],
    'T': [[0, 1, 0],
          [1, 1, 1],
          [0, 0, 0]],
    'S': [[0, 1, 1],
          [1, 1, 0],
          [0, 0, 0]],
    'Z': [[1, 1, 0],
          [0, 1, 1],
          [0, 0, 0]],
    'L': [[0, 0, 1],
          [1, 1, 1],
          [0, 0, 0]],
    'J': [[1, 0, 0],
          [1, 1, 1],
          [0, 0, 0]],
}


# ── Helper: rotate matrix 90° clockwise ────────────────────────────────────
def rotate_cw(matrix):
    """New matrix = old rotated 90° clockwise."""
    rows = len(matrix)
    cols = len(matrix[0])
    return [[matrix[rows - 1 - c][r] for c in range(rows)] for r in range(cols)]


def generate_rotations(base):
    """All unique rotation states for a base matrix."""
    rots = [base]
    cur = base
    for _ in range(3):
        cur = rotate_cw(cur)
        if cur not in rots:
            rots.append(cur)
    return rots


def matrix_offsets(matrix):
    """Convert a binary matrix to a list of (col, row) offsets of filled cells."""
    return [(c, r) for r in range(len(matrix)) for c in range(len(matrix[0])) if matrix[r][c]]


# Build PIECE_ROTATIONS:  index → [ [offsets_rot0], [offsets_rot1], … ]
PIECE_ROTATIONS = {}
for idx, name in enumerate(PIECE_NAMES):
    rots = generate_rotations(BASE_SHAPES[name])
    PIECE_ROTATIONS[idx] = [matrix_offsets(r) for r in rots]


# ── Fonts ──────────────────────────────────────────────────────────────────
FONT_SMALL = None
FONT_MEDIUM = None
FONT_LARGE = None
FONT_TITLE = None


def init_fonts():
    global FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_TITLE
    FONT_SMALL = pygame.font.Font(None, 22)
    FONT_MEDIUM = pygame.font.Font(None, 28)
    FONT_LARGE = pygame.font.Font(None, 36)
    FONT_TITLE = pygame.font.Font(None, 50)


# ═══════════════════════════════════════════════════════════════════════════
#  BOARD
# ═══════════════════════════════════════════════════════════════════════════
class Board:
    """10×20 grid. 0 = empty, 1–7 = colour index + 1."""

    def __init__(self):
        self.grid = [[0] * BOARD_COLS for _ in range(BOARD_ROWS)]

    def valid(self, offsets, col, row):
        """True if *all* offset cells are inside bounds and not occupied."""
        for dx, dy in offsets:
            x = col + dx
            y = row + dy
            if x < 0 or x >= BOARD_COLS or y >= BOARD_ROWS:
                return False
            if y < 0:          # above visible area — always allowed
                continue
            if self.grid[y][x] != 0:
                return False
        return True

    def lock(self, offsets, col, row, piece_idx):
        """Write piece into grid. Return True if any cell landed above row 0."""
        above = False
        for dx, dy in offsets:
            x = col + dx
            y = row + dy
            if y < 0:
                above = True
                continue
            if 0 <= y < BOARD_ROWS and 0 <= x < BOARD_COLS:
                self.grid[y][x] = piece_idx + 1
        return above

    def clear_rows(self):
        """Remove full rows. Return number cleared."""
        cleared = 0
        keep = []
        for row in self.grid:
            if all(cell != 0 for cell in row):
                cleared += 1
            else:
                keep.append(row)
        for _ in range(cleared):
            keep.insert(0, [0] * BOARD_COLS)
        self.grid = keep
        return cleared

    def draw(self, screen):
        # background
        r = pygame.Rect(BOARD_X, BOARD_Y, BOARD_COLS * CELL_SIZE, BOARD_ROWS * CELL_SIZE)
        pygame.draw.rect(screen, BOARD_BG, r)

        # grid lines
        for row in range(BOARD_ROWS + 1):
            y = BOARD_Y + row * CELL_SIZE
            pygame.draw.line(screen, GRID_COLOR,
                             (BOARD_X, y), (BOARD_X + BOARD_COLS * CELL_SIZE, y))
        for col in range(BOARD_COLS + 1):
            x = BOARD_X + col * CELL_SIZE
            pygame.draw.line(screen, GRID_COLOR,
                             (x, BOARD_Y), (x, BOARD_Y + BOARD_ROWS * CELL_SIZE))

        # locked cells
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                val = self.grid[row][col]
                if val:
                    draw_cell(screen, col, row, PIECE_COLORS[val - 1], CELL_SIZE)

        # border
        br = pygame.Rect(BOARD_X - 3, BOARD_Y - 3,
                         BOARD_COLS * CELL_SIZE + 6, BOARD_ROWS * CELL_SIZE + 6)
        pygame.draw.rect(screen, BORDER_LIGHT, br, 3)


# ── Cell drawing helper ────────────────────────────────────────────────────
def draw_cell(screen, col, row, color, size, alpha=False):
    """Single cell with highlight/shadow for a 3-D look."""
    x = BOARD_X + col * size
    y = BOARD_Y + row * size
    inner = pygame.Rect(x + 1, y + 1, size - 2, size - 2)

    if alpha:
        s = pygame.Surface((size - 2, size - 2), pygame.SRCALPHA)
        s.fill((*color, 120))
        screen.blit(s, (x + 1, y + 1))
    else:
        pygame.draw.rect(screen, color, inner)
        hi = tuple(min(255, c + 60) for c in color)
        sh = tuple(max(0, c - 60) for c in color)
        pygame.draw.line(screen, hi, (x, y + size - 1), (x, y))
        pygame.draw.line(screen, hi, (x, y), (x + size - 1, y))
        pygame.draw.line(screen, sh, (x + size - 1, y), (x + size - 1, y + size - 1))
        pygame.draw.line(screen, sh, (x + size - 1, y + size - 1), (x, y + size - 1))


# ═══════════════════════════════════════════════════════════════════════════
#  PIECE
# ═══════════════════════════════════════════════════════════════════════════
class Piece:
    """Falling tetromino."""

    def __init__(self, piece_idx):
        self.idx = piece_idx
        self.rotations = PIECE_ROTATIONS[piece_idx]
        self.rot = 0
        self.offsets = self.rotations[0]

        # spawn centred
        w = max(dx for dx, _ in self.offsets) + 1
        self.col = (BOARD_COLS - w) // 2
        self.row = 0

    def current_offsets(self):
        return self.rotations[self.rot]

    def try_move(self, board, dc, dr):
        offs = self.rotations[self.rot]
        if board.valid(offs, self.col + dc, self.row + dr):
            self.col += dc
            self.row += dr
            return True
        return False

    def try_rotate(self, board):
        """Rotate clockwise with simple wall kicks."""
        new_rot = (self.rot + 1) % len(self.rotations)
        new_off = self.rotations[new_rot]

        # kick offsets to try
        for dc, dr in [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, -2)]:
            if board.valid(new_off, self.col + dc, self.row + dr):
                self.rot = new_rot
                self.offsets = new_off
                self.col += dc
                self.row += dr
                return True
        return False

    def draw(self, screen):
        color = PIECE_COLORS[self.idx]
        for dx, dy in self.offsets:
            c, r = self.col + dx, self.row + dy
            if r >= 0:
                draw_cell(screen, c, r, color, CELL_SIZE)

    def draw_ghost(self, screen, ghost_row):
        """Transparent version at ghost_row."""
        color = PIECE_COLORS[self.idx]
        offs = self.rotations[self.rot]
        for dx, dy in offs:
            c, r = self.col + dx, ghost_row + dy
            if r >= 0:
                draw_cell(screen, c, r, color, CELL_SIZE, alpha=True)

    def draw_preview(self, screen, px, py, cell_sz=24):
        """Static preview (first rotation) inside a box."""
        color = PIECE_COLORS[self.idx]
        offs = self.rotations[0]
        xs = [dx for dx, _ in offs]
        ys = [dy for _, dy in offs]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        ox = px + (4 * cell_sz - w * cell_sz) // 2 - min_x * cell_sz
        oy = py + (4 * cell_sz - h * cell_sz) // 2 - min_y * cell_sz

        for dx, dy in offs:
            x = ox + dx * cell_sz
            y = oy + dy * cell_sz
            inner = pygame.Rect(x + 1, y + 1, cell_sz - 2, cell_sz - 2)
            pygame.draw.rect(screen, color, inner)
            hi = tuple(min(255, c + 60) for c in color)
            sh = tuple(max(0, c - 60) for c in color)
            pygame.draw.line(screen, hi, (x, y + cell_sz - 1), (x, y))
            pygame.draw.line(screen, hi, (x, y), (x + cell_sz - 1, y))
            pygame.draw.line(screen, sh, (x + cell_sz - 1, y),
                             (x + cell_sz - 1, y + cell_sz - 1))
            pygame.draw.line(screen, sh, (x + cell_sz - 1, y + cell_sz - 1),
                             (x, y + cell_sz - 1))


# ═══════════════════════════════════════════════════════════════════════════
#  GAME
# ═══════════════════════════════════════════════════════════════════════════
class TetrisGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris")
        self.clock = pygame.time.Clock()
        self.reset()

    # ── reset ───────────────────────────────────────────────────────────
    def reset(self):
        self.board = Board()
        self.score = 0
        self.level = 1
        self.lines = 0
        self.game_over = False

        # gravity
        self.fall_timer = 0.0

        # lock delay
        self.lock_timer = 0.0
        self.LOCK_MAX = 500  # ms

        # DAS — delayed auto shift
        self.das_dir = 0         # -1 L, 0 none, +1 R
        self.das_timer = 0.0
        self.DAS_DELAY = 170     # ms before repeat starts
        self.DAS_RATE = 50       # ms between repeats

        # bag randomiser
        self.bag = []
        self._fill_bag()
        self.next_idx = self._pull()
        self.piece = None
        self._spawn()

    # ── bag ─────────────────────────────────────────────────────────────
    def _fill_bag(self):
        seq = list(range(7))
        random.shuffle(seq)
        self.bag.extend(seq)

    def _pull(self):
        if len(self.bag) <= 1:
            self._fill_bag()
        return self.bag.pop(0)

    # ── spawn ───────────────────────────────────────────────────────────
    def _spawn(self):
        self.piece = Piece(self.next_idx)
        self.next_idx = self._pull()
        self.fall_timer = 0.0
        self.lock_timer = 0.0
        if not self.board.valid(self.piece.current_offsets(),
                                self.piece.col, self.piece.row):
            self.game_over = True

    # ── speed ───────────────────────────────────────────────────────────
    def fall_speed(self):
        # ms per row; starts at 800, decreases 50/level, floor 80
        return max(80, 800 - (self.level - 1) * 50)

    # ── scoring ─────────────────────────────────────────────────────────
    SCORE_TABLE = {1: 100, 2: 300, 3: 500, 4: 800}

    # ── lock ────────────────────────────────────────────────────────────
    def _lock(self):
        if not self.piece:
            return
        offs = self.piece.current_offsets()
        self.board.lock(offs, self.piece.col, self.piece.row, self.piece.idx)

        cleared = self.board.clear_rows()
        if cleared:
            self.lines += cleared
            self.score += self.SCORE_TABLE.get(cleared, 0) * self.level
            self.level = self.lines // 10 + 1

        self._spawn()

    # ── ghost row ───────────────────────────────────────────────────────
    def _ghost_row(self):
        if not self.piece:
            return 0
        r = self.piece.row
        offs = self.piece.current_offsets()
        while self.board.valid(offs, self.piece.col, r + 1):
            r += 1
        return r

    # ── update ──────────────────────────────────────────────────────────
    def update(self, dt):
        if self.game_over or not self.piece:
            return

        keys = pygame.key.get_pressed()

        # ── DAS horizontal ──────────────────────────────────────────
        left = keys[pygame.K_LEFT]
        right = keys[pygame.K_RIGHT]

        if left and not right:
            new_dir = -1
        elif right and not left:
            new_dir = 1
        else:
            new_dir = 0

        if new_dir != self.das_dir:
            self.das_dir = new_dir
            self.das_timer = 0.0
            if new_dir != 0:
                self.piece.try_move(self.board, new_dir, 0)
                self._bump_lock()
        elif self.das_dir != 0:
            self.das_timer += dt
            while self.das_timer >= self.DAS_DELAY:
                self.das_timer -= self.DAS_RATE
                self.piece.try_move(self.board, self.das_dir, 0)
                self._bump_lock()

        # ── soft drop ────────────────────────────────────────────────
        if keys[pygame.K_DOWN]:
            self.fall_timer += dt * 15   # ~15× faster
            # award 1 point per soft-dropped row later in gravity loop
        else:
            self.fall_timer += dt

        # ── gravity ──────────────────────────────────────────────────
        speed = self.fall_speed()
        while self.fall_timer >= speed:
            self.fall_timer -= speed
            if self.piece.try_move(self.board, 0, 1):
                if keys[pygame.K_DOWN]:
                    self.score += 1      # soft-drop bonus
            else:
                break

        # ── lock delay ───────────────────────────────────────────────
        offs = self.piece.current_offsets()
        resting = not self.board.valid(offs, self.piece.col, self.piece.row + 1)
        if resting:
            self.lock_timer += dt
            if self.lock_timer >= self.LOCK_MAX:
                self._lock()
        else:
            self.lock_timer = 0.0

    def _bump_lock(self):
        """Slightly reduce lock timer after a successful lateral move/rotate
           while resting — gives the player a little more time."""
        if self.piece:
            offs = self.piece.current_offsets()
            if not self.board.valid(offs, self.piece.col, self.piece.row + 1):
                self.lock_timer = max(0.0, self.lock_timer - 200)

    # ── event handling ─────────────────────────────────────────────────
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            if self.game_over:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.reset()
                elif event.key == pygame.K_ESCAPE:
                    return False
            else:
                if event.key == pygame.K_UP and self.piece:
                    self.piece.try_rotate(self.board)
                    self._bump_lock()
                elif event.key == pygame.K_SPACE and self.piece:
                    # hard drop
                    dist = 0
                    while self.piece.try_move(self.board, 0, 1):
                        dist += 1
                    self.score += dist * 2
                    self._lock()
                elif event.key == pygame.K_ESCAPE:
                    return False
        return True

    # ── draw ───────────────────────────────────────────────────────────
    def draw(self):
        screen = self.screen
        screen.fill(BLACK)

        # board + locked cells
        self.board.draw(screen)

        # ghost
        if self.piece and not self.game_over:
            gr = self._ghost_row()
            if gr != self.piece.row:
                self.piece.draw_ghost(screen, gr)

        # active piece
        if self.piece and not self.game_over:
            self.piece.draw(screen)

        # ── right panel ──────────────────────────────────────────────
        panel = pygame.Rect(PREVIEW_X - 10, 10, 150, SCREEN_HEIGHT - 20)
        pygame.draw.rect(screen, PANEL_BG, panel, border_radius=8)
        pygame.draw.rect(screen, BORDER_LIGHT, panel, 2, border_radius=8)

        # "NEXT" label
        lbl = FONT_MEDIUM.render("NEXT", True, TEXT_COLOR)
        screen.blit(lbl, (PREVIEW_X + 32, PREVIEW_Y - 35))

        # preview box
        pbox = pygame.Rect(PREVIEW_X + 5, PREVIEW_Y, 110, 110)
        pygame.draw.rect(screen, BOARD_BG, pbox, border_radius=4)
        pygame.draw.rect(screen, BORDER_DARK, pbox, 2, border_radius=4)

        # draw next piece preview
        pv = Piece(self.next_idx)
        pv.draw_preview(screen, PREVIEW_X + 10, PREVIEW_Y + 5, 24)

        # stats
        y = PREVIEW_Y + 140
        for label, val in [("SCORE", str(self.score)),
                           ("LEVEL", str(self.level)),
                           ("LINES", str(self.lines))]:
            screen.blit(FONT_SMALL.render(label, True, TEXT_DIM), (PREVIEW_X + 5, y))
            y += 22
            screen.blit(FONT_MEDIUM.render(val, True, TEXT_COLOR), (PREVIEW_X + 10, y))
            y += 35

        # controls
        y += 10
        for key, act in [("← →", "Move"), ("↑", "Rotate"),
                         ("↓", "Soft Drop"), ("SPACE", "Hard Drop"),
                         ("ESC", "Quit")]:
            screen.blit(FONT_SMALL.render(key, True, TEXT_DIM), (PREVIEW_X + 5, y))
            screen.blit(FONT_SMALL.render(act, True, TEXT_COLOR), (PREVIEW_X + 58, y))
            y += 22

        # ── game over overlay ────────────────────────────────────────
        if self.game_over:
            self._draw_game_over(screen)

        pygame.display.flip()

    def _draw_game_over(self, screen):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        screen.blit(overlay, (0, 0))

        bw, bh = 320, 220
        bx = (SCREEN_WIDTH - bw) // 2
        by = (SCREEN_HEIGHT - bh) // 2
        box = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(screen, (18, 18, 18), box, border_radius=12)
        pygame.draw.rect(screen, BORDER_LIGHT, box, 3, border_radius=12)

        go = FONT_TITLE.render("GAME OVER", True, (255, 80, 80))
        screen.blit(go, go.get_rect(center=(SCREEN_WIDTH // 2, by + 40)))

        sc = FONT_LARGE.render(f"Score: {self.score}", True, TEXT_COLOR)
        screen.blit(sc, sc.get_rect(center=(SCREEN_WIDTH // 2, by + 90)))

        lv = FONT_MEDIUM.render(f"Level: {self.level}", True, TEXT_COLOR)
        screen.blit(lv, lv.get_rect(center=(SCREEN_WIDTH // 2, by + 130)))

        ln = FONT_MEDIUM.render(f"Lines: {self.lines}", True, TEXT_COLOR)
        screen.blit(ln, ln.get_rect(center=(SCREEN_WIDTH // 2, by + 160)))

        hint = FONT_SMALL.render("SPACE to restart  |  ESC to quit", True, TEXT_DIM)
        screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, by + 195)))

    # ── run ────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)

            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
                    break

            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    init_fonts()
    TetrisGame().run()


if __name__ == "__main__":
    main()
