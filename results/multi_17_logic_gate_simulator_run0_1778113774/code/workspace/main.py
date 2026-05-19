"""Main entry point for the Logic Gate Simulator."""

import sys
import pygame
from constants import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from canvas import Camera, draw_grid
from circuit import Circuit
from ui import UI


def main():
    pygame.init()
    pygame.display.set_caption("Logic Gate Simulator")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    camera = Camera()
    circuit = Circuit()
    ui = UI(circuit, camera)

    running = True

    while running:
        dt = clock.tick(FPS)

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            else:
                ui.handle_event(event)

        # Update
        ui.update()

        # Run circuit simulation each frame
        circuit.evaluate()

        # Drawing
        draw_grid(screen, camera)

        # Draw all wires
        for wire in circuit.wires:
            wire.draw(screen, camera)

        # Draw wire preview (during wiring)
        ui.draw_wire_preview(screen)

        # Draw all components
        for comp in circuit.components:
            selected = comp.comp_id in ui.selected_ids
            comp.draw(screen, camera, selected=selected)

        # Draw placement preview
        ui.draw_placement_preview(screen)

        # Draw rubber band selection
        ui.draw_rubber_band(screen)

        # Draw cycle warning
        ui.draw_cycle_warning(screen)

        # Draw properties panel
        ui.draw_properties_panel(screen)

        # Draw toolbar
        ui.draw_toolbar(screen)

        # Draw overlay (coordinates + zoom)
        ui.draw_overlay(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
