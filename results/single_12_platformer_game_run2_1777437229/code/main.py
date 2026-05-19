"""
2D Platformer Game
A side-view platformer with running, jumping, coins, enemies, and multiple levels.
"""

import pygame
import sys
import math
from settings import *
from levels import LEVELS


class Player:
    """Player character with movement, jumping, gravity, health, and invincibility."""

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.health = PLAYER_MAX_HEALTH
        self.invincible_timer = 0
        self.facing_right = True
        self.coins_collected_this_level = 0

    def update(self, platforms, enemies, coins, goal):
        """Update player position, check collisions, return state changes."""
        keys = pygame.key.get_pressed()

        # Horizontal movement
        self.vx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -PLAYER_SPEED
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = PLAYER_SPEED
            self.facing_right = True

        # Apply gravity
        self.vy += GRAVITY
        if self.vy > MAX_FALL_SPEED:
            self.vy = MAX_FALL_SPEED

        # --- Horizontal movement and collision ---
        self.rect.x += self.vx
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.vx > 0:   # moving right
                    self.rect.right = plat.left
                elif self.vx < 0:  # moving left
                    self.rect.left = plat.right
                self.vx = 0

        # --- Vertical movement and collision ---
        self.rect.y += self.vy
        self.on_ground = False
        for plat in platforms:
            if self.rect.colliderect(plat):
                if self.vy > 0:   # falling down
                    self.rect.bottom = plat.top
                    self.on_ground = True
                elif self.vy < 0:  # jumping up, hit head
                    self.rect.top = plat.bottom
                self.vy = 0

        # --- Collect coins ---
        for coin in coins[:]:
            if self.rect.colliderect(coin.rect):
                coins.remove(coin)
                self.coins_collected_this_level += 1

        # --- Enemy collisions ---
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
        else:
            for enemy in enemies:
                if self.rect.colliderect(enemy.rect):
                    self.health -= 1
                    self.invincible_timer = INVINCIBILITY_FRAMES
                    # Knockback away from enemy
                    knock_dx = 10 if self.rect.centerx >= enemy.rect.centerx else -10
                    self.vx = knock_dx
                    self.vy = -8
                    # Push out to avoid multi-hit
                    if knock_dx > 0:
                        self.rect.left = enemy.rect.right + 1
                    else:
                        self.rect.right = enemy.rect.left - 1
                    break

        # --- Check death by falling ---
        if self.rect.top > SCREEN_HEIGHT + 100:
            self.health -= 1
            if self.health <= 0:
                return "dead"
            return "respawn"

        # --- Check goal ---
        if self.rect.colliderect(goal):
            return "level_complete"

        # --- Check death by health ---
        if self.health <= 0:
            return "dead"

        return None

    def jump(self):
        """Make the player jump if on ground."""
        if self.on_ground:
            self.vy = JUMP_VELOCITY
            self.on_ground = False

    def draw(self, screen, camera_x):
        """Draw the player with blink effect during invincibility."""
        if self.invincible_timer > 0 and (self.invincible_timer // 6) % 2 == 0:
            return  # blink (hidden every other 6 frames)

        draw_x = self.rect.x - camera_x
        draw_rect = pygame.Rect(draw_x, self.rect.y, self.rect.width, self.rect.height)

        # Body
        pygame.draw.rect(screen, PLAYER_COLOR, draw_rect)
        pygame.draw.rect(screen, (30, 70, 200), draw_rect, 2)  # outline

        # Eyes
        eye_y = draw_rect.y + 10
        if self.facing_right:
            eye_x = draw_rect.x + 18
            pupil_off = 2
        else:
            eye_x = draw_rect.x + 10
            pupil_off = -2
        pygame.draw.circle(screen, WHITE, (eye_x, eye_y), 6)
        pygame.draw.circle(screen, BLACK, (eye_x + pupil_off, eye_y), 3)

        # Mouth
        mouth_y = draw_rect.y + 26
        mouth_x = draw_rect.x + 12
        pygame.draw.rect(screen, (255, 220, 180), (mouth_x, mouth_y, 8, 3))


class Enemy:
    """Patrols back and forth between two x-coordinates."""

    def __init__(self, x, y, patrol_min, patrol_max):
        self.rect = pygame.Rect(x, y, ENEMY_WIDTH, ENEMY_HEIGHT)
        self.patrol_min = patrol_min
        self.patrol_max = patrol_max
        self.vx = float(ENEMY_PATROL_SPEED)

    def update(self):
        """Move and reverse at patrol bounds."""
        self.rect.x += self.vx
        if self.rect.x <= self.patrol_min:
            self.rect.x = self.patrol_min
            self.vx = abs(self.vx)
        elif self.rect.x + self.rect.width >= self.patrol_max:
            self.rect.right = self.patrol_max
            self.vx = -abs(self.vx)

    def draw(self, screen, camera_x):
        """Draw the enemy with simple eyes."""
        draw_x = self.rect.x - camera_x
        draw_rect = pygame.Rect(draw_x, self.rect.y, self.rect.width, self.rect.height)

        # Only draw if on screen
        if draw_rect.right < -50 or draw_rect.left > SCREEN_WIDTH + 50:
            return

        pygame.draw.rect(screen, ENEMY_COLOR, draw_rect)
        pygame.draw.rect(screen, (180, 30, 30), draw_rect, 2)

        # Eyes - always face the player-ish, or just forward
        eye_y = draw_rect.y + 8
        # Two menacing eyes
        pygame.draw.circle(screen, WHITE, (draw_rect.x + 8, eye_y), 5)
        pygame.draw.circle(screen, WHITE, (draw_rect.x + 22, eye_y), 5)
        # Pupils look in movement direction
        pupil_off = 1 if self.vx > 0 else -1
        pygame.draw.circle(screen, BLACK, (draw_rect.x + 8 + pupil_off, eye_y), 2)
        pygame.draw.circle(screen, BLACK, (draw_rect.x + 22 + pupil_off, eye_y), 2)


class Coin:
    """Collectible coin with a bobbing animation."""

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.rect = pygame.Rect(
            int(x - COIN_RADIUS), int(y - COIN_RADIUS),
            COIN_RADIUS * 2, COIN_RADIUS * 2,
        )
        self.base_y = y

    def update(self):
        """Bob up and down."""
        offset = math.sin(pygame.time.get_ticks() * 0.004 + self.x * 0.01) * 3
        self.y = self.base_y + offset
        self.rect.centery = int(self.y)

    def draw(self, screen, camera_x):
        """Draw the coin."""
        draw_x = int(self.x - camera_x)
        draw_y = int(self.y)

        # Only draw if on screen
        if draw_x < -COIN_RADIUS or draw_x > SCREEN_WIDTH + COIN_RADIUS:
            return

        pygame.draw.circle(screen, COIN_OUTLINE, (draw_x, draw_y), COIN_RADIUS)
        pygame.draw.circle(screen, COIN_COLOR, (draw_x, draw_y), COIN_RADIUS - 3)
        # Shine highlight
        shine_x = draw_x - 3
        shine_y = draw_y - 3
        pygame.draw.circle(screen, (255, 240, 100), (shine_x, shine_y), COIN_RADIUS // 3)


class Game:
    """Main game manager: loads levels, runs the loop, handles UI."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Platformer Adventure")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_small = pygame.font.Font(None, 28)
        self.font = pygame.font.Font(None, 36)
        self.font_big = pygame.font.Font(None, 64)

        # Persistent across levels
        self.total_coins = 0
        self._coins_before_level = 0  # snapshot for retry
        self.current_level_index = 0

        # State
        self.state = "playing"  # playing | level_complete | game_over | game_won
        self.level_complete_timer = 0

        # Load first level
        self._load_level(self.current_level_index)

    # ------------------------------------------------------------------
    # Level loading
    # ------------------------------------------------------------------
    def _load_level(self, index):
        """Load level data and create all objects."""
        if index >= len(LEVELS):
            self.state = "game_won"
            return

        data = LEVELS[index]
        self.level_name = data["name"]

        # Snapshot coins at level start so we can restore on retry
        self._coins_before_level = self.total_coins

        # Platforms
        self.platforms = [
            pygame.Rect(x, y, w, h) for x, y, w, h in data["platforms"]
        ]

        # Coins
        self.coins = [Coin(x, y) for x, y in data["coins"]]

        # Enemies
        self.enemies = [
            Enemy(x, y, pmin, pmax)
            for x, y, pmin, pmax in data["enemies"]
        ]

        # Player
        px, py = data["player_spawn"]
        self.player = Player(px, py)

        # Goal
        gx, gy = data["goal"]
        self.goal = pygame.Rect(gx, gy, 30, 50)

        # Level width (farthest right edge among platforms and goal)
        max_x = self.goal.right
        for plat in self.platforms:
            if plat.right > max_x:
                max_x = plat.right
        self.level_width = max(int(max_x + 100), SCREEN_WIDTH)

        # Camera starts at 0
        self.camera_x = 0.0

        # State
        self.state = "playing"
        self.level_complete_timer = 0

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _handle_events(self):
        """Process input; return False to quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                # Jump
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP or event.key == pygame.K_w:
                    if self.state == "playing":
                        self.player.jump()
                    elif self.state in ("game_over", "game_won"):
                        # Restart from level 1
                        self.total_coins = 0
                        self.current_level_index = 0
                        self._load_level(0)

                # Retry current level
                if event.key == pygame.K_r:
                    if self.state == "game_over":
                        self._load_level(self.current_level_index)

                # Debug: skip level (backtick)
                if event.key == pygame.K_n and self.state == "playing":
                    self.state = "level_complete"
                    self.level_complete_timer = 60

                # Quit with Escape
                if event.key == pygame.K_ESCAPE:
                    return False

        return True

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def _update(self):
        """Advance game logic by one frame."""
        if self.state == "level_complete":
            self.level_complete_timer -= 1
            if self.level_complete_timer <= 0:
                self.current_level_index += 1
                self._load_level(self.current_level_index)
            return

        if self.state in ("game_over", "game_won"):
            return

        # Update player
        result = self.player.update(
            self.platforms, self.enemies, self.coins, self.goal
        )

        if result == "level_complete":
            # Commit coins from this level
            self.total_coins = self._coins_before_level + self.player.coins_collected_this_level
            self.state = "level_complete"
            self.level_complete_timer = 90
            return

        if result == "dead":
            # Don't keep coins from failed attempt
            self.total_coins = self._coins_before_level
            self.state = "game_over"
            return

        if result == "respawn":
            # Fell off the map – respawn at level start
            self._respawn_player()

        # Update enemies
        for enemy in self.enemies:
            enemy.update()

        # Update coin animations
        for coin in self.coins:
            coin.update()

        # Smooth camera follow
        target_cx = self.player.rect.centerx - SCREEN_WIDTH // 3
        target_cx = max(0, min(target_cx, self.level_width - SCREEN_WIDTH))
        self.camera_x += (target_cx - self.camera_x) * 0.12

    def _respawn_player(self):
        """Respawn the player at the level's spawn point."""
        data = LEVELS[self.current_level_index]
        px, py = data["player_spawn"]
        self.player.rect.x = px
        self.player.rect.y = py
        self.player.vx = 0
        self.player.vy = 0
        self.player.invincible_timer = INVINCIBILITY_FRAMES

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _draw(self):
        """Render everything."""
        if self.state == "game_won":
            self._draw_win_screen()
            pygame.display.flip()
            return

        # Sky background
        self.screen.fill(SKY_BLUE)

        # Distant background hills (parallax-like, slightly slower scroll)
        self._draw_background_hills()

        # Platforms
        self._draw_platforms()

        # Goal flag
        self._draw_goal()

        # Coins
        for coin in self.coins:
            coin.draw(self.screen, self.camera_x)

        # Enemies
        for enemy in self.enemies:
            enemy.draw(self.screen, self.camera_x)

        # Player
        self.player.draw(self.screen, self.camera_x)

        # UI overlay (fixed on screen)
        self._draw_ui()

        # Level complete overlay
        if self.state == "level_complete":
            self._draw_overlay("Level Complete!", GOAL_COLOR)
            sub = self.font.render("Get ready...", True, WHITE)
            self.screen.blit(sub, (
                SCREEN_WIDTH // 2 - sub.get_width() // 2,
                SCREEN_HEIGHT // 2 + 40,
            ))

        # Game over overlay
        if self.state == "game_over":
            self._draw_overlay("GAME OVER", ENEMY_COLOR)
            sub1 = self.font_small.render(
                "Press R to retry level", True, WHITE
            )
            sub2 = self.font_small.render(
                "Press SPACE to restart from beginning", True, WHITE
            )
            self.screen.blit(sub1, (
                SCREEN_WIDTH // 2 - sub1.get_width() // 2,
                SCREEN_HEIGHT // 2 + 30,
            ))
            self.screen.blit(sub2, (
                SCREEN_WIDTH // 2 - sub2.get_width() // 2,
                SCREEN_HEIGHT // 2 + 60,
            ))

        pygame.display.flip()

    def _draw_background_hills(self):
        """Simple parallax background hills."""
        cam = int(self.camera_x * 0.3)  # slower than foreground
        hill_color = (100, 160, 100)
        # Draw a few rolling hills
        for i in range(0, self.level_width // 300 + 3):
            base_x = i * 300 - (cam % 300) - 100
            # Hill shape using ellipse
            hill_rect = pygame.Rect(base_x, SCREEN_HEIGHT - 120, 350, 200)
            pygame.draw.ellipse(self.screen, hill_color, hill_rect)
            hill_rect2 = pygame.Rect(base_x + 150, SCREEN_HEIGHT - 100, 300, 180)
            pygame.draw.ellipse(self.screen, (85, 140, 85), hill_rect2)

    def _draw_platforms(self):
        """Draw all platforms, culling off-screen ones."""
        cam = int(self.camera_x)
        for plat in self.platforms:
            draw_rect = pygame.Rect(
                plat.x - cam, plat.y, plat.width, plat.height
            )
            if draw_rect.right < -10 or draw_rect.left > SCREEN_WIDTH + 10:
                continue
            pygame.draw.rect(self.screen, PLATFORM_COLOR, draw_rect)
            # Top edge highlight
            pygame.draw.line(
                self.screen, PLATFORM_TOP,
                (draw_rect.x, draw_rect.y),
                (draw_rect.x + draw_rect.width, draw_rect.y),
                3,
            )
            # Subtle border
            pygame.draw.rect(self.screen, (60, 60, 75), draw_rect, 1)

    def _draw_goal(self):
        """Draw the goal flag."""
        cam = int(self.camera_x)
        gx = self.goal.x - cam
        gy = self.goal.y
        gw = self.goal.width
        gh = self.goal.height

        if gx + gw < 0 or gx > SCREEN_WIDTH:
            return

        # Pole
        pole_x = gx + gw // 2
        pygame.draw.rect(self.screen, GOAL_POLE, (pole_x - 3, gy - 40, 6, gh + 40))
        # Flag
        flag_pts = [
            (pole_x + 3, gy - 38),
            (pole_x + 3 + 28, gy - 24),
            (pole_x + 3, gy - 10),
        ]
        pygame.draw.polygon(self.screen, FLAG_RED, flag_pts)
        # Base platform
        pygame.draw.rect(self.screen, GOAL_COLOR, (gx, gy, gw, gh))
        pygame.draw.rect(self.screen, (30, 200, 70), (gx, gy, gw, gh), 2)
        # Label
        label = self.font_small.render("GOAL", True, WHITE)
        self.screen.blit(label, (gx + gw // 2 - label.get_width() // 2, gy - 48))

    def _draw_ui(self):
        """Draw health bar, coin counter, and level name (screen-fixed)."""
        # ---- Health bar ----
        bar_width = 220
        bar_height = 24
        bar_x = 20
        bar_y = 20

        # Background
        pygame.draw.rect(self.screen, HEALTH_BG,
                         (bar_x - 1, bar_y - 1, bar_width + 2, bar_height + 2))
        pygame.draw.rect(self.screen, (30, 30, 30),
                         (bar_x, bar_y, bar_width, bar_height))

        # Fill
        ratio = max(0, self.player.health) / PLAYER_MAX_HEALTH
        fill_w = int(bar_width * ratio)
        if ratio > 0.5:
            color = HEALTH_GREEN
        elif ratio > 0.25:
            color = HEALTH_YELLOW
        else:
            color = HEALTH_RED
        if fill_w > 0:
            pygame.draw.rect(self.screen, color, (bar_x, bar_y, fill_w, bar_height))

        # Border
        pygame.draw.rect(self.screen, WHITE,
                         (bar_x, bar_y, bar_width, bar_height), 2)

        # Label
        hp_text = self.font_small.render(
            f"HP: {max(0, self.player.health)} / {PLAYER_MAX_HEALTH}",
            True, WHITE,
        )
        self.screen.blit(hp_text, (bar_x, bar_y + bar_height + 4))

        # ---- Coin counter ----
        display_coins = self._coins_before_level + self.player.coins_collected_this_level
        coin_label = self.font.render(
            f"Coins: {display_coins}", True, COIN_COLOR
        )
        self.screen.blit(coin_label,
                         (SCREEN_WIDTH - coin_label.get_width() - 20, 18))

        # ---- Level name ----
        lvl = self.font_small.render(self.level_name, True, WHITE)
        self.screen.blit(lvl,
                         (SCREEN_WIDTH // 2 - lvl.get_width() // 2, 10))

        # ---- Level progress bar ----
        if self.level_width > SCREEN_WIDTH:
            prog_w = 200
            prog_h = 6
            px = SCREEN_WIDTH // 2 - prog_w // 2
            py = SCREEN_HEIGHT - 18
            # Background
            pygame.draw.rect(self.screen, (40, 40, 40), (px, py, prog_w, prog_h))
            # Position indicator
            cam_ratio = self.camera_x / (self.level_width - SCREEN_WIDTH)
            ind_x = px + int(cam_ratio * (prog_w - 20))
            pygame.draw.rect(self.screen, WHITE, (ind_x, py - 2, 20, prog_h + 4))

    def _draw_overlay(self, title, color):
        """Draw a centered translucent overlay with big text."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(170)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        text = self.font_big.render(title, True, color)
        self.screen.blit(text, (
            SCREEN_WIDTH // 2 - text.get_width() // 2,
            SCREEN_HEIGHT // 2 - text.get_height() // 2 - 20,
        ))

    def _draw_win_screen(self):
        """You beat all levels!"""
        self.screen.fill((20, 30, 50))
        title = self.font_big.render("YOU WIN!", True, GOAL_COLOR)
        self.screen.blit(title, (
            SCREEN_WIDTH // 2 - title.get_width() // 2,
            SCREEN_HEIGHT // 2 - 100,
        ))
        coins_msg = self.font.render(
            f"Total coins collected: {self.total_coins}", True, COIN_COLOR
        )
        self.screen.blit(coins_msg, (
            SCREEN_WIDTH // 2 - coins_msg.get_width() // 2,
            SCREEN_HEIGHT // 2 - 20,
        ))
        restart = self.font.render(
            "Press SPACE to play again", True, WHITE
        )
        self.screen.blit(restart, (
            SCREEN_WIDTH // 2 - restart.get_width() // 2,
            SCREEN_HEIGHT // 2 + 50,
        ))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        """Run the main game loop."""
        running = True
        while running:
            running = self._handle_events()
            self._update()
            self._draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


# ======================================================================
if __name__ == "__main__":
    game = Game()
    game.run()
