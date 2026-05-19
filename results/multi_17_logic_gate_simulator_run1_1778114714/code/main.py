"""Logic Gate Simulator - Main Entry Point."""
import sys
import os
import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    COLOR_BG, FONT_SIZE_NORMAL, TOOLBAR_WIDTH,
)
from canvas import Canvas
from circuit import Circuit
from toolbar import Toolbar
from input_handler import InputManager
from ui import draw_coordinate_overlay, draw_warning_overlay, draw_help_text


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, FONT_SIZE_NORMAL)

    # Core objects
    canvas = Canvas(WINDOW_WIDTH, WINDOW_HEIGHT)
    circuit = Circuit()
    toolbar = Toolbar()
    input_mgr = InputManager(canvas, circuit, toolbar)

    # For save/load callbacks
    save_callback = None
    load_callback = None

    running = True
    while running:
        dt = clock.tick(60)  # 60 FPS
        time_ms = pygame.time.get_ticks()

        # Update canvas size on resize
        current_w, current_h = screen.get_size()
        if current_w != canvas.width or current_h != canvas.height:
            canvas.width = current_w
            canvas.height = current_h
            canvas.canvas_rect = pygame.Rect(
                canvas.toolbar_width, 0,
                current_w - canvas.toolbar_width, current_h
            )
            toolbar.rect.height = current_h

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Handle save/load shortcuts before input_mgr
            if event.type == pygame.KEYDOWN and not input_mgr.is_dialog_open() and input_mgr.property_target is None:
                if event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
                    input_mgr.show_dialog("Save circuit (filename):", lambda name: save_circuit(name, circuit))
                    continue
                elif event.key == pygame.K_o and (event.mod & pygame.KMOD_CTRL):
                    input_mgr.show_dialog("Load circuit (filename):", lambda name: load_circuit(name, circuit, input_mgr))
                    continue

            # Zoom with mouse wheel
            if event.type == pygame.MOUSEWHEEL:
                if event.y != 0:
                    mx, my = pygame.mouse.get_pos()
                    if canvas.is_on_canvas(mx, my):
                        factor = 1.1 if event.y > 0 else 0.9
                        canvas.zoom_at(mx, my, factor)

            # Toolbar events
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx < canvas.toolbar_width:
                    result = toolbar.handle_event(event, canvas)
                    if result:
                        input_mgr.mode = InputManager.MODE_PLACING
                        input_mgr.selected_ids.clear()
                    else:
                        input_mgr.mode = InputManager.MODE_IDLE
                    continue

            # Pass to input manager
            input_mgr.handle_event(event)

        # Update clock components continuously
        for comp in circuit.components:
            from components import Clock
            if isinstance(comp, Clock):
                comp.update_state(time_ms)

        # Run simulation
        circuit.simulate(time_ms)

        # Clear screen
        screen.fill(COLOR_BG)

        # Draw canvas (grid)
        canvas.draw(screen)

        # Draw circuit
        circuit.draw(screen, canvas, font, input_mgr.selected_ids)

        # Draw input overlays (rubber band, wire preview, dialogs)
        input_mgr.draw(screen, font)

        # Draw toolbar (on top of canvas but to the left)
        toolbar.draw(screen)

        # Draw UI overlays
        draw_coordinate_overlay(screen, canvas)
        draw_warning_overlay(screen, circuit.warning_message)
        draw_help_text(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


def save_circuit(filename, circuit):
    """Save circuit to JSON file."""
    if not filename:
        return
    if not filename.endswith('.json'):
        filename += '.json'

    # Ensure sample_circuits directory exists
    dirname = os.path.dirname(filename)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)

    try:
        circuit.save_to_file(filename)
        print(f"Circuit saved to {filename}")
    except Exception as e:
        print(f"Error saving: {e}")


def load_circuit(filename, circuit, input_mgr):
    """Load circuit from JSON file."""
    if not filename:
        return
    if not filename.endswith('.json'):
        filename += '.json'

    # Check sample_circuits folder
    if not os.path.exists(filename):
        alt_path = os.path.join("sample_circuits", filename)
        if os.path.exists(alt_path):
            filename = alt_path

    try:
        circuit.load_from_file(filename)
        input_mgr.selected_ids.clear()
        input_mgr._cancel_current()
        print(f"Circuit loaded from {filename}")
    except Exception as e:
        print(f"Error loading: {e}")


if __name__ == "__main__":
    main()
