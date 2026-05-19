"""Canvas rendering: dot-grid background."""

import pygame
from config import GRID_SIZE, COLOR_GRID_DOT, COLOR_GRID_DOT_FADED, COLOR_BACKGROUND
from camera import Camera


class Canvas:
    """Renders the infinite dot-grid background."""

    @staticmethod
    def render(screen: pygame.Surface, camera: Camera):
        """Draw the dot-grid background."""
        screen.fill(COLOR_BACKGROUND)

        screen_w, screen_h = screen.get_size()

        # Get visible world rectangle
        world_tl = camera.screen_to_world((0, 0))
        world_br = camera.screen_to_world((screen_w, screen_h))

        # Determine grid spacing in world coordinates for dot skipping
        # At zoom < 0.5, skip every other dot; at zoom < 0.25, skip 3 of 4, etc.
        zoom = camera.zoom
        if zoom >= 0.5:
            step = 1
            color = COLOR_GRID_DOT
        elif zoom >= 0.25:
            step = 2
            color = COLOR_GRID_DOT_FADED
        else:
            step = 4
            color = COLOR_GRID_DOT_FADED

        grid_size = GRID_SIZE * step

        # Find start and end grid lines
        start_x = int(world_tl.x // grid_size) * grid_size
        start_y = int(world_tl.y // grid_size) * grid_size
        end_x = world_br.x
        end_y = world_br.y

        x = start_x
        while x <= end_x:
            y = start_y
            while y <= end_y:
                screen_pos = camera.world_to_screen((x, y))
                sx, sy = int(screen_pos.x), int(screen_pos.y)
                if 0 <= sx < screen_w and 0 <= sy < screen_h:
                    screen.set_at((sx, sy), color)
                y += grid_size
            x += grid_size
