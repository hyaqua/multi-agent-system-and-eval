"""
game.py – Main Game class that manages game states, levels, and the game loop.
"""
import sys
import pygame
from settings import *
from sprites import Player, Enemy, Coin, Platform, Goal
from camera import Camera
from levels import LEVELS


class Game:
    """Main game manager."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24, bold=True)
        self.big_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 18)

        self.current_level_index = 0
        self.coins_collected = 0

        self.all_sprites = pygame.sprite.Group()
        self.platforms = pygame.sprite.Group()
        self.coins = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.goal_group = pygame.sprite.GroupSingle()

        self.player = None
        self.camera = None
        self.level_width = 0
        self.level_height = 0
        self.goal_reached = False
        self.game_over = False
        self.game_complete = False
        self.transition_timer = 0

        self._load_level(self.current_level_index)

    # ───────────────────────── level loading ─────────────────────────

    def _load_level(self, index):
        """Load a level from LEVELS by index."""
        if index >= len(LEVELS):
            self.game_complete = True
            return

        level_data = LEVELS[index]
        self.all_sprites.empty()
        self.platforms.empty()
        self.coins.empty()
        self.enemies.empty()
        self.goal_group.empty()

        self.level_width = 0
        self.level_height = SCREEN_HEIGHT
        self.goal_reached = False
        self.transition_timer = 0

        # Background color for this level
        self.bg_color = level_data.get("background_color", SKY_BLUE)

        # Create platforms
        for x, y, w, h in level_data["platforms"]:
            p = Platform(x, y, w, h)
            self.platforms.add(p)
            self.all_sprites.add(p)
            right_edge = x + w
            if right_edge > self.level_width:
                self.level_width = right_edge
            bottom_edge = y + h
            if bottom_edge > self.level_height:
                self.level_height = bottom_edge

        # Create coins
        for cx, cy in level_data["coins"]:
            c = Coin(cx, cy)
            self.coins.add(c)
            self.all_sprites.add(c)

        # Create enemies
        for ex, ey, pl, pr in level_data["enemies"]:
            e = Enemy(ex, ey, pl, pr)
            self.enemies.add(e)
            self.all_sprites.add(e)

        # Create player
        px, py = level_data["player_start"]
        self.player = Player(px, py)
        self.all_sprites.add(self.player)

        # Create goal
        gx, gy = level_data["goal"]
        goal = Goal(gx, gy)
        self.goal_group.add(goal)
        self.all_sprites.add(goal)

        # Camera
        self.camera = Camera(self.level_width, self.level_height)

        # Ensure level_width at least screen width
        if self.level_width < SCREEN_WIDTH:
            self.level_width = SCREEN_WIDTH

    # ───────────────────────── update ────────────────────────────────

    def _handle_input(self):
        keys = pygame.key.get_pressed()

        if self.game_over or self.game_complete:
            if keys[pygame.K_r]:
                self._restart_game()
            return

        if self.goal_reached:
            return

        # Horizontal movement
        self.player.vel_x = 0.0
        if keys[pygame.K_LEFT]:
            self.player.vel_x = -PLAYER_SPEED
            self.player.facing_right = False
        if keys[pygame.K_RIGHT]:
            self.player.vel_x = PLAYER_SPEED
            self.player.facing_right = True

        # Jump
        if keys[pygame.K_SPACE] and self.player.on_ground:
            self.player.vel_y = PLAYER_JUMP_VELOCITY
            self.player.on_ground = False

    def _apply_gravity(self):
        if not self.player.on_ground:
            self.player.vel_y += GRAVITY
            if self.player.vel_y > MAX_FALL_SPEED:
                self.player.vel_y = MAX_FALL_SPEED

    def _handle_platform_collisions(self):
        """Move player and resolve platform collisions."""
        # Horizontal movement
        self.player.rect.x += self.player.vel_x
        self._resolve_horizontal_collisions()

        # Vertical movement
        self.player.rect.y += self.player.vel_y
        self._resolve_vertical_collisions()

        # Clamp player within level bounds
        if self.player.rect.left < 0:
            self.player.rect.left = 0
        if self.player.rect.right > self.level_width:
            self.player.rect.right = self.level_width
        if self.player.rect.top < 0:
            self.player.rect.top = 0
            self.player.vel_y = 0
        # Fall off bottom = death
        if self.player.rect.top > self.level_height + 100:
            self.player.health = 0

    def _resolve_horizontal_collisions(self):
        hits = pygame.sprite.spritecollide(self.player, self.platforms, False)
        for plat in hits:
            if self.player.vel_x > 0:  # moving right
                self.player.rect.right = plat.rect.left
            elif self.player.vel_x < 0:  # moving left
                self.player.rect.left = plat.rect.right
            self.player.vel_x = 0

    def _resolve_vertical_collisions(self):
        self.player.on_ground = False
        hits = pygame.sprite.spritecollide(self.player, self.platforms, False)
        for plat in hits:
            if self.player.vel_y > 0:  # falling down
                # Land on top of the platform
                self.player.rect.bottom = plat.rect.top
                self.player.vel_y = 0
                self.player.on_ground = True
            elif self.player.vel_y < 0:  # jumping up
                # Hit head on bottom of platform
                self.player.rect.top = plat.rect.bottom
                self.player.vel_y = 0

    def _handle_coin_pickups(self):
        collected = pygame.sprite.spritecollide(self.player, self.coins, True)
        self.coins_collected += len(collected)

    def _handle_enemy_collisions(self):
        hits = pygame.sprite.spritecollide(self.player, self.enemies, False)
        for enemy in hits:
            # If player is falling onto enemy from above, stomp it
            if self.player.vel_y > 0 and self.player.rect.bottom <= enemy.rect.centery:
                enemy.kill()
                self.player.vel_y = PLAYER_JUMP_VELOCITY * 0.6  # bounce
            else:
                self.player.take_damage()

    def _handle_goal(self):
        if not self.goal_reached and self.goal_group.sprite:
            if self.player.rect.colliderect(self.goal_group.sprite.rect):
                self.goal_reached = True
                self.transition_timer = 90  # 1.5 seconds

    def _check_game_over(self):
        if not self.player.is_alive() and not self.game_over:
            self.game_over = True

    def update(self):
        self._handle_input()

        if self.game_over or self.game_complete:
            return

        if self.goal_reached:
            self.transition_timer -= 1
            if self.transition_timer <= 0:
                self.current_level_index += 1
                self._load_level(self.current_level_index)
            return

        self._apply_gravity()
        self._handle_platform_collisions()
        self._handle_coin_pickups()
        self._handle_enemy_collisions()
        self._handle_goal()
        self._check_game_over()

        # Update all sprites
        for sprite in self.all_sprites:
            if sprite != self.player:
                sprite.update()

        self.player.update()

        # Update camera to follow player
        if self.camera:
            self.camera.update(self.player.rect)

    # ───────────────────────── drawing ───────────────────────────────

    def _draw_hud(self):
        """Draw coin count and health bar on screen (not affected by camera)."""
        # Coin counter
        coin_text = self.font.render(f"Coins: {self.coins_collected}", True, BLACK)
        coin_bg = pygame.Surface((coin_text.get_width() + 20, coin_text.get_height() + 10))
        coin_bg.fill((255, 255, 255, 180))
        coin_bg.set_alpha(180)
        self.screen.blit(coin_bg, (10, 10))
        self.screen.blit(coin_text, (20, 15))

        # Health bar
        bar_width = 200
        bar_height = 24
        bar_x = SCREEN_WIDTH - bar_width - 20
        bar_y = 15

        # Background
        pygame.draw.rect(self.screen, DARK_GRAY,
                         (bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4))
        pygame.draw.rect(self.screen, (60, 60, 60),
                         (bar_x, bar_y, bar_width, bar_height))

        # Health fill
        health_ratio = max(0, self.player.health / PLAYER_MAX_HEALTH)
        fill_width = int(bar_width * health_ratio)
        if health_ratio > 0.5:
            fill_color = GREEN
        elif health_ratio > 0.25:
            fill_color = ORANGE
        else:
            fill_color = RED
        if fill_width > 0:
            pygame.draw.rect(self.screen, fill_color,
                             (bar_x, bar_y, fill_width, bar_height))

        # Health label
        health_label = self.small_font.render(
            f"HP: {max(0, self.player.health)}/{PLAYER_MAX_HEALTH}", True, WHITE)
        label_rect = health_label.get_rect(
            center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
        self.screen.blit(health_label, label_rect)

        # Level name
        if self.current_level_index < len(LEVELS):
            level_name = self.small_font.render(
                LEVELS[self.current_level_index]["name"], True, WHITE)
            name_rect = level_name.get_rect(center=(SCREEN_WIDTH // 2, 20))
            shadow = self.small_font.render(
                LEVELS[self.current_level_index]["name"], True, BLACK)
            self.screen.blit(shadow, (name_rect.x + 1, name_rect.y + 1))
            self.screen.blit(level_name, name_rect)

    def _draw_level_complete_overlay(self):
        """Show a brief overlay when the level is complete."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        if self.game_complete:
            msg = "YOU WIN! All Levels Complete!"
        else:
            msg = f"Level {self.current_level_index + 1} Complete!"
        text = self.big_font.render(msg, True, GOLD)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(text, rect)

        sub = self.font.render("Loading next level...", True, WHITE)
        sub_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(sub, sub_rect)

    def _draw_game_over_screen(self):
        """Show game over overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        text = self.big_font.render("GAME OVER", True, RED)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(text, rect)

        sub = self.font.render("Press R to restart", True, WHITE)
        sub_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
        self.screen.blit(sub, sub_rect)

        coins_text = self.font.render(
            f"Coins collected: {self.coins_collected}", True, YELLOW)
        coins_rect = coins_text.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
        self.screen.blit(coins_text, coins_rect)

    def _draw_win_screen(self):
        """Show win overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        text = self.big_font.render("YOU WIN!", True, GOLD)
        rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(text, rect)

        sub = self.font.render(
            f"All {len(LEVELS)} levels complete! Coins: {self.coins_collected}",
            True, WHITE)
        sub_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
        self.screen.blit(sub, sub_rect)

        restart_text = self.font.render("Press R to play again", True, WHITE)
        restart_rect = restart_text.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70))
        self.screen.blit(restart_text, restart_rect)

    def draw(self):
        self.screen.fill(self.bg_color)

        # Draw all sprites with camera offset
        for sprite in self.all_sprites:
            offset_rect = self.camera.apply(sprite.rect)
            self.screen.blit(sprite.image, offset_rect)

        # Draw HUD (not affected by camera)
        self._draw_hud()

        # Draw overlays
        if self.game_complete:
            self._draw_win_screen()
        elif self.game_over:
            self._draw_game_over_screen()
        elif self.goal_reached:
            self._draw_level_complete_overlay()

        pygame.display.flip()

    # ───────────────────────── game loop ─────────────────────────────

    def _restart_game(self):
        self.current_level_index = 0
        self.coins_collected = 0
        self.game_over = False
        self.game_complete = False
        self.goal_reached = False
        self._load_level(self.current_level_index)

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            self.update()
            self.draw()

        pygame.quit()
        sys.exit()
